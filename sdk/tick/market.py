"""The feed, plus everything a game needs to know about it before betting.

A raw feed hands you prices. A `Market` answers the four questions that decide
whether a bet may be sold at all:

    market.fresh(now)    is the last price recent enough to settle money on?
    market.ready         has the feed moved enough to measure anything yet?
    market.quiet(now)    has it stopped moving, so every bet is a certainty?
    market.variance      how much is it actually moving, right now?

and one question that decides the price of the bet:

    market.probability(low, high, horizon)

Measuring volatility: read this before changing it
--------------------------------------------------

Realized variance over the last minute of **wall time** -- squared log returns
summed, divided by the seconds they span. Three details, each of which fixed a
real exploit:

* **Stillness counts.** Time spent sitting on one price is counted as exactly
  that. A pool nobody swapped in is a calm market, and the bell settles on that
  same price. An earlier version skipped repeated prices and fell back to
  "typical ETH" when it saw too few moves -- which is precisely what a flat feed
  produces -- and a box parked on the line won 58 bets out of 58.
* **One print cannot move the odds.** Each move is capped at `SPIKE_CAP` median
  moves, so a glitch or a flash spike cannot inflate payouts for a minute.
* **A prior, always.** Every estimate is made as if the window began with
  `PRIOR_S` seconds of ordinary movement, so the first seconds after boot, or a
  market waking from a lull, are not priced as if nothing could ever move. A
  full minute of real data outweighs the prior six to one.
"""
from __future__ import annotations

from collections import deque
import math
import statistics
import time

from .feeds import BaseFeed, open_feed
from .pricing import DEFAULT_VARIANCE, multiple, probability, sigma
from .ticks import PriceTick


def moved(before: float, after: float) -> bool:
    """A real price change, not float noise from re-averaging pools.

    A thousandth of a basis point: far below a one-cent tick, far above what
    re-weighting unchanged pool prices can produce.
    """
    return abs(after - before) > before * 1e-7


class Market:
    STALE_AFTER = 4.0        # a tick older than this cannot price or settle
    VOL_WINDOW_S = 60.0      # volatility is measured over this much wall time
    MIN_MOVES = 10           # ... and is trusted after this many moves
    READ_S = 3.0             # ... or this much history, whichever comes first
    SPIKE_CAP = 4.0          # one move counts for at most this many median moves
    PRIOR_S = 10.0           # seconds of "ordinary market" folded into every estimate
    QUIET_AFTER = 15.0       # no movement for this long and nothing is sold
    HISTORY = 2400           # enough for VOL_WINDOW_S of the fastest feed (20 Hz)

    def __init__(self, feed: BaseFeed | None = None, source: str | None = None,
                 seed: int | None = None, **kwargs) -> None:
        self.feed = feed if feed is not None else open_feed(source, seed, **kwargs)
        self.asset = getattr(self.feed, 'asset', None)
        self.tick: PriceTick | None = None
        self.history: deque[tuple[float, float]] = deque(maxlen=self.HISTORY)
        self.ready = False            # seen enough of the feed to price from it
        self.last_move_at = -math.inf
        self.started = False
        self._variance = 0.0

    # ---- reading it ------------------------------------------------------
    @property
    def price(self) -> float:
        return self.tick.price if self.tick else 0.0

    @property
    def name(self) -> str:
        return getattr(self.feed, 'name', 'FEED')

    @property
    def status(self) -> str:
        return getattr(self.feed, 'status', '')

    def fresh(self, now: float) -> bool:
        return self.tick is not None and self.tick.age(now) <= self.STALE_AFTER

    def quiet(self, now: float) -> bool:
        """True when the price has sat on one value for QUIET_AFTER seconds.

        Counted from the first tick while the price has never moved, so a feed
        that merely pauses at start-up is not called asleep.
        """
        return self.started and now - self.last_move_at >= self.QUIET_AFTER

    def sellable(self, now: float) -> bool:
        """The one call a game makes before taking money: may I sell a bet?"""
        return self.started and self.ready and self.fresh(now) and not self.quiet(now)

    def why_not(self, now: float) -> str:
        """Words for the screen when `sellable` is False. Empty when it is True."""
        if not self.started:
            return 'READING THE MARKET'
        if not self.fresh(now):
            return 'FEED STALE'
        # Checked before readiness: a feed running for a minute on one price is
        # asleep, not unread, and saying so is the more useful answer.
        if self.quiet(now):
            return 'MARKET QUIET / NO BETS'
        if not self.ready:
            return 'READING THE MARKET'
        return ''

    # ---- driving it ------------------------------------------------------
    def poll(self, dt: float, now: float | None = None) -> list[PriceTick]:
        """Read the feed and fold every tick in. Call once per frame."""
        now = time.monotonic() if now is None else now
        accepted = []
        for tick in self.feed.poll(dt, now):
            if self.accept(tick, now):
                accepted.append(tick)
        return accepted

    def accept(self, tick: PriceTick, now: float) -> bool:
        """Validate one tick and fold it in. False means it was rejected."""
        if not math.isfinite(tick.price) or tick.price <= 0:
            return False
        if not math.isfinite(tick.source_age) or tick.source_age < 0:
            return False
        if self.tick is not None and tick.sequence <= self.tick.sequence:
            return False              # duplicate or out of order
        if tick.age(now) > self.STALE_AFTER:
            return False              # born stale: it can price nothing
        if self.tick is None or moved(self.tick.price, tick.price):
            self.last_move_at = tick.received_at
        self.tick = tick
        self.started = True
        self.history.append((tick.received_at, tick.price))
        self._variance = self._measure()
        return True

    def close(self) -> None:
        self.feed.close()

    # ---- volatility ------------------------------------------------------
    @property
    def variance(self) -> float:
        """Realized variance per second (cached; recomputed once per tick).

        Cached because a renderer asks for this for every point it plots, and
        rescanning a minute of history hundreds of times a frame is time a Pi
        does not have.
        """
        return self._variance or self._measure()

    def _measure(self) -> float:
        points: list[tuple[float, float]] = []
        end = self.history[-1][0] if self.history else 0.0
        for t, p in reversed(self.history):
            if end - t > self.VOL_WINDOW_S:
                break
            points.append((t, p))
        points.reverse()
        moves = [math.log(p1 / p0) for (_, p0), (_, p1) in zip(points, points[1:])
                 if moved(p0, p1)]
        span = points[-1][0] - points[0][0] if points else 0.0
        if moves and (len(moves) >= self.MIN_MOVES or span >= self.READ_S):
            self.ready = True         # and stays so: a later lull is calm, not unknown
        if not self.ready:
            return DEFAULT_VARIANCE
        total = 0.0
        if moves:
            cap = (self.SPIKE_CAP * statistics.median(abs(r) for r in moves)) ** 2
            total = sum(min(r * r, cap) for r in moves)
        variance = (total + DEFAULT_VARIANCE * self.PRIOR_S) / (span + self.PRIOR_S)
        # Floor it: a feed printing one price must not quote an infinite multiple.
        return max(variance, DEFAULT_VARIANCE / 20)

    # ---- odds ------------------------------------------------------------
    def sigma(self, horizon: float) -> float:
        """One standard deviation of price movement over `horizon` seconds."""
        return sigma(self.price, self.variance, horizon)

    def probability(self, low: float, high: float, horizon: float) -> float:
        """Chance the price lands in [low, high] in `horizon` seconds."""
        return probability(self.price, low, high, self.variance, horizon)

    def quote(self, low: float, high: float, horizon: float,
              edge: float = 0.0, cap: float = 25.0) -> float:
        """Return multiple (stake included) for that range over that horizon."""
        return multiple(self.probability(low, high, horizon), edge, cap)

    def band(self, sigmas: float, horizon: float) -> float:
        """Half-width of a box that is `sigmas` standard deviations wide."""
        return sigmas * self.sigma(horizon)
