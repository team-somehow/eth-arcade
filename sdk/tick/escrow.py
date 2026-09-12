"""Real money, without asking the player to trust the handheld.

The flow, and why each step exists
----------------------------------

1. The device shows **its own address** as a QR code. The player sends USDC
   from their own wallet -- a plain send from MetaMask works, no dApp, no
   connect, no signature prompt on a 480x320 screen.
2. The device watches the chain for that transfer, keeps a small fixed gas fee
   (USDC is the gas token on Arc, so the device never needs a second coin), and
   locks the rest in `TickEscrow` with `openFor`, **in the sender's name**.
3. Bets run on the device against that balance, exactly as in demo play. No
   transaction per bet: a 10-second round cannot wait for a block, and a player
   will not approve forty transactions an hour.
4. Cashing out closes the session at the final balance, and the escrow pays it
   **straight back to the address the USDC came from** -- not to the device, not
   to an operator. The device cannot send it anywhere else.

So the device never custodies anything it could run away with: one deposit in,
one settlement out, and the contract decides the payout.

The cap
-------

The escrow can only pay what it holds, so every session has a ceiling
(`deposit + reserve`). The wallet exposes it as `wallet.cap`, and a game must
refuse a bet whose best case would win past it -- otherwise the screen promises
a payout the contract will refuse. That check is one line; see
`Wallet.would_exceed_cap` and `GameContext.bet`.

Threading
---------

All chain work runs on one worker thread. The game thread calls `sync(wallet)`
every frame -- which only drains a queue -- and `cash_out(wallet)` on request. A
slow RPC can never stall a frame. State (open sessions, balance, last block
read) is saved under `.tick/`, so a restart resumes play and finishes an
interrupted cash-out rather than losing a session.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import queue
import threading
import time

from .chain import Chain, Incoming, load_device, network, short
from .money import Deposit, parse_usdc


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


class EscrowFunding:
    """A `Wallet` funding backend backed by a real escrow contract.

    Swap it in with TICK_FUNDING=arc-testnet; a game never imports it.
    """

    name = 'USDC'
    live = True
    onchain = True
    POLL_S = 1.5
    RETRY_S = 4.0
    MAX_RANGE = 5_000     # blocks per log query when catching up after downtime
    MAX_TRIES = 3         # a deposit failing this often is set aside, not retried forever
    SEEN = 200            # transfers remembered, so a retried range never opens one twice

    def __init__(self, kind: str = 'arc-testnet', chain=None, state_dir: str | Path = '.tick',
                 gas_fee: int | None = None, start: bool = True) -> None:
        self.kind = kind
        self.net = network(kind)
        if not self.net.escrow:
            raise ValueError(f'No escrow address for {kind}; set TICK_ESCROW_ADDRESS')
        self.state_dir = Path(state_dir)
        self.chain = chain or Chain(self.net, load_device(self.state_dir / 'device.json'))
        self.address = self.chain.address
        self.gas_fee = (parse_usdc(os.environ.get('TICK_GAS_FEE_USDC', '0.01'))
                        if gas_fee is None else gas_fee)
        self.state_path = self.state_dir / f'{kind}.json'
        self.lock = threading.Lock()
        self.events: queue.Queue[tuple] = queue.Queue()
        # Saved across restarts.
        self.sessions: list[Session] = []
        self.balance = 0
        self.last_block: int | None = None
        self.pending_cashout: int | None = None
        self.seen: list[str] = []
        # Shown on screen.
        self.status = 'CONNECTING'
        self.busy = False
        self.error = ''
        self.last_deposit: tuple[int, str] | None = None
        self.last_cashout: tuple[int, str, str] | None = None
        self.tries: dict[str, int] = {}
        self.checked = False
        self._load()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._worker: threading.Thread | None = None
        if start:
            self._worker = threading.Thread(target=self._run, name='escrow', daemon=True)
            self._worker.start()

    # ---- read by the game ------------------------------------------------
    @property
    def qr_text(self) -> str:
        """EIP-681: scanned in a wallet, it opens a send to the device on this chain."""
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

    @property
    def player_short(self) -> str:
        return short(self.player)

    def tx_url(self, tx: str) -> str:
        return f'{self.net.explorer}/tx/{tx}'

    def load(self, amount: int) -> Deposit:
        """Real USDC is sent to the device, never minted by a button."""
        return Deposit(amount, 'failed', 'send-usdc-to-the-device')

    # ---- called by the game ----------------------------------------------
    def sync(self, wallet) -> list[tuple]:
        """Apply the worker's news to the wallet and save. Cheap; call every frame."""
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
            self._worker.join(timeout=0.2)

    # ---- the worker ------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.step()
                self.error = ''
                wait = self.POLL_S
            except Exception as exc:      # network, RPC or revert: show it and retry
                self.error = str(exc)[:120]
                self.status = 'CHAIN UNREACHABLE / RETRYING'
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
            # Money the house cannot back is sent straight back, not held.
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

    # ---- saved state -----------------------------------------------------
    def _mark(self, key: str) -> None:
        """Remember a transfer as handled and save. Call with the lock held."""
        self.seen = (self.seen + [key])[-self.SEEN:]
        self.tries.pop(key, None)
        self._save()

    def _load(self) -> None:
        try:
            data = json.loads(self.state_path.read_text())
        except (FileNotFoundError, ValueError):
            return
        if data.get('escrow', '').lower() != self.net.escrow.lower():
            return      # sessions on another escrow are not this one's to close
        self.sessions = [Session(**s) for s in data.get('sessions', [])]
        self.balance = int(data.get('balance', 0))
        self.last_block = data.get('last_block')
        self.pending_cashout = data.get('pending_cashout')
        self.seen = list(data.get('seen', []))

    def _save(self) -> None:
        """Write the state atomically. Call with the lock held."""
        data = {'escrow': self.net.escrow, 'device': self.address,
                'last_block': self.last_block, 'balance': self.balance,
                'pending_cashout': self.pending_cashout,
                'sessions': [asdict(s) for s in self.sessions], 'seen': self.seen}
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=1))
        os.replace(tmp, self.state_path)


FUNDING_KINDS = ('demo', 'arc-testnet')


def build_wallet(kind: str | None = None, balance: int | None = None):
    """The wallet named by TICK_FUNDING: paper by default, real USDC on request."""
    from .money import MICRO, DemoFunding, Wallet
    kind = (kind or os.environ.get('TICK_FUNDING', 'demo')).strip()
    if kind not in FUNDING_KINDS:
        raise ValueError(f"TICK_FUNDING must be one of {', '.join(FUNDING_KINDS)}")
    if kind == 'demo':
        return Wallet(100 * MICRO if balance is None else balance, DemoFunding())
    funding = EscrowFunding(kind)
    return Wallet(funding.balance, funding)
