"""Adds the ETH/USDC pools found in Messari's standardized DEX subgraphs to .env.

The stream prices ETH from every pool in TICK_POOLS_<CHAIN>, and each pool
needs its token order and decimals to turn sqrtPriceX96 into dollars. Messari's
DEX subgraphs on The Graph know both for every pool, in one schema shared by
every protocol and chain. So this sends the same query to each subgraph in
TICK_SUBGRAPHS_<CHAIN>, Uniswap V3 and Sushiswap V3 alike, and a protocol is
added by its subgraph id, with no code.

It only adds. A pool already listed is left exactly as it is, and a chain whose
subgraphs cannot be reached keeps its list, so running this never costs the
stream a pool. Pools no subgraph covers, Aerodrome Slipstream and Uniswap v4,
stay listed by hand. Restart relay.py afterwards: stream.sh reads .env when it
starts.

Standard library only.

    python3 pools.py             # add what it finds to .env
    python3 pools.py --dry-run   # show it and change nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / '.env'
GATEWAY = 'https://gateway.thegraph.com/api/{key}/subgraphs/id/{subgraph}'

# A pool's price is only pulled back to the market once it is a fee away, so a
# 0.3% pool can sit about $7 off, more than a box. The same reason the
# hand-picked lists leave them out.
MAX_FEE_PERCENT = 0.05
# Below this a pool trades too rarely for its last price to be the market's.
# Counted in the USDC the pool holds, which needs no price to read: the
# subgraphs' USD figures put some of the biggest pools at $0.
MIN_USDC = 25_000
ATTEMPTS = 3
FIELDS = 'id name inputTokens { id symbol decimals } inputTokenBalances fees { feeType feePercentage }'


def read_env(path: Path) -> dict[str, str]:
    """KEY=value lines, as stream.sh sources them; comments and blanks skipped."""
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        values[key.strip()] = value.strip().strip('"\'')
    return values


def split(value: str) -> list[str]:
    return [item.strip() for item in value.split(',') if item.strip()]


def pools_query(pairs: list[list[str]]) -> str:
    """One query for every pair, an alias each, so a subgraph is asked once."""
    parts = [f'p{i}: liquidityPools(first: 20, where: {{inputTokens: {json.dumps(pair)}}}) {{ {FIELDS} }}'
             for i, pair in enumerate(pairs)]
    return '{ protocols(first: 1) { name network } ' + ' '.join(parts) + ' }'


def ask(key: str, subgraph: str, query: str) -> dict:
    """The query's data; raises RuntimeError once every attempt has failed.

    The gateway answers a busy or lagging indexer with an error rather than a
    slow reply, so a failure is worth a second try a few seconds later.
    """
    request = urllib.request.Request(
        GATEWAY.format(key=key, subgraph=subgraph), json.dumps({'query': query}).encode(),
        {'Content-Type': 'application/json', 'User-Agent': 'TICK-Hackathon/0.1'})
    problem = ''
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(5 * attempt)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                answer = json.load(response)
        except (OSError, ValueError) as error:
            problem = str(error)
            continue
        if answer.get('errors'):
            problem = str(answer['errors'][0].get('message', answer['errors'][0]))
            continue
        return answer['data']
    raise RuntimeError(problem[:120])


def trading_fee(pool: dict) -> float | None:
    for fee in pool['fees']:
        if fee['feeType'] == 'FIXED_TRADING_FEE':
            return float(fee['feePercentage'])
    return None


def usdc_held(pool: dict, usdcs: list[str]) -> float:
    """Dollars of USDC in the pool, read straight from its token balance."""
    for token, balance in zip(pool['inputTokens'], pool['inputTokenBalances']):
        if token['id'] in usdcs:
            return int(balance) / 10 ** int(token['decimals'])
    return 0.0


def pool_entry(pool: dict, eth: str) -> str:
    """The pool as map_pool_prices takes it, quoted in USDC per ETH."""
    token0, token1 = pool['inputTokens']
    entry = f"{pool['id']}:{token0['decimals']}:{token1['decimals']}"
    # The module quotes token1 per token0, which with USDC as token0 would be
    # ETH per dollar.
    return entry if token0['id'] == eth else entry + ':invert'


def find(chain: str, env: dict[str, str], key: str, listed: set[str], min_usdc: float) -> list[str]:
    """Entries for the chain's ETH/USDC pools not yet listed, reporting each pool seen."""
    upper = chain.upper()
    subgraphs = split(env.get(f'TICK_SUBGRAPHS_{upper}', ''))
    eth = env.get(f'TICK_ETH_{upper}', '').lower()
    usdcs = [usdc.lower() for usdc in split(env.get(f'TICK_USDC_{upper}', ''))]
    if not (subgraphs and eth and usdcs):
        print(f'  skipped: set TICK_SUBGRAPHS_{upper}, TICK_ETH_{upper} and TICK_USDC_{upper}')
        return []
    # A v3 pool lists its tokens in address order, and the filter matches that order.
    pairs = [sorted([eth, usdc]) for usdc in usdcs]
    query = pools_query(pairs)
    found = []
    for subgraph in subgraphs:
        try:
            data = ask(key, subgraph, query)
        except RuntimeError as error:
            print(f'  {subgraph[:10]}...: unreachable, its pools stay as they are ({error})')
            continue
        protocol = (data.get('protocols') or [{}])[0]
        pools = [pool for i in range(len(pairs)) for pool in data.get(f'p{i}') or []]
        print(f"  {protocol.get('name', subgraph)} on {protocol.get('network', '?')}: "
              f'{len(pools)} ETH/USDC pools')
        for pool in sorted(pools, key=lambda p: -usdc_held(p, usdcs)):
            fee, held = trading_fee(pool), usdc_held(pool, usdcs)
            if pool['id'] in listed:
                mark, verdict = '=', 'already listed'
            elif fee is None or fee > MAX_FEE_PERCENT:
                mark, verdict = '-', f'left out, {fee:g}% fee' if fee is not None else 'left out, fee unknown'
            elif held < min_usdc:
                mark, verdict = '-', 'left out, too small'
            else:
                mark, verdict = '+', 'added'
                found.append(pool_entry(pool, eth))
                listed.add(pool['id'])
            print(f"    {mark} {pool['id']}  {pool['name']:<42} {held:>13,.0f} USDC  {verdict}")
    return found


def write_env(path: Path, updates: dict[str, str]) -> None:
    """Replaces just the named lines; every other line is kept as written."""
    lines = path.read_text().splitlines()
    for name, value in updates.items():
        for i, line in enumerate(lines):
            if line.partition('=')[0].strip() == name:
                lines[i] = f'{name}={value}'
                break
        else:
            lines.append(f'{name}={value}')
    path.write_text('\n'.join(lines) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--dry-run', action='store_true', help='show what would be added; change nothing')
    parser.add_argument('--min-usdc', type=float, default=MIN_USDC,
                        help=f'smallest pool to add, by the USDC it holds (default {MIN_USDC:,})')
    args = parser.parse_args()

    if not ENV_FILE.exists():
        sys.exit('no .env here: copy .env.example to .env')
    env = read_env(ENV_FILE)
    key = os.environ.get('GRAPH_API_KEY') or env.get('GRAPH_API_KEY')
    if not key:
        sys.exit('set GRAPH_API_KEY in .env: an API key from Subgraph Studio')

    updates = {}
    for chain in split(env.get('TICK_CHAINS', '')):
        chain = chain.lower()
        name = f'TICK_POOLS_{chain.upper()}'
        current = split(env.get(name, ''))
        listed = {entry.split(':')[0].lower() for entry in current}
        print(chain)
        added = find(chain, env, key, listed, args.min_usdc)
        if added:
            updates[name] = ','.join(current + added)
        print(f'  {len(added)} added, {len(current) + len(added)} pools in {name}')

    if not updates:
        print('nothing to add; .env not changed')
    elif args.dry_run:
        print('dry run; .env not changed')
    else:
        write_env(ENV_FILE, updates)
        print('.env updated; restart relay.py to stream the new pools')


if __name__ == '__main__':
    main()
