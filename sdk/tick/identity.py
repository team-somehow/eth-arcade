"""Players have names, and the names carry their record.

A wallet address is not an identity a person can read, remember, or be proud
of. `0x7ee8...CCac` on a leaderboard is noise. So the SDK gives every wallet
that plays a **subname under a parent ENS name** -- `amber-otter.tick.eth` --
and writes that player's record into the name's own text records.

Why the record lives on the name
--------------------------------

The alternative is a database, which means a server, which means your game's
leaderboard dies when you stop paying for it and cannot be read by anything
else. Text records on an ENS name are read by any ENS client, survive the
game, and belong to the name rather than to your backend. The leaderboard here
is *derived*, not stored: it is a read of the registry plus one resolver call
per player.

The handle is derived from the address
--------------------------------------

`handle(address)` hashes the wallet into `adjective-noun`. That means a device
can work out which name to look for **without an index and without a lookup
service** -- it computes the candidate and asks the resolver whether that name
points back at this wallet. Collisions fall through to `-2`, `-3`; a name is
trusted only when its `addr` record resolves back to the wallet, so squatting
a handle gains nothing.

Who may write what
------------------

Two sets of records, split by who can write them:

    tick.*      sessions, wins, pnl, best, last_tx -- written only by the
                scorekeeper, because a player who could write their own
                score has no score
    avatar,
    description,
    url, ...    the player's own, written by the player

Everything in this module is **read-only**. Writing stats is a privileged,
single-instance job (see `docs/identity-ens.md`) and deliberately does not
live on the device.

Names and stats sit on their own chain, independent of wherever your money
settles -- keeping identity cheap and public while settlement stays fast.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
import os
import threading
import time

from .chain import Rpc, RpcError, _abi, calldata, topic

# ENSIP-11: an EVM chain's coin type is 0x80000000 | its chain id.
COIN_TYPE_BASE = 0x80000000
# ENS's Universal Resolver reads any name's records the way ENS apps do.
UNIVERSAL_RESOLVER = '0xeeeeeeee14d718c2b47d9923deab1335e144eeee'
LOG_RANGE = 10_000
ATTEMPTS = 4                 # handles tried per wallet before giving up
ZERO = '0x' + '00' * 20

# Records the scorekeeper writes. Rename the prefix for your own game.
STATS = ('tick.sessions', 'tick.wins', 'tick.deposited', 'tick.paid',
         'tick.pnl', 'tick.best', 'tick.last_tx')
# Records the player owns.
PROFILE = ('avatar', 'description', 'url', 'com.twitter')

ADJECTIVES = (
    'amber', 'bold', 'brisk', 'calm', 'cheeky', 'clever', 'cosmic', 'crafty', 'crisp', 'dusty',
    'eager', 'electric', 'fancy', 'fierce', 'frosty', 'gentle', 'glossy', 'golden', 'grand',
    'happy', 'hazy', 'jolly', 'keen', 'lucky', 'lunar', 'mellow', 'mighty', 'misty', 'neon',
    'nimble', 'noble', 'plucky', 'polar', 'proud', 'quick', 'quiet', 'rapid', 'rusty', 'salty',
    'shiny', 'silent', 'silver', 'sleek', 'sly', 'smooth', 'snappy', 'solar', 'sonic', 'spicy',
    'steady', 'stormy', 'sunny', 'swift', 'tidy', 'turbo', 'velvet', 'vivid', 'wild', 'windy',
    'witty', 'zany', 'zesty',
)
NOUNS = (
    'badger', 'bison', 'cobra', 'comet', 'crab', 'crane', 'dingo', 'eagle', 'falcon', 'ferret',
    'fox', 'gecko', 'hawk', 'heron', 'hornet', 'ibis', 'jackal', 'kiwi', 'koala', 'lark', 'lemur',
    'lynx', 'mantis', 'marmot', 'mink', 'mole', 'moose', 'moth', 'narwhal', 'newt', 'ocelot',
    'orca', 'otter', 'owl', 'panda', 'pelican', 'pony', 'puffin', 'quokka', 'raven', 'rhino',
    'robin', 'seal', 'shark', 'sloth', 'squid', 'swan', 'tapir', 'tiger', 'toad', 'toucan',
    'turtle', 'viper', 'vole', 'walrus', 'weasel', 'whale', 'wolf', 'wombat', 'yak', 'zebra',
)


@dataclass(frozen=True)
class Ens:
    """Where your game's names live. Point it at your own parent and registry."""
    parent: str        # the parent name, e.g. 'tick.eth'
    rpc: str
    chain_id: int
    registry: str      # the parent's own subname registry
    resolver: str      # the one resolver every subname uses
    since: int         # the registry's first block: where a leaderboard starts reading


SEPOLIA = Ens('tick.eth', 'https://ethereum-sepolia-rpc.publicnode.com', 11155111,
              '0xD25ACD4eB42A40D8145E3A7F1feFB17D09649cAa',
              '0xDBe98b10176aBf0BD2DFEE86fD3ee59A7630FAa8', 11684278)


def ens() -> Ens:
    """The configured names, with TICK_ENS_* overrides so a fork needs no code change."""
    env = os.environ.get
    return replace(SEPOLIA,
                   parent=env('TICK_ENS_PARENT', SEPOLIA.parent),
                   rpc=env('TICK_ENS_RPC', SEPOLIA.rpc),
                   registry=env('TICK_ENS_REGISTRY', SEPOLIA.registry),
                   resolver=env('TICK_ENS_RESOLVER', SEPOLIA.resolver),
                   since=int(env('TICK_ENS_SINCE', SEPOLIA.since)))


def coin_type(chain_id: int) -> int:
    """ENSIP-11 coin type for an EVM chain, for an address record on that chain."""
    return COIN_TYPE_BASE | chain_id


def namehash(name: str) -> bytes:
    _, _, _, keccak, _ = _abi()
    node = bytes(32)
    for label in reversed(name.split('.') if name else []):
        node = keccak(node + keccak(text=label))
    return node


def dns_encode(name: str) -> bytes:
    """A name in DNS wire format, as ENSv2 takes it."""
    out = b''
    for part in name.split('.') if name else []:
        out += bytes([len(part)]) + part.encode()
    return out + b'\0'


def labelhash(label: str) -> int:
    _, _, _, keccak, _ = _abi()
    return int.from_bytes(keccak(text=label), 'big')


def handle(address: str, attempt: int = 0) -> str:
    """The wallet's handle: `amber-otter`, then `amber-otter-2` if that is taken."""
    _, _, _, keccak, _ = _abi()
    h = keccak(bytes.fromhex(address[2:]))
    adjective = ADJECTIVES[int.from_bytes(h[:4], 'big') % len(ADJECTIVES)]
    noun = NOUNS[int.from_bytes(h[4:8], 'big') % len(NOUNS)]
    return f'{adjective}-{noun}' if attempt == 0 else f'{adjective}-{noun}-{attempt + 1}'


def addr_of(rpc: Rpc, resolver: str, name: str) -> str:
    """The name's address record, or ZERO if it has none."""
    decode, _, _, _, to_checksum_address = _abi()
    data = rpc('eth_call', {'to': resolver,
                            'data': calldata('addr(bytes32)', namehash(name))}, 'latest')
    return to_checksum_address(decode(['address'], bytes.fromhex(data[2:]))[0])


def name_of(address: str, net: Ens | None = None, rpc: Rpc | None = None) -> str | None:
    """The wallet's name, or None while nothing has named it.

    No index, no API: compute the candidate handle, ask the resolver, and
    accept it only if it points back at this wallet.
    """
    net = net or ens()
    if not net.resolver:
        return None
    rpc = rpc or Rpc(net.rpc)
    for attempt in range(ATTEMPTS):
        name = f'{handle(address, attempt)}.{net.parent}'
        owner = addr_of(rpc, net.resolver, name)
        if owner.lower() == address.lower():
            return name
        if owner == ZERO:
            return None    # handles are taken in order: no later one is this wallet's
    return None


def records_of(rpc: Rpc, name: str, keys=STATS,
               resolver: str = UNIVERSAL_RESOLVER) -> dict[str, str]:
    """Several text records of one name, in a single Universal Resolver call.

    One round trip for every key, rather than one per key: on a handheld
    reading a dozen players, that is the difference between a leaderboard and
    a spinner.
    """
    decode, _, _, _, _ = _abi()
    node = namehash(name)
    batch = [bytes.fromhex(calldata('text(bytes32,string)', node, key)[2:]) for key in keys]
    data = rpc('eth_call', {'to': resolver, 'data': calldata(
        'resolve(bytes,bytes)', dns_encode(name),
        bytes.fromhex(calldata('multicall(bytes[])', batch)[2:]))}, 'latest')
    result, _ = decode(['bytes', 'address'], bytes.fromhex(data[2:]))
    answers = decode(['bytes[]'], result)[0]
    return {key: decode(['string'], answer)[0] for key, answer in zip(keys, answers)}


@dataclass(frozen=True)
class Standing:
    name: str
    player: str        # the wallet the name was registered to
    sessions: int
    wins: int
    pnl: Decimal       # USDC
    best: Decimal      # best single session, USDC


class Standings:
    """The leaderboard, read from ENS alone.

    Registered names come from the registry's own `LabelRegistered` logs, and
    each name's stats from one resolver call. The block cursor is remembered,
    so a refresh asks only for blocks it has not read.
    """

    LABEL_REGISTERED = 'LabelRegistered(uint256,bytes32,string,address,uint64,address)'

    def __init__(self, net: Ens | None = None, rpc: Rpc | None = None, keys=STATS) -> None:
        self.net = net or ens()
        self.rpc = rpc or Rpc(self.net.rpc)
        self.keys = keys
        self.players: dict[str, str] = {}     # label -> the wallet it was registered to
        self.next_block = self.net.since

    def read(self) -> list[Standing]:
        decode, _, _, _, to_checksum_address = _abi()
        head = int(self.rpc('eth_blockNumber'), 16)
        while self.next_block <= head:
            last = min(head, self.next_block + LOG_RANGE - 1)
            for log in self.rpc('eth_getLogs', {
                    'fromBlock': hex(self.next_block), 'toBlock': hex(last),
                    'address': self.net.registry, 'topics': [topic(self.LABEL_REGISTERED)]}):
                label, owner, _ = decode(['string', 'address', 'uint64'],
                                         bytes.fromhex(log['data'][2:]))
                self.players[label] = to_checksum_address(owner)
            self.next_block = last + 1
        rows: list[Standing] = []
        for label, player in self.players.items():
            name = f'{label}.{self.net.parent}'
            try:
                stats = records_of(self.rpc, name, self.keys)
            except RpcError:      # a name the resolver no longer answers for
                continue
            if stats.get('tick.sessions'):
                rows.append(Standing(name, player, int(stats['tick.sessions']),
                                     int(stats.get('tick.wins') or 0),
                                     Decimal(stats.get('tick.pnl') or 0),
                                     Decimal(stats.get('tick.best') or 0)))
        rows.sort(key=lambda row: (-row.pnl, -row.wins, row.name))
        return rows


class Leaderboard:
    """`Standings` on a worker thread, so a slow RPC never costs a frame.

        board = Leaderboard()
        board.want()                # start reading
        ...
        for row in board.rows or []:
            draw(row)

    Nothing is read until it is first wanted, and it sleeps whenever the board
    is not on screen.
    """

    REFRESH_S = 20.0
    RETRY_S = 5.0

    def __init__(self, read=None) -> None:
        self.read = read
        self.rows: list[Standing] | None = None    # None until the first read lands
        self.error = ''
        self.updated = 0.0
        self.showing = False
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def want(self) -> None:
        if self._thread is None:
            if self.read is None:
                self.read = Standings().read
            self._thread = threading.Thread(target=self._run, name='ens-board', daemon=True)
            self._thread.start()
        self._wake.set()

    def refresh(self) -> bool:
        try:
            self.rows, self.error, self.updated = self.read(), '', time.monotonic()
            return True
        except Exception as exc:      # unreachable RPC: keep the last rows, say so
            self.error = str(exc)[:80] or 'ENS UNREACHABLE'
            return False

    def _run(self) -> None:
        while True:
            self._wake.clear()
            ok = self.refresh()
            self._wake.wait((self.REFRESH_S if ok else self.RETRY_S) if self.showing else None)
