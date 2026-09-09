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
    # Tick spacing, held in integer microseconds so the same wall-clock time
    # yields the same ticks at any frame rate (float seconds drift and drop one).
    INTERVAL_US = 50_000

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.price = 2500.0
        self.sequence = 0
        self.accumulated_us = 0
        self.status = 'Simulated ETH/USD'

    def poll(self, dt: float, now: float) -> list[PriceTick]:
        self.accumulated_us += int(max(0, dt) * 1_000_000)
        step = self.INTERVAL_US / 1_000_000
        result = []
        while self.accumulated_us >= self.INTERVAL_US:
            self.accumulated_us -= self.INTERVAL_US
            self.sequence += 1
            # Demo volatility, NOT an estimate of real ETH market volatility.
            self.price *= math.exp(self.rng.gauss(0, .0012 * math.sqrt(step)))
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
    """Public REST ticker on a worker thread; read-only, no trading endpoints.

    Polled at 5 Hz: a 20-second window needs a trace, not a staircase, and this
    stays well inside the public rate limit. Kept dependency-free for the Pi. A
    production adapter should use the venue's WebSocket trade stream instead.
    """
    name = 'COINBASE LIVE'
    URL = 'https://api.exchange.coinbase.com/products/ETH-USD/ticker'
    INTERVAL = 0.2

    def __init__(self):
        self.status = 'Connecting to Coinbase'
        self.items: queue.Queue[PriceTick] = queue.Queue(maxsize=32)
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self._run, name='coinbase-prices', daemon=True)
        self.worker.start()

    def _run(self):
        last_sequence = -1
        retry = self.INTERVAL
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
                self.status = 'Coinbase ETH/USD / 5 Hz'
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
