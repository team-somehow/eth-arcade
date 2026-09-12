"""The data layer with no game attached: prices in a terminal.

    python examples/ticker.py                    simulated
    python examples/ticker.py coinbase           live exchange
    python examples/ticker.py substreams         on-chain pools via the relay

Proof that the SDK is a data library first and a game engine second. There is
no pygame import anywhere in this file.
"""
import sys
import time

from tick import Market, open_feed
from tick.pricing import annualized

source = sys.argv[1] if len(sys.argv) > 1 else 'sim'
market = Market(feed=open_feed(source))

print(f'{market.name}: {market.status}')
print(f"{'time':>8}  {'price':>12}  {'age':>6}  {'vol':>7}  {'P(+-0.05%, 10s)':>16}")

last = time.monotonic()
try:
    while True:
        now = time.monotonic()
        for tick in market.poll(now - last, now):
            band = market.price * 0.0005
            chance = market.probability(market.price - band, market.price + band, 10.0)
            print(f'{time.strftime("%H:%M:%S"):>8}  {tick.price:>12,.4f}  '
                  f'{tick.age(now):>5.1f}s  {annualized(market.variance):>6.1%}  '
                  f'{chance:>15.1%}'
                  f'{"" if market.ready else "   (still reading)"}', flush=True)
        last = now
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    market.close()
