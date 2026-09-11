"""Player names: every wallet that plays TICK gets <handle>.tick.eth.

The money stays on Arc; the names live on ENSv2 on Sepolia. Nothing changes
for the player: the scorekeeper (ens/scorekeeper.py) names a wallet when its
first session opens and writes its stats to the name after every close.

A handle comes from the wallet address (amber-otter), so the device knows which
name to look for without an index. It trusts the name only once the name's
address record points back at the wallet.

The leaderboard (Standings) is read from ENS alone: the names in tick.eth's
registry, and their stats through ENS's Universal Resolver.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
import os

from eth_abi import decode
from eth_utils import keccak, to_checksum_address

from arc import Rpc, RpcError, calldata, topic

PARENT = 'tick.eth'
# ENS's Universal Resolver on Sepolia: reads any name's records the way ENS apps do.
UNIVERSAL_RESOLVER = to_checksum_address('0xeeeeeeee14d718c2b47d9923deab1335e144eeee')
LABEL_REGISTERED = topic('LabelRegistered(uint256,bytes32,string,address,uint64,address)')
LOG_RANGE = 10_000     # blocks per eth_getLogs
# ENSIP-11: an EVM chain's coin type is 0x80000000 | its chain id.
ARC_COIN_TYPE = 0x80000000 | 5042002
# Text records only the scorekeeper may write, on every name.
STATS = ('tick.sessions', 'tick.wins', 'tick.deposited', 'tick.paid', 'tick.pnl', 'tick.best',
         'tick.last_tx')
# Text records only a name's own player may write.
PROFILE = ('avatar', 'description', 'url', 'com.twitter')
# Handles tried per wallet: amber-otter, then amber-otter-2, and so on.
ATTEMPTS = 4
ZERO = '0x' + '00' * 20

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
    rpc: str
    chain_id: int
    registry: str   # tick.eth's own subname registry
    resolver: str   # the one resolver every tick.eth name uses
    since: int      # the registry's first block, where the leaderboard starts reading


SEPOLIA = Ens('https://ethereum-sepolia-rpc.publicnode.com', 11155111,
              '0xD25ACD4eB42A40D8145E3A7F1feFB17D09649cAa',
              '0xDBe98b10176aBf0BD2DFEE86fD3ee59A7630FAa8', 11684278)


def ens() -> Ens:
    """TICK's names on Sepolia, with TICK_ENS_RPC/_REGISTRY/_RESOLVER/_SINCE overrides."""
    env = os.environ.get
    return replace(SEPOLIA, rpc=env('TICK_ENS_RPC', SEPOLIA.rpc),
                   registry=env('TICK_ENS_REGISTRY', SEPOLIA.registry),
                   resolver=env('TICK_ENS_RESOLVER', SEPOLIA.resolver),
                   since=int(env('TICK_ENS_SINCE', SEPOLIA.since)))


def namehash(name: str) -> bytes:
    node = bytes(32)
    for label in reversed(name.split('.') if name else []):
        node = keccak(node + keccak(text=label))
    return node


def dns_encode(name: str) -> bytes:
    """A name in DNS wire format, as ENSv2 takes it. The empty name means any name."""
    out = b''
    for label in name.split('.') if name else []:
        out += bytes([len(label)]) + label.encode()
    return out + b'\0'


def labelhash(label: str) -> int:
    return int.from_bytes(keccak(text=label), 'big')


def handle(address: str, attempt: int = 0) -> str:
    """The wallet's handle: amber-otter, or amber-otter-2 when the first is someone else's."""
    h = keccak(bytes.fromhex(address[2:]))
    adjective = ADJECTIVES[int.from_bytes(h[:4], 'big') % len(ADJECTIVES)]
    noun = NOUNS[int.from_bytes(h[4:8], 'big') % len(NOUNS)]
    return f'{adjective}-{noun}' if attempt == 0 else f'{adjective}-{noun}-{attempt + 1}'


def addr_of(rpc: Rpc, resolver: str, name: str) -> str:
    """The name's Ethereum address record, or ZERO if it has none."""
    data = rpc('eth_call', {'to': resolver, 'data': calldata('addr(bytes32)', namehash(name))},
               'latest')
    return to_checksum_address(decode(['address'], bytes.fromhex(data[2:]))[0])


def name_of(address: str, net: Ens | None = None, rpc: Rpc | None = None) -> str | None:
    """The wallet's tick.eth name, or None while the scorekeeper has not named it."""
    net = net or ens()
    if not net.resolver:
        return None
    rpc = rpc or Rpc(net.rpc)
    for attempt in range(ATTEMPTS):
        name = f'{handle(address, attempt)}.{PARENT}'
        owner = addr_of(rpc, net.resolver, name)
        if owner.lower() == address.lower():
            return name
        if owner == ZERO:
            return None    # handles are taken in order, so no later one is this wallet's
    return None


def stats_of(rpc: Rpc, name: str) -> dict[str, str]:
    """The name's tick.* records, all in one Universal Resolver call."""
    node = namehash(name)
    batch = [bytes.fromhex(calldata('text(bytes32,string)', node, key)[2:]) for key in STATS]
    data = rpc('eth_call', {'to': UNIVERSAL_RESOLVER, 'data': calldata(
        'resolve(bytes,bytes)', dns_encode(name),
        bytes.fromhex(calldata('multicall(bytes[])', batch)[2:]))}, 'latest')
    result, _ = decode(['bytes', 'address'], bytes.fromhex(data[2:]))
    answers = decode(['bytes[]'], result)[0]
    return {key: decode(['string'], answer)[0] for key, answer in zip(STATS, answers)}


@dataclass(frozen=True)
class Standing:
    name: str
    player: str      # the wallet the name was registered to
    sessions: int
    wins: int
    pnl: Decimal     # USDC
    best: Decimal    # the best single session, USDC


class Standings:
    """The leaderboard: every tick.eth name with stats, best P&L first.

    Remembers how far it has read the registry, so a refresh asks only for the
    new blocks, then one Universal Resolver call per player.
    """

    def __init__(self, net: Ens | None = None, rpc: Rpc | None = None) -> None:
        self.net = net or ens()
        self.rpc = rpc or Rpc(self.net.rpc)
        self.players: dict[str, str] = {}    # label -> the wallet it was registered to
        self.next_block = self.net.since

    def read(self) -> list[Standing]:
        head = int(self.rpc('eth_blockNumber'), 16)
        while self.next_block <= head:
            last = min(head, self.next_block + LOG_RANGE - 1)
            for log in self.rpc('eth_getLogs', {
                    'fromBlock': hex(self.next_block), 'toBlock': hex(last),
                    'address': self.net.registry, 'topics': [LABEL_REGISTERED]}):
                label, owner, _ = decode(['string', 'address', 'uint64'],
                                         bytes.fromhex(log['data'][2:]))
                self.players[label] = to_checksum_address(owner)
            self.next_block = last + 1
        rows = []
        for label, player in self.players.items():
            name = f'{label}.{PARENT}'
            try:
                stats = stats_of(self.rpc, name)
            except RpcError:    # a name ENS no longer resolves
                continue
            if stats['tick.sessions']:    # the scorekeeper's own name has none
                rows.append(Standing(name, player, int(stats['tick.sessions']),
                                     int(stats['tick.wins'] or 0), Decimal(stats['tick.pnl'] or 0),
                                     Decimal(stats['tick.best'] or 0)))
        rows.sort(key=lambda row: (-row.pnl, -row.wins, row.name))
        return rows
