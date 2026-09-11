"""Real USDC on Arc: the device's key, the chain, and escrow sessions.

TICK_FUNDING=arc-testnet swaps the paper balance for real testnet USDC:

1. The device shows its own Arc address as a QR code. The player sends it USDC
   from any wallet; a plain send from MetaMask works.
2. The device sees the transfer and who sent it, keeps a small fixed gas fee
   (USDC is Arc's gas token, so the device never needs another coin), and
   locks the rest in TickEscrow with openFor, in the sender's name.
3. Bets run on the device against that balance, exactly as in demo play.
4. Cashing out closes the session with the final balance, and the escrow pays
   it straight back to the address the USDC came from.

Chain work runs on one worker thread; the game thread only reads state and
posts requests, so a slow RPC never stalls a frame. The open sessions, the
local balance and the last block read are saved under .tick/, so a restart
resumes play and finishes an interrupted cash-out. The device key is created
there on first run and never leaves it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import os
from pathlib import Path
import queue
import threading
import time
import urllib.request

from eth_abi import decode, encode
from eth_account import Account
from eth_utils import keccak, to_checksum_address

from wallet import Deposit, parse_usdc

TICK_DIR = Path(__file__).resolve().parent / '.tick'
FUNDING_KINDS = ('arc-testnet',)

# Arc logs every USDC movement, native send or ERC-20 transfer, as a Transfer
# from this system address with an 18-decimal amount (EIP-7708). Watching it
# catches both kinds exactly once; the ERC-20 contract's own log would miss
# a plain send.
SYSTEM_LOGGER = '0xfffffffffffffffffffffffffffffffffffffffe'
NATIVE_PER_MICRO = 10 ** 12
MAX_UINT = 2 ** 256 - 1


def topic(signature: str) -> str:
    return '0x' + keccak(text=signature).hex()


TRANSFER = topic('Transfer(address,address,uint256)')
SESSION_OPENED = topic('SessionOpened(uint256,address,address,uint256,uint256)')
SESSION_CLOSED = topic('SessionClosed(uint256,uint256,uint256,int256)')


@dataclass(frozen=True)
class Network:
    name: str
    chain_id: int
    rpc: str
    explorer: str
    usdc: str
    escrow: str


NETWORKS = {
    'arc-testnet': Network('ARC TESTNET', 5042002, 'https://rpc.testnet.arc.io',
                           'https://testnet.arcscan.app',
                           '0x3600000000000000000000000000000000000000',
                           '0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627'),
}


def network(kind: str) -> Network:
    """The network for a TICK_FUNDING value, with TICK_ARC_RPC and TICK_ESCROW_ADDRESS overrides."""
    net = NETWORKS[kind]
    return replace(net, rpc=os.environ.get('TICK_ARC_RPC', net.rpc),
                   escrow=os.environ.get('TICK_ESCROW_ADDRESS', net.escrow))


def load_device(path: Path = TICK_DIR / 'device.json'):
    """The device's Arc account, created on first run. The key never leaves .tick/."""
    if path.exists():
        return Account.from_key(json.loads(path.read_text())['private_key'])
    account = Account.create()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump({'address': account.address, 'private_key': '0x' + bytes(account.key).hex()}, f)
    return account


def short(address: str) -> str:
    return f'{address[:6]}..{address[-4:]}' if address else ''


def calldata(signature: str, *args) -> str:
    """ABI-encode a call; the argument types come from the signature."""
    inner = signature[signature.index('(') + 1:-1]
    types = inner.split(',') if inner else []
    return '0x' + (keccak(text=signature)[:4] + encode(types, list(args))).hex()


class RpcError(Exception):
    pass


class Rpc:
    """Plain JSON-RPC over HTTPS: the standard library is enough."""

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout

    def __call__(self, method: str, *params):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': list(params)})
        request = urllib.request.Request(self.url, body.encode(), {
            'Content-Type': 'application/json', 'User-Agent': 'TICK-Hackathon/0.1'})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            reply = json.load(response)
        if 'error' in reply:
            error = reply['error']
            raise RpcError(error.get('message', str(error)) if isinstance(error, dict) else str(error))
        return reply['result']


@dataclass(frozen=True)
class Incoming:
    """USDC that arrived at the device."""
    sender: str
    amount: int     # micro-USDC
    key: str        # tx hash and log index: each transfer is taken once


@dataclass(frozen=True)
class House:
    free: int
    win_cap_bps: int
    max_deposit: int
    paused: bool


class Chain:
    """Everything the device does on Arc, as blocking calls. Tests use a fake."""
    TIP = 10 ** 9                 # 1 gwei
    MIN_FEE = 40 * 10 ** 9        # well over Arc's 20 gwei floor, below which a tx is dropped
    RECEIPT_TIMEOUT = 60.0

    def __init__(self, net: Network, account) -> None:
        self.net = net
        self.account = account
        self.address = account.address
        self.rpc = Rpc(net.rpc)

    def block(self) -> int:
        return int(self.rpc('eth_blockNumber'), 16)

    def _read(self, to: str, signature: str, out: list[str], *args) -> tuple:
        data = self.rpc('eth_call', {'to': to, 'data': calldata(signature, *args)}, 'latest')
        return decode(out, bytes.fromhex(data[2:]))

    def incoming(self, first: int, last: int) -> list[Incoming]:
        logs = self.rpc('eth_getLogs', {
            'fromBlock': hex(first), 'toBlock': hex(last), 'address': SYSTEM_LOGGER,
            'topics': [TRANSFER, None, '0x' + self.address[2:].lower().rjust(64, '0')]})
        return [Incoming(to_checksum_address('0x' + log['topics'][1][-40:]),
                         int(log['data'], 16) // NATIVE_PER_MICRO,
                         f"{log['transactionHash']}:{int(log['logIndex'], 16)}")
                for log in logs]

    def house(self) -> House:
        escrow = self.net.escrow
        free, = self._read(escrow, 'freeHouse()', ['uint256'])
        bps, = self._read(escrow, 'winCapBps()', ['uint256'])
        most, = self._read(escrow, 'maxSessionDeposit()', ['uint256'])
        paused, = self._read(escrow, 'paused()', ['bool'])
        return House(free, bps, most, paused)

    def allowance(self) -> int:
        return self._read(self.net.usdc, 'allowance(address,address)', ['uint256'],
                          self.address, self.net.escrow)[0]

    def session_open(self, sid: int) -> bool:
        return self._read(self.net.escrow, 'sessions(uint256)',
                          ['address', 'address', 'uint96', 'uint96', 'uint64', 'bool'], sid)[5]

    def approve_escrow(self) -> str:
        receipt = self.send(self.net.usdc, calldata('approve(address,uint256)', self.net.escrow, MAX_UINT))
        return receipt['transactionHash']

    def open_for(self, player: str, amount: int) -> tuple[int, int, int, str]:
        """Lock `amount` of the device's USDC for `player`: (id, deposit, reserve, tx)."""
        receipt = self.send(self.net.escrow, calldata('openFor(address,uint256,address)',
                                                      player, amount, self.address))
        log = self._event(receipt, SESSION_OPENED)
        deposit, reserve = decode(['uint256', 'uint256'], bytes.fromhex(log['data'][2:]))
        return int(log['topics'][1], 16), deposit, reserve, receipt['transactionHash']

    def close(self, sid: int, final: int) -> tuple[int, str]:
        """Settle a session at `final`: (payout to its player, tx)."""
        receipt = self.send(self.net.escrow, calldata('close(uint256,uint256)', sid, final))
        _, payout, _ = decode(['uint256', 'uint256', 'int256'],
                              bytes.fromhex(self._event(receipt, SESSION_CLOSED)['data'][2:]))
        return payout, receipt['transactionHash']

    def transfer(self, to: str, amount: int) -> str:
        return self.send(self.net.usdc, calldata('transfer(address,uint256)', to, amount))['transactionHash']

    def _event(self, receipt: dict, topic0: str) -> dict:
        for log in receipt['logs']:
            if log['address'].lower() == self.net.escrow.lower() and log['topics'][0] == topic0:
                return log
        raise RpcError('expected escrow event missing from receipt')

    def send(self, to: str, data: str) -> dict:
        """Sign and send one transaction and wait for its receipt. Raises on revert."""
        rpc = self.rpc
        gas = int(rpc('eth_estimateGas', {'from': self.address, 'to': to, 'data': data}), 16)
        price = int(rpc('eth_gasPrice'), 16)
        tx = {'type': 2, 'chainId': self.net.chain_id, 'to': to, 'data': data, 'value': 0,
              'nonce': int(rpc('eth_getTransactionCount', self.address, 'pending'), 16),
              'gas': gas * 5 // 4, 'maxPriorityFeePerGas': self.TIP,
              'maxFeePerGas': max(2 * price, self.MIN_FEE)}
        signed = self.account.sign_transaction(tx)
        raw = getattr(signed, 'raw_transaction', None) or signed.rawTransaction
        tx_hash = rpc('eth_sendRawTransaction', '0x' + bytes(raw).hex())
        deadline = time.monotonic() + self.RECEIPT_TIMEOUT
        while time.monotonic() < deadline:
            receipt = rpc('eth_getTransactionReceipt', tx_hash)
            if receipt:
                if int(receipt['status'], 16) != 1:
                    raise RpcError(f'transaction reverted: {tx_hash}')
                return receipt
            time.sleep(.4)
        raise RpcError(f'no receipt yet for {tx_hash}')


@dataclass
class Session:
    id: int
    player: str
    deposit: int
    reserve: int

    @property
    def cap(self) -> int:
        """The most the escrow will pay out for this session."""
        return self.deposit + self.reserve


class ArcFunding:
    """Real USDC through TickEscrow; see the module docstring.

    The game thread calls `sync` every frame and `cash_out` on request, and
    reads the plain attributes for display. The worker thread runs `step`,
    which tests call directly with a fake chain.
    """
    name = 'USDC'
    live = True
    onchain = True
    POLL_S = 1.5
    RETRY_S = 4.0
    MAX_RANGE = 5_000     # blocks per log query when catching up after downtime
    MAX_TRIES = 3         # a deposit that fails this often is set aside, not retried forever
    SEEN = 200            # transfers remembered, so a retried range never opens one twice

    def __init__(self, kind: str = 'arc-testnet', chain=None, state_path: Path | None = None,
                 gas_fee: int | None = None, start: bool = True) -> None:
        self.kind = kind
        self.net = network(kind)
        if not self.net.escrow:
            raise ValueError(f'No TickEscrow address for {kind}; set TICK_ESCROW_ADDRESS')
        self.chain = chain or Chain(self.net, load_device())
        self.address = self.chain.address
        self.gas_fee = (parse_usdc(os.environ.get('TICK_GAS_FEE_USDC', '0.01'))
                        if gas_fee is None else gas_fee)
        self.state_path = state_path or TICK_DIR / f'{kind}.json'
        self.lock = threading.Lock()
        self.events: queue.Queue[tuple] = queue.Queue()
        # Saved across restarts.
        self.sessions: list[Session] = []
        self.balance = 0                          # the game's balance, micro-USDC
        self.last_block: int | None = None
        self.pending_cashout: int | None = None   # a final balance still being paid out
        self.seen: list[str] = []
        # Shown on screen.
        self.status = 'CONNECTING TO ARC'
        self.busy = False
        self.error = ''
        self.last_deposit: tuple[int, str] | None = None
        self.last_cashout: tuple[int, str, str] | None = None   # paid, player, tx
        self.tries: dict[str, int] = {}
        self.checked = False
        self._load()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._worker: threading.Thread | None = None
        if start:
            self._worker = threading.Thread(target=self._run, name='arc-funding', daemon=True)
            self._worker.start()

    # ---- read by the game ------------------------------------------------
    @property
    def qr_text(self) -> str:
        """EIP-681: scanned in MetaMask, it opens a send to the device on this chain."""
        return f'ethereum:{self.address}@{self.net.chain_id}'

    @property
    def in_session(self) -> bool:
        return bool(self.sessions) and self.pending_cashout is None

    @property
    def cap(self) -> int | None:
        """The most the open sessions will pay out; the game never bets past it."""
        sessions = list(self.sessions)
        return sum(s.cap for s in sessions) if sessions else None

    @property
    def player(self) -> str:
        sessions = list(self.sessions)
        return sessions[-1].player if sessions else ''

    def tx_url(self, tx: str) -> str:
        return f'{self.net.explorer}/tx/{tx}'

    def load(self, amount: int) -> Deposit:
        """Real USDC is sent to the device, never minted by a button."""
        return Deposit(amount, 'failed', 'send-usdc-to-the-device')

    # ---- called by the game ----------------------------------------------
    def sync(self, wallet) -> list[tuple]:
        """Apply the worker's news to the wallet and save its balance. Every frame."""
        news = []
        with self.lock:
            while True:
                try:
                    event = self.events.get_nowait()
                except queue.Empty:
                    break
                if event[0] == 'opened':
                    wallet.credit(event[1])
                elif event[0] == 'ended':
                    wallet.balance = 0
                news.append(event)
            if self.pending_cashout is None and wallet.balance != self.balance:
                self.balance = wallet.balance
                self._save()
        return news

    def cash_out(self, wallet) -> bool:
        """Pay the whole balance back to the player; the worker sends it."""
        with self.lock:
            if not self.in_session:
                return False
            self.pending_cashout = wallet.balance
            wallet.balance = 0
            self.balance = 0
            self._save()
        self.status = 'CASHING OUT'
        self._wake.set()
        return True

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._worker is not None:
            self._worker.join(timeout=.2)

    # ---- the worker --------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.step()
                self.error = ''
                wait = self.POLL_S
            except Exception as exc:    # network, RPC or revert: show it and retry
                self.error = str(exc)[:120]
                self.status = 'ARC UNREACHABLE / RETRYING'
                self.busy = False
                wait = self.RETRY_S
            self._wake.wait(wait)
            self._wake.clear()

    def step(self) -> None:
        """One pass: finish any cash-out, then take the deposits that arrived."""
        if self.last_block is None:
            head = self.chain.block()
            with self.lock:
                # USDC that reached the device before it first ran is not a deposit.
                self.last_block = head
                self._save()
        if not self.checked:
            self._drop_ended_sessions()
            self.checked = True
        if self.pending_cashout is not None:
            self._pay_out()
        head = self.chain.block()
        while self.last_block < head:
            last = min(head, self.last_block + self.MAX_RANGE)
            for incoming in self.chain.incoming(self.last_block + 1, last):
                self._take(incoming)
            with self.lock:
                self.last_block = last
                self._save()
        if not self.busy:
            self.status = 'IN PLAY' if self.sessions else 'WAITING FOR USDC'

    def _drop_ended_sessions(self) -> None:
        """Forget sessions that ended while the device was off (a reclaim, say)."""
        still = [s for s in self.sessions if self.chain.session_open(s.id)]
        if len(still) == len(self.sessions):
            return
        with self.lock:
            self.sessions = still
            if not still and self.pending_cashout is None:
                self.balance = 0
                self.events.put(('ended',))
            self._save()

    def _take(self, incoming: Incoming) -> None:
        if incoming.key in self.seen:
            return
        if incoming.sender.lower() in (self.net.escrow.lower(), self.address.lower()):
            self._mark(incoming.key)
            return
        amount = incoming.amount - self.gas_fee
        if amount <= 0:
            self._mark(incoming.key)     # too small to play with: it tops up the gas
            return
        tries = self.tries.get(incoming.key, 0) + 1
        self.tries[incoming.key] = tries
        if tries > self.MAX_TRIES:
            self._mark(incoming.key)
            self.error = f'COULD NOT OPEN {incoming.key[:10]}; RECLAIM BY HAND'
            return
        self.busy = True
        self.status = 'OPENING SESSION'
        house = self.chain.house()
        reserve = amount * house.win_cap_bps // 10_000
        if house.paused or amount > house.max_deposit or reserve > house.free:
            reason = ('HOUSE PAUSED' if house.paused else
                      'OVER MAX DEPOSIT' if amount > house.max_deposit else 'HOUSE TOO SMALL')
            tx = self.chain.transfer(incoming.sender, amount)
            with self.lock:
                self._mark(incoming.key)
                self.events.put(('refunded', amount, incoming.sender, reason, tx))
            self.busy = False
            return
        if self.chain.allowance() < amount:
            self.chain.approve_escrow()
        sid, deposit, reserve, tx = self.chain.open_for(incoming.sender, amount)
        with self.lock:
            self.sessions.append(Session(sid, incoming.sender, deposit, reserve))
            self.balance += deposit
            self._mark(incoming.key)
            self.events.put(('opened', deposit, incoming.sender, tx))
        self.last_deposit = (deposit, incoming.sender)
        self.busy = False

    def _pay_out(self) -> None:
        """Close every open session, oldest first, until the final balance is paid."""
        self.busy = True
        self.status = 'CASHING OUT'
        paid: list[tuple[int, str, str]] = []
        while self.sessions:
            session = self.sessions[0]
            remaining = self.pending_cashout or 0
            payout, tx = 0, ''
            if self.chain.session_open(session.id):
                payout, tx = self.chain.close(session.id, min(remaining, session.cap))
            with self.lock:
                self.sessions.pop(0)
                self.pending_cashout = remaining - payout
                self._save()
            paid.append((payout, session.player, tx))
        with self.lock:
            self.pending_cashout = None
            self._save()
            self.events.put(('cashed_out', paid))
        if paid:
            self.last_cashout = (sum(p for p, _, _ in paid), paid[-1][1], paid[-1][2])
        self.busy = False

    # ---- saved state -------------------------------------------------------
    def _mark(self, key: str) -> None:
        """Remember a transfer as handled and save. Call with the lock held."""
        self.seen = (self.seen + [key])[-self.SEEN:]
        self.tries.pop(key, None)
        self._save()

    def _load(self) -> None:
        try:
            data = json.loads(self.state_path.read_text())
        except FileNotFoundError:
            return
        if data.get('escrow', '').lower() != self.net.escrow.lower():
            return    # sessions on another escrow are not this one's to close
        self.sessions = [Session(**s) for s in data.get('sessions', [])]
        self.balance = int(data.get('balance', 0))
        self.last_block = data.get('last_block')
        self.pending_cashout = data.get('pending_cashout')
        self.seen = list(data.get('seen', []))

    def _save(self) -> None:
        """Write the state atomically. Call with the lock held."""
        data = {'escrow': self.net.escrow, 'device': self.address, 'last_block': self.last_block,
                'balance': self.balance, 'pending_cashout': self.pending_cashout,
                'sessions': [asdict(s) for s in self.sessions], 'seen': self.seen}
        self.state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=1))
        os.replace(tmp, self.state_path)
