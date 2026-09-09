"""BOX RUN practice rules. No networking, real prices, or real-money settlement."""

from __future__ import annotations

import math
import random


class BoxRunModel:
    DURATION = 20.0
    TICK = 0.1
    TICKS = 200
    STEP_SIGMA = 0.7
    STAKE = 10

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.balance = 100
        self.rounds = 0
        self.hits = 0
        self.reset_prediction()

    def reset_prediction(self) -> None:
        """Start setup without changing the practice balance."""
        self.phase = "aim" if self.balance >= self.STAKE else "empty"
        self.center = 0.0
        self.half_width = 7.0
        self.elapsed = 0.0
        self.path = [0.0]
        self.hit = False
        self.locked_center = 0.0
        self.locked_width = 7.0
        self.locked_return = 0

    @property
    def total_return(self) -> int:
        """Illustrative quote from the SAME Gaussian model used by simulation.

        Total includes the stake. Cap at 100 credits; never offer a real quote.
        There is no adaptive difficulty or outcome selection based on the box.
        """
        sigma = self.STEP_SIGMA * math.sqrt(self.TICKS)
        cdf = lambda x: (1 + math.erf(x / (sigma * math.sqrt(2)))) / 2
        probability = cdf(self.center + self.half_width) - cdf(self.center - self.half_width)
        return min(100, max(11, math.floor(self.STAKE / max(probability, 0.001))))

    @property
    def remaining(self) -> int:
        return max(0, math.ceil(self.DURATION - self.elapsed - 1e-8))

    @property
    def net(self) -> int:
        return (self.locked_return if self.hit else 0) - self.STAKE

    def adjust(self, direction: int) -> None:
        if self.phase == "aim":
            self.center = max(-22.0, min(22.0, self.center + direction))
        elif self.phase == "size":
            self.half_width = max(3.0, min(15.0, self.half_width + direction))

    def confirm(self) -> None:
        if self.phase == "aim":
            self.phase = "size"
        elif self.phase == "size":
            self.phase = "review"
        elif self.phase == "review" and self.balance >= self.STAKE:
            self.locked_center = self.center
            self.locked_width = self.half_width
            self.locked_return = self.total_return
            self.balance -= self.STAKE
            self.elapsed = 0.0
            self.path = [0.0]
            self.phase = "running"
        elif self.phase == "result":
            self.reset_prediction()
        elif self.phase == "empty":
            # An explicit refill only; no automatic restart or repeat stake.
            self.balance = 100
            self.reset_prediction()

    def back(self) -> bool:
        """True requests home. Committed rounds cannot be abandoned via B."""
        if self.phase == "size":
            self.phase = "aim"
        elif self.phase == "review":
            self.phase = "size"
        elif self.phase != "running":
            return True
        return False

    def update(self, dt: float) -> None:
        if self.phase != "running":
            return
        if not math.isfinite(dt) or dt < 0:
            return
        self.elapsed = min(self.DURATION, self.elapsed + dt)
        # Fixed simulation ticks make outcomes independent of display frame rate.
        required = min(self.TICKS, int((self.elapsed + 1e-8) / self.TICK))
        while len(self.path) <= required:
            self.path.append(self.path[-1] + self.rng.gauss(0.0, self.STEP_SIGMA))
        if self.elapsed >= self.DURATION - 1e-8:
            self.elapsed = self.DURATION
            self.hit = abs(self.path[-1] - self.locked_center) <= self.locked_width
            if self.hit:
                self.balance += self.locked_return
                self.hits += 1
            self.rounds += 1
            self.phase = "result"
