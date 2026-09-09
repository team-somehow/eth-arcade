"""Market adapters. Default is simulated; Coinbase is explicitly opt-in."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
import math
import queue
import random
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


class SimulatedFeed:
    name = 'SIMULATED'

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.price = 2500.0
        self.sequence = 0
        self.accumulated = 0.0
        self.status = 'Simulated ETH/USD'

    def poll(self, dt: float, now: float) -> list[PriceTick]:
        self.accumulated += max(0, dt)
        result = []
        while self.accumulated >= .05:
            self.accumulated -= .05
            self.sequence += 1
            # Demo volatility, NOT an estimate of real ETH market volatility.
            self.price *= math.exp(self.rng.gauss(0, .0012 * math.sqrt(.05)))
            result.append(PriceTick(self.price, self.sequence, now))
        return result

    def close(self):
        pass


def parse_coinbase(data: dict, now: float, wall_now: float) -> PriceTick:
    price = float(data['price'])
    sequence = int(data['trade_id'])
    timestamp = datetime.fromisoformat(data['time'].replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Missing timestamp timezone')
    source_time = timestamp.timestamp()
    if not math.isfinite(price) or price <= 0 or sequence < 0 or source_time > wall_now + 5:
        raise ValueError('Invalid market tick')
    return PriceTick(price, sequence, now, max(0, wall_now - source_time))


class CoinbaseFeed:
    """Public REST snapshot at ~1 Hz on a worker thread; no trading endpoints.

    Kept dependency-free for the Pi. A production low-latency execution adapter
    should use the selected venue's WebSocket/book/fill streams instead.
    """
    name = 'COINBASE LIVE'
    URL = 'https://api.exchange.coinbase.com/products/ETH-USD/ticker'

    def __init__(self):
        self.status = 'Connecting to Coinbase'
        self.items: queue.Queue[PriceTick] = queue.Queue(maxsize=32)
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self._run, name='coinbase-prices', daemon=True)
        self.worker.start()

    def _run(self):
        last_sequence = -1
        retry = 1.0
        while not self.stop.is_set():
            try:
                request = urllib.request.Request(self.URL, headers={'User-Agent': 'TICK-Hackathon/0.1'})
                with urllib.request.urlopen(request, timeout=3) as response:
                    data = json.load(response)
                tick = parse_coinbase(data, time.monotonic(), time.time())
                if tick.sequence > last_sequence:
                    if self.items.full():
                        try:
                            self.items.get_nowait()
                        except queue.Empty:
                            pass
                    self.items.put_nowait(tick)
                    last_sequence = tick.sequence
                self.status = 'Coinbase ETH/USD / 1 Hz'
                retry = 1.0
            except (OSError, ValueError, KeyError, TypeError, queue.Full):
                self.status = 'Feed unavailable / retrying'
                retry = min(10, retry * 2)
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
