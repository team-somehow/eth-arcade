"""The smallest chain client that can hold a player's money honestly.

Plain JSON-RPC over HTTPS with the standard library, plus `eth-account` and
`eth-abi` for signing and ABI encoding. No web3, no async, no provider stack:
this runs on a Pi Zero and installs in seconds.

Everything here is **blocking**. That is deliberate and safe, because nothing
here is ever called from the frame loop -- `tick.escrow` runs it on a worker
thread and the game only reads finished state. A slow RPC must never cost a
frame; a dropped frame on a handheld is felt immediately.

The device key
--------------

Created on first run in `.tick/device.json`, mode 0600, and it never leaves
that folder. It is not the player's key and holds nothing but gas: the player
keeps their own wallet and the escrow pays them back directly.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import time
import urllib.request

USER_AGENT = 'tick-sdk/0.1'


def _abi():
    """Import the ABI/signing libraries, with a message worth reading if absent."""
    try:
        from eth_abi import decode, encode
        from eth_account import Account
        from eth_utils import keccak, to_checksum_address
    except ImportError as exc:      # pragma: no cover - depends on the install
        raise ImportError(
            'Real funds need the chain extras: pip install "tick-sdk[chain]" '
            '(eth-account, eth-abi, eth-utils). Demo play needs none of them.'
        ) from exc
    return decode, encode, Account, keccak, to_checksum_address


def topic(signature: str) -> str:
    _, _, _, keccak, _ = _abi()
    return '0x' + keccak(text=signature).hex()


def calldata(signature: str, *args) -> str:
    """ABI-encode a call; the argument types come from the signature itself."""
    decode, encode, _, keccak, _ = _abi()
    inner = signature[signature.index('(') + 1:-1]
    types = inner.split(',') if inner else []
    return '0x' + (keccak(text=signature)[:4] + encode(types, list(args))).hex()


@dataclass(frozen=True)
class Network:
    name: str
    chain_id: int
    rpc: str
    explorer: str
    usdc: str
    escrow: str
    # Arc logs every USDC movement -- native send or ERC-20 transfer -- as a
    # Transfer from this system address with an 18-decimal amount (EIP-7708).
    # Watching it catches both kinds exactly once; the token contract's own log
    # would miss a plain send. A chain without it leaves this empty and the
    # token address is watched instead.
    system_logger: str = ''
    native_per_micro: int = 10 ** 12


NETWORKS = {
    'arc-testnet': Network(
        'ARC TESTNET', 5042002, 'https://rpc.testnet.arc.io',
        'https://testnet.arcscan.app',
        '0x3600000000000000000000000000000000000000',
        '0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627',
        system_logger='0xfffffffffffffffffffffffffffffffffffffffe'),
}


def network(kind: str) -> Network:
    """A named network, with TICK_ARC_RPC / TICK_ESCROW_ADDRESS overrides applied."""
    if kind not in NETWORKS:
        raise ValueError(f"Unknown network {kind!r}; known: {', '.join(NETWORKS)}")
    net = NETWORKS[kind]
    return replace(net,
                   rpc=os.environ.get('TICK_ARC_RPC', net.rpc),
                   escrow=os.environ.get('TICK_ESCROW_ADDRESS', net.escrow))


def load_device(path: str | Path = '.tick/device.json'):
    """The device's account, created on first run. Mode 0600, never copied out."""
    _, _, Account, _, _ = _abi()
    path = Path(path)
    if path.exists():
        return Account.from_key(json.loads(path.read_text())['private_key'])
    account = Account.create()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump({'address': account.address,
                   'private_key': '0x' + bytes(account.key).hex()}, handle)
    return account


def short(address: str) -> str:
    return f'{address[:6]}..{address[-4:]}' if address else ''


class RpcError(Exception):
    pass


class Rpc:
    """Plain JSON-RPC over HTTPS."""

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout

    def __call__(self, method: str, *params):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': list(params)})
        request = urllib.request.Request(
            self.url, body.encode(),
            {'Content-Type': 'application/json', 'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            reply = json.load(response)
        if 'error' in reply:
            error = reply['error']
            raise RpcError(error.get('message', str(error))
                           if isinstance(error, dict) else str(error))
        return reply['result']


@dataclass(frozen=True)
class Incoming:
    """USDC that arrived at the device."""
    sender: str
    amount: int      # micro-USDC
    key: str         # tx hash and log index: each transfer is taken exactly once


@dataclass(frozen=True)
class House:
    """What the escrow will currently accept and pay."""
    free: int
    win_cap_bps: int
    max_deposit: int
    paused: bool


MAX_UINT = 2 ** 256 - 1


class Chain:
    """Every on-chain call the SDK makes, as blocking methods.

    Tests never touch a network: they pass a fake object with these same
    methods to `EscrowFunding(chain=...)`, which is why the escrow state
    machine is fully testable offline.
    """

    TIP = 10 ** 9                # 1 gwei
    MIN_FEE = 40 * 10 ** 9       # over Arc's 20 gwei floor, under which a tx is dropped
    RECEIPT_TIMEOUT = 60.0

    def __init__(self, net: Network, account) -> None:
        self.net = net
        self.account = account
        self.address = account.address
        self.rpc = Rpc(net.rpc)

    def block(self) -> int:
        return int(self.rpc('eth_blockNumber'), 16)

    def _read(self, to: str, signature: str, out: list[str], *args) -> tuple:
        decode, _, _, _, _ = _abi()
        data = self.rpc('eth_call', {'to': to, 'data': calldata(signature, *args)}, 'latest')
        return decode(out, bytes.fromhex(data[2:]))

    def incoming(self, first: int, last: int) -> list[Incoming]:
        """USDC transfers into the device between two blocks, inclusive."""
        _, _, _, _, to_checksum_address = _abi()
        source = self.net.system_logger or self.net.usdc
        logs = self.rpc('eth_getLogs', {
            'fromBlock': hex(first), 'toBlock': hex(last), 'address': source,
            'topics': [topic('Transfer(address,address,uint256)'), None,
                       '0x' + self.address[2:].lower().rjust(64, '0')]})
        scale = self.net.native_per_micro if self.net.system_logger else 1
        return [Incoming(to_checksum_address('0x' + log['topics'][1][-40:]),
                         int(log['data'], 16) // scale,
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
        return self.send(self.net.usdc,
                         calldata('approve(address,uint256)', self.net.escrow, MAX_UINT)
                         )['transactionHash']

    def open_for(self, player: str, amount: int) -> tuple[int, int, int, str]:
        """Lock `amount` of the device's USDC for `player`: (id, deposit, reserve, tx)."""
        decode, _, _, _, _ = _abi()
        receipt = self.send(self.net.escrow,
                            calldata('openFor(address,uint256,address)',
                                     player, amount, self.address))
        log = self._event(receipt, topic('SessionOpened(uint256,address,address,uint256,uint256)'))
        deposit, reserve = decode(['uint256', 'uint256'], bytes.fromhex(log['data'][2:]))
        return int(log['topics'][1], 16), deposit, reserve, receipt['transactionHash']

    def close(self, sid: int, final: int) -> tuple[int, str]:
        """Settle a session at `final`: (payout to its player, tx)."""
        decode, _, _, _, _ = _abi()
        receipt = self.send(self.net.escrow, calldata('close(uint256,uint256)', sid, final))
        log = self._event(receipt, topic('SessionClosed(uint256,uint256,uint256,int256)'))
        _, payout, _ = decode(['uint256', 'uint256', 'int256'], bytes.fromhex(log['data'][2:]))
        return payout, receipt['transactionHash']

    def transfer(self, to: str, amount: int) -> str:
        return self.send(self.net.usdc,
                         calldata('transfer(address,uint256)', to, amount))['transactionHash']

    def _event(self, receipt: dict, topic0: str) -> dict:
        for log in receipt['logs']:
            if log['address'].lower() == self.net.escrow.lower() and log['topics'][0] == topic0:
                return log
        raise RpcError('expected escrow event missing from receipt')

    def send(self, to: str, data: str, value: int = 0) -> dict:
        """Sign, send, and wait for the receipt. Raises on revert."""
        rpc = self.rpc
        gas = int(rpc('eth_estimateGas', {'from': self.address, 'to': to,
                                          'data': data, 'value': hex(value)}), 16)
        price = int(rpc('eth_gasPrice'), 16)
        tx = {'type': 2, 'chainId': self.net.chain_id, 'to': to, 'data': data, 'value': value,
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
            time.sleep(0.4)
        raise RpcError(f'no receipt yet for {tx_hash}')
