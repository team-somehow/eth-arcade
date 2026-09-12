"""On-chain prices: every swap in every watched ETH/USDC pool, block by block.

The shape of it
---------------

    The Graph  ->  substreams run (one per chain)  ->  relay.py  ->  your game
                   JSON lines on stdout             HTTP ndjson    PriceTick

The relay runs on a laptop or a server, because the Substreams key must not
live on a handheld somebody can pick up. The device holds one long-lived HTTP
connection to `GET /stream` and reads newline-delimited JSON: one line per
block per chain. Each line looks like

    {"chain": "arbitrum", "@block": 21, "@data": {
        "blockNumber": 3103, "timestampMs": 1757000000000,
        "prices": [{"pool": "0x...", "price": 2500.1, "liquidity": 9.1e21}, ...]}}

Two classes here, at two altitudes:

* `PoolStream` -- the raw stream. Iterate `blocks()` and you get every pool's
  own price, per block, per chain. Use it for a dashboard, an arb bot, a
  logger: anything that wants more than one number.
* `SubstreamsFeed` -- a `Feed`. Combines those pools into a single price and
  hands your game `PriceTick`s. Use it to play.

Why one price out of many pools, and why *this* way
---------------------------------------------------

Weighted average by in-range liquidity, after discarding any pool too far from
the weighted median. A plain median is harder to push but pins the price to a
single pool -- usually the biggest, which can go a minute without a trade, so
the number stops moving. A plain average moves on every trade anywhere, but one
broken or pushed pool drags it. Outlier-trim first, then weight: a trade in any
pool moves the price by that pool's share, and a pool 0.5% away from the rest
is not a view of the market.

A pool that did not trade in a block is still *at* its last price, so every
block -- traded or not -- is a fresh reading. That is why a repeated price from
this feed is real information and is counted as a calm market, not skipped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import queue
import threading
import time
import urllib.request

from ..ticks import ASSETS, PriceTick
from .base import BaseFeed
from .coinbase import USER_AGENT, _drain, _offer


@dataclass(frozen=True)
class PoolPrice:
    pool: str
    price: float
    liquidity: float


@dataclass(frozen=True)
class Block:
    """One block on one chain, as the stream reports it."""
    chain: str
    number: int
    time: float                       # unix seconds
    prices: list[PoolPrice] = field(default_factory=list)

    def age(self, wall_now: float) -> float:
        return max(0.0, wall_now - self.time)


def parse_block(line: str | bytes) -> Block | None:
    """One stream line to a Block, or None if the line is not one."""
    message = json.loads(line)
    data = message.get('@data') if isinstance(message, dict) else None
    if not isinstance(data, dict):
        return None
    prices = []
    for entry in data.get('prices', []):
        price, liquidity = float(entry['price']), float(entry['liquidity'])
        if math.isfinite(price) and price > 0 and math.isfinite(liquidity) and liquidity > 0:
            prices.append(PoolPrice(str(entry['pool']), price, liquidity))
    return Block(str(message.get('chain', '')), int(data['blockNumber']),
                 int(data['timestampMs']) / 1000, prices)


def weighted_median(points: list[tuple[float, float]]) -> float:
    """The value with half the weight on either side; points are (value, weight)."""
    points = sorted((value, weight) for value, weight in points if weight > 0)
    if not points:
        raise ValueError('No weighted points')
    half = sum(weight for _, weight in points) / 2
    running = 0.0
    for value, weight in points:
        running += weight
        if running >= half:
            return value
    return points[-1][0]


class PoolBook:
    """Latest price of every watched pool, across chains, as one number."""

    # Stop counting a chain's pools if its stream falls this far behind: their
    # last prices are then no longer that chain's current ones.
    CHAIN_STALE_AFTER = 10.0
    # A pool this far from the weighted median is broken or being pushed.
    # 0.5% is wider than any watched pool's fee.
    OUTLIER_BPS = 50

    def __init__(self) -> None:
        self.pools: dict[str, tuple[float, float]] = {}   # chain:pool -> price, liquidity
        self.heads: dict[str, tuple[int, float]] = {}     # chain -> block, block time

    def apply(self, line: str | bytes, wall_now: float) -> float | None:
        """Take one stream line; return its block time, or None to skip it."""
        block = parse_block(line)
        if block is None:
            return None
        if block.time > wall_now + 5:
            raise ValueError('Block from the future')
        # Already seen: a replay after reconnecting, or a duplicate.
        if block.number <= self.heads.get(block.chain, (-1, 0.0))[0]:
            return None
        self.heads[block.chain] = (block.number, block.time)
        for entry in block.prices:
            self.pools[f'{block.chain}:{entry.pool}'] = (entry.price, entry.liquidity)
        return block.time

    def live_pools(self, wall_now: float) -> list[tuple[float, float]]:
        return [value for key, value in self.pools.items()
                if wall_now - self.heads[key.split(':', 1)[0]][1] <= self.CHAIN_STALE_AFTER]

    def price(self, wall_now: float) -> float | None:
        live = self.live_pools(wall_now)
        if not live:
            return None
        middle = weighted_median(live)
        # Never empty: the pool at the median is always kept.
        kept = [(p, w) for p, w in live if abs(p / middle - 1) * 10_000 <= self.OUTLIER_BPS]
        return sum(p * w for p, w in kept) / sum(w for _, w in kept)


class PoolStream:
    """The raw relay stream, as an iterator of `Block`. No game loop needed.

        for block in PoolStream('http://localhost:8787').blocks():
            for p in block.prices:
                print(block.chain, p.pool[:8], p.price)

    Reconnects on its own; stops when you break out of the loop.
    """

    READ_TIMEOUT = 5.0

    def __init__(self, base_url: str = 'http://localhost:8787') -> None:
        self.url = base_url.rstrip('/') + '/stream'
        self.connected = False

    def blocks(self, reconnect: bool = True):
        retry = 1.0
        while True:
            try:
                request = urllib.request.Request(self.url, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(request, timeout=self.READ_TIMEOUT) as response:
                    self.connected = True
                    for line in response:
                        block = parse_block(line)
                        if block is not None:
                            yield block
                    retry = 1.0
            except (OSError, ValueError, KeyError, TypeError):
                pass
            self.connected = False
            if not reconnect:
                return
            time.sleep(retry)
            retry = min(10.0, retry * 2)


class SubstreamsFeed(BaseFeed):
    """One price out of many pools, as `PriceTick`s a game can settle on.

    Ticks carry the block's own time as their `source_age`, so the chain's
    delay counts against staleness exactly as it should: a relay that falls
    behind stops the betting instead of settling on old blocks.
    """

    name = 'SUBSTREAMS LIVE'
    # No block for this long means the relay or its stream is gone. Arbitrum
    # makes four blocks a second and Base one every two.
    READ_TIMEOUT = 5.0

    def __init__(self, base_url: str = 'http://localhost:8787') -> None:
        self.asset = ASSETS['eth']     # the module watches ETH pools only
        self.url = base_url.rstrip('/') + '/stream'
        self.status = 'Connecting to Substreams relay'
        self.pools = 0
        self.items: queue.Queue[PriceTick] = queue.Queue(maxsize=32)
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self._run, name='substreams-prices', daemon=True)
        self.worker.start()

    def _run(self) -> None:
        sequence = 0
        retry = 1.0
        while not self.stop.is_set():
            # A fresh book per connection: whatever the old one held is stale.
            book = PoolBook()
            try:
                request = urllib.request.Request(self.url, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(request, timeout=self.READ_TIMEOUT) as response:
                    self.status = 'Substreams / waiting for a block'
                    for line in response:
                        if self.stop.is_set():
                            return
                        wall_now = time.time()
                        block_time = book.apply(line, wall_now)
                        price = book.price(wall_now) if block_time is not None else None
                        if price is None:
                            continue
                        sequence += 1
                        _offer(self.items, PriceTick(price, sequence, time.monotonic(),
                                                     max(0.0, wall_now - block_time)))
                        self.pools = len(book.live_pools(wall_now))
                        self.status = f'Substreams ETH/USD / {self.pools} pools'
                        retry = 1.0
                self.status = 'Relay closed the stream / retrying'
            except (OSError, ValueError, KeyError, TypeError, queue.Full):
                self.status = 'Relay unavailable / retrying'
            self.stop.wait(retry)
            retry = min(10.0, retry * 2)

    def poll(self, _dt: float = 0.0, _now: float = 0.0) -> list[PriceTick]:
        return _drain(self.items)

    def close(self) -> None:
        self.stop.set()
        self.worker.join(timeout=0.1)
