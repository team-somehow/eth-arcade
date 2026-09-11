"""Market adapters. Default is simulated; live sources are explicitly opt-in."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime
import json
import math
import os
import queue
import random
import re
import threading
import time
import urllib.request


@dataclass(frozen=True)
class PriceTick:
    price: float
    sequence: int
    received_at: float
    source_age: float = 0.0

    def age(self, now: float) -> float:
        return max(0, now - self.received_at) + self.source_age


@dataclass(frozen=True)
class Asset:
    symbol: str
    coinbase: str    # Coinbase product id
    start: float     # simulated feed's opening price
    sigma: float     # simulated volatility per square-root second
    places: int = 2  # decimals shown on screen; a sub-dollar coin needs more

    def format(self, price: float, sign: bool = False) -> str:
        return f'{price:{"+" if sign else ""},.{self.places}f}'


# Volatility per square-root second, set to roughly each coin live: for ETH
# about 0.04% over 20 seconds, or a dollar on $2,500. Testing against a feed an
# order of magnitude wilder than the real one teaches the wrong thing.
ASSETS = {
    'eth': Asset('ETH', 'ETH-USD', 2500.0, 0.00009),
    'btc': Asset('BTC', 'BTC-USD', 77_000.0, 0.00007),
    'sol': Asset('SOL', 'SOL-USD', 100.0, 0.00013),
    'hbar': Asset('HBAR', 'HBAR-USD', 0.075, 0.00015, places=5),
}


def current_asset() -> Asset:
    """The coin named by TICK_ASSET, ETH by default."""
    key = os.environ.get('TICK_ASSET', 'eth').strip().lower()
    if key not in ASSETS:
        raise ValueError(f"TICK_ASSET must be one of {', '.join(ASSETS)}")
    return ASSETS[key]


class SimulatedFeed:
    name = 'SIMULATED'
    # Tick spacing, held in integer microseconds so the same wall-clock time
    # yields the same ticks at any frame rate (float seconds drift and drop one).
    INTERVAL_US = 50_000
    SIGMA = ASSETS['eth'].sigma

    def __init__(self, seed: int | None = None, asset: Asset = ASSETS['eth']):
        self.rng = random.Random(seed)
        self.asset = asset
        self.price = asset.start
        self.sigma = asset.sigma
        self.sequence = 0
        self.accumulated_us = 0
        self.status = f'Simulated {asset.symbol}/USD'

    def poll(self, dt: float, now: float) -> list[PriceTick]:
        self.accumulated_us += int(max(0, dt) * 1_000_000)
        step = self.INTERVAL_US / 1_000_000
        result = []
        while self.accumulated_us >= self.INTERVAL_US:
            self.accumulated_us -= self.INTERVAL_US
            self.sequence += 1
            self.price *= math.exp(self.rng.gauss(0, self.sigma * math.sqrt(step)))
            result.append(PriceTick(self.price, self.sequence, now))
        return result

    def close(self):
        pass


def parse_coinbase(data: dict, now: float, wall_now: float) -> PriceTick:
    price = float(data['price'])
    sequence = int(data['trade_id'])
    # Coinbase stamps nanoseconds; Python before 3.11 takes at most six digits.
    stamp = re.sub(r'(\.\d{6})\d+', r'\1', data['time']).replace('Z', '+00:00')
    timestamp = datetime.fromisoformat(stamp)
    if timestamp.tzinfo is None:
        raise ValueError('Missing timestamp timezone')
    source_time = timestamp.timestamp()
    if not math.isfinite(price) or price <= 0 or sequence < 0 or source_time > wall_now + 5:
        raise ValueError('Invalid market tick')
    return PriceTick(price, sequence, now, max(0, wall_now - source_time))


class CoinbaseFeed:
    """Public REST ticker on a worker thread; read-only, no trading endpoints.

    Polled at 5 Hz: a 20-second window needs a trace, not a staircase, and this
    stays well inside the public rate limit. Kept dependency-free for the Pi. A
    production adapter should use the venue's WebSocket trade stream instead.

    Every answer is a tick, including one that repeats the last trade. ETH-USD
    can go several seconds without a trade, and aging the price by its last
    trade made a quiet book look like a dead feed: bets refused as stale while
    the connection was fine. A successful poll confirms the price as of the
    response, which the API caches for up to CACHE_S.
    """
    name = 'COINBASE LIVE'
    URL = 'https://api.exchange.coinbase.com/products/{product}/ticker'
    INTERVAL = 0.2
    CACHE_S = 1.0   # the ticker answers with cache-control max-age=1

    def __init__(self, asset: Asset = ASSETS['eth']):
        self.asset = asset
        self.url = self.URL.format(product=asset.coinbase)
        self.status = 'Connecting to Coinbase'
        self.items: queue.Queue[PriceTick] = queue.Queue(maxsize=32)
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self._run, name='coinbase-prices', daemon=True)
        self.worker.start()

    def _run(self):
        last_trade = -1
        sequence = 0
        retry = self.INTERVAL
        while not self.stop.is_set():
            try:
                request = urllib.request.Request(self.url, headers={'User-Agent': 'TICK-Hackathon/0.1'})
                with urllib.request.urlopen(request, timeout=3) as response:
                    data = json.load(response)
                tick = parse_coinbase(data, time.monotonic(), time.time())
                # An older trade than one already seen is a lagging cache node:
                # skip it rather than walk the price backwards. The same trade
                # again is still news — see the class docstring.
                if tick.sequence >= last_trade:
                    last_trade = tick.sequence
                    sequence += 1
                    tick = replace(tick, sequence=sequence,
                                   source_age=min(tick.source_age, self.CACHE_S))
                    if self.items.full():
                        try:
                            self.items.get_nowait()
                        except queue.Empty:
                            pass
                    self.items.put_nowait(tick)
                self.status = f'Coinbase {self.asset.symbol}/USD / 5 Hz'
                retry = self.INTERVAL
            except (OSError, ValueError, KeyError, TypeError, queue.Full):
                self.status = 'Feed unavailable / retrying'
                # Back off on failure so a dead network is not hammered.
                retry = min(10, max(1.0, retry * 2))
            self.stop.wait(retry)

    def poll(self, _dt: float, _now: float) -> list[PriceTick]:
        result = []
        while True:
            try:
                result.append(self.items.get_nowait())
            except queue.Empty:
                return result

    def close(self):
        self.stop.set()
        self.worker.join(timeout=.1)


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
    """Latest price of every watched pool, across chains, as one number.

    Fed the JSON lines of the tick_eth_price Substreams module (see
    substreams/), one per block per chain. A pool that did not trade in a block
    is still at its last price, so every block, traded or not, is a fresh
    reading.

    Pools are combined by an average weighted by in-range liquidity, so a
    trade in any pool moves the price by that pool's share. A median would be
    harder to push but pins the price to a single pool, usually the biggest,
    which can go a minute without a trade. Pushing is handled instead by
    leaving out any pool too far from the weighted median before averaging.
    """
    # Stop counting a chain's pools if its stream falls this far behind; their
    # last prices are then no longer the chain's current ones.
    CHAIN_STALE_AFTER = 10.0
    # A pool this far from the weighted median is broken or being pushed, not
    # a view of the market. 0.5% is wider than any watched pool's fee.
    OUTLIER_BPS = 50

    def __init__(self):
        self.pools: dict[str, tuple[float, float]] = {}  # chain:pool -> price, liquidity
        self.heads: dict[str, tuple[int, float]] = {}    # chain -> block, block time

    def apply(self, line: str | bytes, wall_now: float) -> float | None:
        """Take one stream line; return its block time, or None to skip it."""
        message = json.loads(line)
        data = message.get('@data') if isinstance(message, dict) else None
        if not isinstance(data, dict):
            return None
        chain = str(message.get('chain', ''))
        number = int(data['blockNumber'])
        block_time = int(data['timestampMs']) / 1000
        if block_time > wall_now + 5:
            raise ValueError('Block from the future')
        # Blocks already seen: a replay after reconnecting, or a duplicate.
        if number <= self.heads.get(chain, (-1, 0.0))[0]:
            return None
        self.heads[chain] = (number, block_time)
        for entry in data.get('prices', []):
            price, liquidity = float(entry['price']), float(entry['liquidity'])
            if math.isfinite(price) and price > 0 and math.isfinite(liquidity) and liquidity > 0:
                self.pools[f"{chain}:{entry['pool']}"] = (price, liquidity)
        return block_time

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


class SubstreamsFeed:
    """Uniswap v3 pool prices from The Graph's Substreams, via substreams/relay.py.

    The stream runs on a laptop or server and this reads it over one long-lived
    HTTP connection, so each block arrives as soon as it is out rather than on
    the next poll, and no Graph credentials live on the device. Ticks carry the
    block's own time as their source age, so the chain's delay counts against
    staleness exactly as it should.
    """
    name = 'SUBSTREAMS LIVE'
    # No block for this long means the relay or its stream is gone. Arbitrum
    # makes four a second and Base one every two.
    READ_TIMEOUT = 5.0

    def __init__(self, base_url: str):
        self.asset = ASSETS['eth']   # the Substreams module watches ETH pools only
        self.url = base_url.rstrip('/') + '/stream'
        self.status = 'Connecting to Substreams relay'
        self.items: queue.Queue[PriceTick] = queue.Queue(maxsize=32)
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self._run, name='substreams-prices', daemon=True)
        self.worker.start()

    def _run(self):
        sequence = 0
        retry = 1.0
        while not self.stop.is_set():
            # A fresh book per connection: whatever the old one held is stale.
            book = PoolBook()
            try:
                request = urllib.request.Request(self.url, headers={'User-Agent': 'TICK-Hackathon/0.1'})
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
                        tick = PriceTick(price, sequence, time.monotonic(), max(0, wall_now - block_time))
                        if self.items.full():
                            try:
                                self.items.get_nowait()
                            except queue.Empty:
                                pass
                        self.items.put_nowait(tick)
                        self.status = f'Substreams ETH/USD / {len(book.live_pools(wall_now))} pools'
                        retry = 1.0
                self.status = 'Relay closed the stream / retrying'
            except (OSError, ValueError, KeyError, TypeError, queue.Full):
                self.status = 'Relay unavailable / retrying'
            self.stop.wait(retry)
            retry = min(10, retry * 2)

    def poll(self, _dt: float, _now: float) -> list[PriceTick]:
        result = []
        while True:
            try:
                result.append(self.items.get_nowait())
            except queue.Empty:
                return result

    def close(self):
        self.stop.set()
        self.worker.join(timeout=.1)


SOURCES = ('sim', 'coinbase', 'substreams')


def open_feed(source: str, seed: int | None = None, asset: Asset | None = None):
    """The feed named by TICK_MARKET_SOURCE, for the coin named by TICK_ASSET."""
    asset = asset or current_asset()
    if source == 'coinbase':
        return CoinbaseFeed(asset)
    if source == 'substreams':
        if asset != ASSETS['eth']:
            raise ValueError('TICK_MARKET_SOURCE=substreams only prices ETH; use sim or coinbase')
        return SubstreamsFeed(os.environ.get('SUBSTREAMS_BASE_URL', 'http://localhost:8787'))
    if source == 'sim':
        return SimulatedFeed(seed, asset)
    raise ValueError(f"TICK_MARKET_SOURCE must be one of {', '.join(SOURCES)}")
