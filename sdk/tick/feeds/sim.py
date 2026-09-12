"""A believable market with no network: the feed you develop against.

Geometric Brownian motion at the coin's real volatility, seeded so the same
seed replays the same market exactly. That is what makes a test of your odds
a test and not a coin flip.

Tick spacing is held in **integer microseconds**, and each frame's delta is
rounded into that accumulator rather than truncated. Accumulating float seconds
drifts, and truncating 1/60 of a second loses two thirds of a microsecond every
frame -- enough that the same ten seconds of wall clock yields 200 ticks at one
frame rate and 199 at another, which would make your volatility estimate depend
on the frame rate.
"""
from __future__ import annotations

import math
import random

from ..ticks import ASSETS, Asset, PriceTick
from .base import BaseFeed


class SimulatedFeed(BaseFeed):
    name = 'SIMULATED'
    INTERVAL_US = 50_000     # 20 Hz

    def __init__(self, seed: int | None = None, asset: Asset = ASSETS['eth'],
                 volatility: float | None = None) -> None:
        self.rng = random.Random(seed)
        self.asset = asset
        self.price = asset.start
        self.sigma = asset.sigma if volatility is None else volatility
        self.sequence = 0
        self.accumulated_us = 0
        self.status = f'Simulated {asset.symbol}/USD'

    def poll(self, dt: float, now: float) -> list[PriceTick]:
        self.accumulated_us += int(round(max(0.0, dt) * 1_000_000))
        step = self.INTERVAL_US / 1_000_000
        out: list[PriceTick] = []
        while self.accumulated_us >= self.INTERVAL_US:
            self.accumulated_us -= self.INTERVAL_US
            self.sequence += 1
            self.price *= math.exp(self.rng.gauss(0, self.sigma * math.sqrt(step)))
            out.append(PriceTick(self.price, self.sequence, now))
        return out

    def close(self) -> None:
        pass


class FrozenFeed(BaseFeed):
    """A feed that never moves. For testing that your game refuses to sell
    a certain win -- a flat line means a box on spot wins every time."""

    name = 'FROZEN'

    def __init__(self, price: float = 2500.0, asset: Asset = ASSETS['eth']) -> None:
        self.asset = asset
        self.price = price
        self.sequence = 0
        self.accumulated_us = 0
        self.status = 'Frozen'

    def poll(self, dt: float, now: float) -> list[PriceTick]:
        self.accumulated_us += int(round(max(0.0, dt) * 1_000_000))
        out: list[PriceTick] = []
        while self.accumulated_us >= 50_000:
            self.accumulated_us -= 50_000
            self.sequence += 1
            out.append(PriceTick(self.price, self.sequence, now))
        return out

    def close(self) -> None:
        pass
