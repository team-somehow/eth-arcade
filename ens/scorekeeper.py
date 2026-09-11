"""TICK's players on ENS: a name for every wallet, and the leaderboard on the names.

    python ens/scorekeeper.py deploy   # once: tick.eth, its registry and resolver, the scorekeeper
    python ens/scorekeeper.py run      # while people play: names new players, writes their stats
    python ens/scorekeeper.py board    # the leaderboard, read back from ENS alone

Names live on ENSv2 on Sepolia; money stays on Arc. Two keys, two jobs:

- The TICK key (ARC_DEPLOYER_KEY in contracts/.env, also the escrow's owner)
  owns tick.eth, its own subname registry and its resolver. It names each new
  player <handle>.tick.eth: owned by the player's wallet, pointing at it on
  Ethereum and on Arc, not transferable, expiring at season end. The player
  may write their own profile records and nothing else.
- The scorekeeper key (ens/.tick/scorekeeper.json, created on deploy) is
  scorekeeper.tick.eth. The resolver lets it write the tick.* stats records on
  any name and nothing else: it cannot touch a profile, and a player cannot
  touch their own stats.

Stats come from TickEscrow's own events on Arc, so anyone can recompute them.
Run it with the firmware's venv: firmware/.venv/bin/python ens/scorekeeper.py run
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'firmware'))

from eth_abi import decode  # noqa: E402
from eth_account import Account  # noqa: E402
from eth_utils import keccak, to_checksum_address  # noqa: E402

import arc  # noqa: E402
import names  # noqa: E402
from arc import Chain, Network, Rpc, calldata, topic  # noqa: E402
from envfile import load_env_file  # noqa: E402
from names import PARENT, dns_encode, labelhash, namehash  # noqa: E402

# ENSv2 beta on Sepolia: https://docs.ens.domains/learn/deployments
ETH_REGISTRY = to_checksum_address('0xbdc85dd5b15d7ecb354cd7cb6f2c50b4f2c4f0e2')
ETH_REGISTRAR = to_checksum_address('0xa88553f454b77203b0d036a05c894d555eaaa2cc')
VERIFIABLE_FACTORY = to_checksum_address('0x10dc6333cdfe1fcef624c6e0a8221b91804cd7ef')
USER_REGISTRY_IMPL = to_checksum_address('0x624a25d67b59d587752ebec8dded8827dae52050')
RESOLVER_IMPL = to_checksum_address('0x9eae5c2730a7dd16bdd1dee6421a1b91e3b0365e')
# The registrar's payment token; anyone can mint it.
MOCK_USDC = to_checksum_address('0x768f42455a2d082e23ceef7d51e5787c82d67a39')

KEEPER_KEY = Path(__file__).resolve().parent / '.tick' / 'scorekeeper.json'
KEEPER_GAS = 10 ** 16                  # 0.01 Sepolia ETH, sent to the scorekeeper on deploy
REGISTER_DURATION = 365 * 86400        # tick.eth itself
SEASON_END = int(os.environ.get('TICK_SEASON_END', 1798761600))  # player names expire 2027-01-01
ESCROW_SINCE = 61593022                # TickEscrow 0x4FA3…8627's deploy block on Arc testnet
AVAILABLE = 0                          # IPermissionedRegistry.Status


def _with_admin(roles: int) -> int:
    return roles | roles << 128


# The TICK key's roles on its registry: registrar, register-reserved, set-parent,
# unregister, renew, set-subregistry, set-resolver, set-uri, upgrade; with admins.
REGISTRY_ROLES = _with_admin(sum(1 << n for n in (0, 4, 8, 12, 16, 20, 24, 36, 124)))
# ...and on its resolver: every record type, alias, clear and upgrade; with admins.
RESOLVER_ROLES = _with_admin(sum(1 << n for n in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 124)))

OPENED, CLOSED = arc.SESSION_OPENED, arc.SESSION_CLOSED
RECLAIMED = topic('SessionReclaimed(uint256,uint256)')
PROXY_DEPLOYED = topic('ProxyDeployed(address,address,uint256,address)')

KEEPER_CONTEXT = (
    'TICK scorekeeper. Watches TickEscrow (0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627, Arc '
    'testnet) and writes each player\'s tick.* stats records on their tick.eth name. It can '
    'write those records and nothing else.')


# ---- plumbing --------------------------------------------------------------

def call(signature: str, *args) -> bytes:
    """ABI-encoded calldata as bytes, for a multicall."""
    return bytes.fromhex(calldata(signature, *args)[2:])


def read(rpc: Rpc, to: str, signature: str, out: list[str], *args) -> tuple:
    data = rpc('eth_call', {'to': to, 'data': calldata(signature, *args)}, 'latest')
    return decode(out, bytes.fromhex(data[2:]))


def block_time(rpc: Rpc, block: str) -> int:
    return int(rpc('eth_getBlockByNumber', block, False)['timestamp'], 16)


def sepolia(account) -> Chain:
    net = names.ens()
    chain = Chain(Network('SEPOLIA', net.chain_id, net.rpc, 'https://sepolia.etherscan.io', '', ''),
                  account)
    chain.MIN_FEE = 2 * 10 ** 9    # Arc's 20 gwei floor does not apply here
    return chain


def team_account():
    load_env_file(ROOT / 'contracts' / '.env')
    key = os.environ.get('ARC_DEPLOYER_KEY', '')
    if not (key.startswith('0x') and len(key) == 66):
        sys.exit('Set ARC_DEPLOYER_KEY in contracts/.env: the TICK key that owns tick.eth')
    return Account.from_key(key)


def usdc(micro: int) -> str:
    """Micro-USDC as a plain decimal: 45000 -> '0.045', -5000 -> '-0.005'."""
    text = f'{Decimal(micro).scaleb(-6):f}'
    return text.rstrip('0').rstrip('.') if '.' in text else text


def player_records(name: str, player: str) -> list[bytes]:
    """A new player's name points at their wallet on Ethereum and Arc; the profile is theirs."""
    node = namehash(name)
    calls = [call('setAddr(bytes32,address)', node, player),
             call('setAddr(bytes32,uint256,bytes)', node, names.ARC_COIN_TYPE,
                  bytes.fromhex(player[2:]))]
    calls += [call('authorizeTextRoles(bytes,string,address,bool)', dns_encode(name), key, player,
                   True) for key in names.PROFILE]
    return calls


# ---- deploy ----------------------------------------------------------------

def salt_for(text: str) -> int:
    return int.from_bytes(keccak(text=f'{PARENT} {text}'), 'big')


def deploy_proxy(chain: Chain, implementation: str, salt: int, init: bytes) -> str:
    receipt = chain.send(VERIFIABLE_FACTORY, calldata('deployProxy(address,uint256,bytes)',
                                                      implementation, salt, init))
    for log in receipt['logs']:
        if log['topics'][0] == PROXY_DEPLOYED:
            return to_checksum_address('0x' + log['topics'][2][-40:])
    raise arc.RpcError('the factory deployed no proxy')


def deploy() -> None:
    team = sepolia(team_account())
    keeper = arc.load_device(KEEPER_KEY)
    rpc, me = team.rpc, team.address
    label = PARENT.split('.')[0]
    if not read(rpc, ETH_REGISTRAR, 'isAvailable(string)', ['bool'], label)[0]:
        sys.exit(f'{PARENT} is taken; pick a free name for names.PARENT')
    print(f'TICK key {me}, scorekeeper {keeper.address}')

    since = team.block()
    # The factory places a proxy by sender and salt alone, so each needs its own salt.
    stamp = time.time_ns()
    resolver = deploy_proxy(team, RESOLVER_IMPL, salt_for(f'resolver {stamp}'),
                            call('initialize(address,uint256,bytes[])', me, RESOLVER_ROLES, []))
    print(f'resolver  {resolver}')
    registry = deploy_proxy(team, USER_REGISTRY_IMPL, salt_for(f'registry {stamp}'),
                            call('initialize(address,uint256)', me, REGISTRY_ROLES))
    print(f'registry  {registry}')

    # tick.eth, committed then registered, paid in the registrar's mock USDC.
    base, premium = read(rpc, ETH_REGISTRAR, 'getRegisterPrice(string,uint64,address)',
                         ['uint256', 'uint256'], label, REGISTER_DURATION, MOCK_USDC)
    team.send(MOCK_USDC, calldata('mint(address,uint256)', me, base + premium))
    team.send(MOCK_USDC, calldata('approve(address,uint256)', ETH_REGISTRAR, base + premium))
    order = (label, me, os.urandom(32), registry, resolver, REGISTER_DURATION)
    commitment, = read(rpc, ETH_REGISTRAR,
                       'makeCommitment(string,address,bytes32,address,address,uint64,bytes32)',
                       ['bytes32'], *order, bytes(32))
    committed = team.send(ETH_REGISTRAR, calldata('commit(bytes32)', commitment))
    age, = read(rpc, ETH_REGISTRAR, 'MIN_COMMITMENT_AGE()', ['uint64'])
    ready = block_time(rpc, committed['blockNumber']) + age
    print(f'committed; registering {PARENT} in {age}s')
    while block_time(rpc, 'latest') <= ready:
        time.sleep(3)
    team.send(ETH_REGISTRAR, calldata(
        'register(string,address,bytes32,address,address,uint64,address,bytes32)',
        *order, MOCK_USDC, bytes(32)))
    team.send(registry, calldata('setParent(address,string)', ETH_REGISTRY, label))
    print(f'{PARENT} registered')

    # scorekeeper.tick.eth, allowed to write the stats records on any name.
    keeper_name = f'scorekeeper.{PARENT}'
    team.send(registry, calldata('register(string,address,address,address,uint256,uint64)',
                                 'scorekeeper', keeper.address, names.ZERO, resolver, 0, SEASON_END))
    calls = [
        call('setAddr(bytes32,address)', namehash(PARENT), me),
        call('setText(bytes32,string,string)', namehash(PARENT), 'description',
             'TICK, a handheld crypto arcade. Every player has a name here.'),
        call('setAddr(bytes32,address)', namehash(keeper_name), keeper.address),
        call('setText(bytes32,string,string)', namehash(keeper_name), 'agent-context',
             KEEPER_CONTEXT),
    ]
    calls += [call('authorizeTextRoles(bytes,string,address,bool)', dns_encode(''), key,
                   keeper.address, True) for key in names.STATS]
    team.send(resolver, calldata('multicall(bytes[])', calls))
    team.send(keeper.address, '0x', value=KEEPER_GAS)
    print(f'{keeper_name} may write {", ".join(names.STATS)}')
    print(f'\nTICK_ENS_REGISTRY={registry}\nTICK_ENS_RESOLVER={resolver}\nTICK_ENS_SINCE={since}')


# ---- run -------------------------------------------------------------------

@dataclass
class Stats:
    sessions: int = 0
    wins: int = 0
    deposited: int = 0   # micro-USDC
    paid: int = 0
    best: int = 0        # best single session, net
    last_tx: str = ''

    def close(self, deposit: int, payout: int, tx: str) -> None:
        net = payout - deposit
        self.best = net if self.sessions == 0 else max(self.best, net)
        self.sessions += 1
        self.wins += payout > deposit
        self.deposited += deposit
        self.paid += payout
        self.last_tx = tx

    def records(self) -> dict[str, str]:
        return dict(zip(names.STATS, (
            str(self.sessions), str(self.wins), usdc(self.deposited), usdc(self.paid),
            usdc(self.paid - self.deposited), usdc(self.best), self.last_tx)))


class Scorekeeper:
    """Follows TickEscrow on Arc; names players and publishes their stats on Sepolia."""
    POLL_S = 6.0
    RANGE = 10_000   # Arc blocks per log query

    def __init__(self, team: Chain, keeper: Chain, arc_rpc: Rpc, escrow: str, since: int) -> None:
        self.team, self.keeper = team, keeper
        self.net = names.ens()
        self.arc, self.escrow = arc_rpc, escrow
        self.last = since - 1
        self.open: dict[int, tuple[str, int]] = {}   # session id -> (player, deposit)
        self.stats: dict[str, Stats] = {}
        self.named: dict[str, str] = {}              # wallet -> name
        self.published: dict[str, dict[str, str]] = {}

    def step(self) -> None:
        self.scan()
        for player, stats in self.stats.items():
            if player not in self.named:
                self.named[player] = self.name(player)
            self.publish(self.named[player], stats.records())

    def scan(self) -> None:
        head = int(self.arc('eth_blockNumber'), 16)
        while self.last < head:
            last = min(head, self.last + self.RANGE)
            for log in self.arc('eth_getLogs', {
                    'fromBlock': hex(self.last + 1), 'toBlock': hex(last), 'address': self.escrow,
                    'topics': [[OPENED, CLOSED, RECLAIMED]]}):
                self.apply(log)
            self.last = last

    def apply(self, log: dict) -> None:
        kind, sid = log['topics'][0], int(log['topics'][1], 16)
        data = bytes.fromhex(log['data'][2:])
        if kind == OPENED:
            player = to_checksum_address('0x' + log['topics'][2][-40:])
            self.open[sid] = (player, decode(['uint256', 'uint256'], data)[0])
            self.stats.setdefault(player, Stats())
        elif sid in self.open:
            player, deposit = self.open.pop(sid)
            # A reclaim hands the deposit back: a session that broke even.
            payout = decode(['uint256', 'uint256', 'int256'], data)[1] if kind == CLOSED else deposit
            self.stats[player].close(deposit, payout, log['transactionHash'])

    def name(self, player: str) -> str:
        """The player's name, registered by the TICK key if the wallet has none yet."""
        rpc, net = self.team.rpc, self.net
        for attempt in range(names.ATTEMPTS):
            label = names.handle(player, attempt)
            name = f'{label}.{PARENT}'
            status, _, owner, _, _ = read(rpc, net.registry, 'getState(uint256)',
                                          ['uint8', 'uint64', 'address', 'uint256', 'uint256'],
                                          labelhash(label))
            if status == AVAILABLE:
                self.team.send(net.registry, calldata(
                    'register(string,address,address,address,uint256,uint64)',
                    label, player, names.ZERO, net.resolver, 0, SEASON_END))
            elif owner.lower() != player.lower():
                continue    # another wallet's handle
            if names.addr_of(rpc, net.resolver, name).lower() != player.lower():
                self.team.send(net.resolver, calldata('multicall(bytes[])',
                                                      player_records(name, player)))
                print(f'named {player} {name}')
            return name
        raise RuntimeError(f'no free handle for {player}')

    def publish(self, name: str, records: dict[str, str]) -> None:
        """Write the stats that changed, as the scorekeeper, in one transaction."""
        node = namehash(name)
        if name not in self.published:
            self.published[name] = {key: read(self.keeper.rpc, self.net.resolver,
                                              'text(bytes32,string)', ['string'], node, key)[0]
                                    for key in records}
        changed = {k: v for k, v in records.items() if self.published[name].get(k) != v}
        if not changed:
            return
        self.keeper.send(self.net.resolver, calldata('multicall(bytes[])', [
            call('setText(bytes32,string,string)', node, k, v) for k, v in changed.items()]))
        self.published[name].update(changed)
        print(f'{name}: ' + ', '.join(f'{k}={v}' for k, v in changed.items()))


def deployed() -> names.Ens:
    net = names.ens()
    if not (net.registry and net.resolver):
        sys.exit('No tick.eth registry yet: run deploy, then fill in names.SEPOLIA')
    return net


def run() -> None:
    deployed()
    net = arc.network('arc-testnet')
    keeper = Scorekeeper(sepolia(team_account()), sepolia(arc.load_device(KEEPER_KEY)),
                         Rpc(net.rpc), net.escrow,
                         int(os.environ.get('TICK_ESCROW_SINCE', ESCROW_SINCE)))
    print(f'scorekeeper {keeper.keeper.address} following {net.escrow}')
    while True:
        try:
            keeper.step()
        except Exception as exc:    # RPC hiccup or a revert: say so and try again
            print(f'retrying: {exc}')
        time.sleep(keeper.POLL_S)


# ---- board -----------------------------------------------------------------

def board() -> None:
    """The same standings the device shows: ENS alone, through the Universal Resolver."""
    rows = names.Standings(deployed()).read()
    print(f'{"#":>2}  {"PLAYER":<28} {"P&L":>10} {"SESSIONS":>8} {"WINS":>5} {"BEST":>9}')
    for rank, s in enumerate(rows, 1):
        print(f'{rank:>2}  {s.name:<28} {s.pnl:>10} {s.sessions:>8} {s.wins:>5} {s.best:>9}')


def main(argv: list[str]) -> None:
    commands = {'deploy': deploy, 'run': run, 'board': board}
    if len(argv) < 2 or argv[1] not in commands:
        sys.exit(__doc__)
    load_env_file()    # firmware/.env: TICK_ESCROW_ADDRESS and friends
    try:
        commands[argv[1]]()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main(sys.argv)
