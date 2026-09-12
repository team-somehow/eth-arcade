"""Every watched pool, block by block, straight off the on-chain stream.

    python examples/pools.py [relay-url]

One line per block per chain, then one per pool that priced in it. This is the
raw material the combined price is made of: use it for a dashboard, a spread
monitor, or a game that plays two venues against each other rather than
flattening them into one number.

Needs the relay running (see docs/prices-substreams.md).
"""
import sys
import time

from tick import PoolStream
from tick.feeds import PoolBook

url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8787'
stream = PoolStream(url)
book = PoolBook()

print(f'reading {stream.url} -- ctrl-c to stop')
try:
    for block in stream.blocks():
        now = time.time()
        for pool in block.prices:
            book.pools[f'{block.chain}:{pool.pool}'] = (pool.price, pool.liquidity)
        book.heads[block.chain] = (block.number, block.time)
        combined = book.price(now)
        print(f'{block.chain:<10} {block.number:<12} {block.age(now):4.1f}s old  '
              f'{len(block.prices)} pools   combined {combined:,.4f}'
              if combined else f'{block.chain} {block.number}: no price yet')
        for pool in block.prices:
            drift = (pool.price / combined - 1) * 10_000 if combined else 0
            print(f'    {pool.pool[:10]}...  {pool.price:>12,.4f}  '
                  f'{drift:+6.1f} bps from mid   liq {pool.liquidity:.3e}')
except KeyboardInterrupt:
    pass
