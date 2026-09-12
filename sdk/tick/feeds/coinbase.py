"""Live trades from a public exchange, with no key and no account.

Read-only REST, polled at 5 Hz on a worker thread. Kept dependency-free (no
requests, no websockets) so it installs on a Pi with the stock Python.

Two decisions worth knowing, because both were bugs first:

* **Every successful poll is a tick, even one repeating the last trade.**
  ETH-USD can go seconds without a trade. Aging the price by its last *trade*
  made a quiet book look like a dead feed, and bets were refused as stale while
  the connection was perfectly fine.
* **A trade id older than one already seen is dropped, not replayed.** That is
  a lagging cache node, and honouring it walks the price backwards.

A production adapter should use the venue's WebSocket trade stream; this one
is here so a game is playable on real prices with zero setup.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
import queue
import re
import threading
import time
import urllib.request

from ..ticks import ASSETS, Asset, PriceTick
from .base import BaseFeed

USER_AGENT = 'tick-sdk/0.1'


def parse_coinbase(data: dict, now: float, wall_now: float) -> PriceTick:
    """Validate one ticker payload into a tick, or raise.

    Everything that reaches the pricing model is checked here: finite positive
    price, timezone-aware timestamp, no stamp from the future.
    """
    price = float(data['price'])
    sequence = int(data['trade_id'])
    # Coinbase stamps nanoseconds; fromisoformat takes at most six digits.
    stamp = re.sub(r'(\.\d{6})\d+', r'\1', data['time']).replace('Z', '+00:00')
    timestamp = datetime.fromisoformat(stamp)
    if timestamp.tzinfo is None:
        raise ValueError('Missing timestamp timezone')
    source_time = timestamp.timestamp()
    if not math.isfinite(price) or price <= 0 or sequence < 0 or source_time > wall_now + 5:
        raise ValueError('Invalid market tick')
    return PriceTick(price, sequence, now, max(0.0, wall_now - source_time))


class CoinbaseFeed(BaseFeed):
    name = 'COINBASE LIVE'
    URL = 'https://api.exchange.coinbase.com/products/{product}/ticker'
    INTERVAL = 0.2
    CACHE_S = 1.0    # the ticker answers with cache-control max-age=1

    def __init__(self, asset: Asset = ASSETS['eth']) -> None:
        self.asset = asset
        self.url = self.URL.format(product=asset.coinbase)
        self.status = 'Connecting to Coinbase'
        self.items: queue.Queue[PriceTick] = queue.Queue(maxsize=32)
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self._run, name='coinbase-prices', daemon=True)
        self.worker.start()

    def _run(self) -> None:
        last_trade = -1
        sequence = 0
        retry = self.INTERVAL
        while not self.stop.is_set():
            try:
                request = urllib.request.Request(self.url, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(request, timeout=3) as response:
                    data = json.load(response)
                tick = parse_coinbase(data, time.monotonic(), time.time())
                if tick.sequence >= last_trade:
                    last_trade = tick.sequence
                    sequence += 1
                    tick = replace(tick, sequence=sequence,
                                   source_age=min(tick.source_age, self.CACHE_S))
                    _offer(self.items, tick)
                self.status = f'Coinbase {self.asset.symbol}/USD / 5 Hz'
                retry = self.INTERVAL
            except (OSError, ValueError, KeyError, TypeError, queue.Full):
                self.status = 'Feed unavailable / retrying'
                retry = min(10.0, max(1.0, retry * 2))    # never hammer a dead network
            self.stop.wait(retry)

    def poll(self, _dt: float = 0.0, _now: float = 0.0) -> list[PriceTick]:
        return _drain(self.items)

    def close(self) -> None:
        self.stop.set()
        self.worker.join(timeout=0.1)


def _offer(items: 'queue.Queue[PriceTick]', tick: PriceTick) -> None:
    """Put a tick on a full queue by dropping the oldest: news beats history."""
    if items.full():
        try:
            items.get_nowait()
        except queue.Empty:
            pass
    items.put_nowait(tick)


def _drain(items: 'queue.Queue[PriceTick]') -> list[PriceTick]:
    out: list[PriceTick] = []
    while True:
        try:
            out.append(items.get_nowait())
        except queue.Empty:
            return out
