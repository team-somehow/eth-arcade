"""BOX RUN rules: crank a box on the price ladder, buy the next 20 seconds.

The window clock never stops. A 20-second window is always running; when it
expires, whatever box you bought for it settles against the live price and the
next window starts in the same frame. The dial is always live — cranking moves
an aim cursor, and pressing A buys the next window at wherever the cursor sits.

The box is always the same size — a fixed slice of the price, about $1.41 wide
on $2,500 ETH for a ten-second window — so there is nothing to learn about it
and nothing that changes under you. Its one degree of freedom is how far from spot you park it, and that
distance is the whole risk decision. Only the *payout* reacts to the market,
priced from measured volatility of the live tick stream over the true remaining
horizon rather than a hardcoded table: the same box pays more when the market is
wild because it is genuinely harder to hit.

There is no size step, no confirmation, and no early exit: once bought, the box
rides to expiry, and the dial is locked out until the window rolls — only money
can still be added.

Each window records the price it opened at, so movement can be shown against a
reference that holds still instead of against a spot that moves with it.

Balances are integer micro-USDC (see wallet.py). Prices come from a feed; this
file never invents one.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import math
import statistics

from markets.feed import PriceTick
from wallet import MICRO, Wallet

# Fallback volatility until enough ticks have arrived to measure any: ~55%
# annualized, expressed as variance per second of relative return.
SECONDS_PER_YEAR = 31_536_000
DEFAULT_VARIANCE = (0.55 ** 2) / SECONDS_PER_YEAR


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def moved(before: float, after: float) -> bool:
    """A real price change, not float noise from re-averaging pools.

    A thousandth of a basis point: far below a one-cent Coinbase tick, far
    above what re-weighting unchanged pool prices can produce.
    """
    return abs(after - before) > before * 1e-7


@dataclass
class Order:
    """A bought box. `payout` is the total returned if it lands, stake included."""
    level: float          # box center, an absolute price
    half: float           # half-height in quote currency
    stake: int = 0        # micro-USDC in
    payout: float = 0.0   # micro-USDC out if the price lands inside

    @property
    def low(self) -> float:
        return self.level - self.half

    @property
    def high(self) -> float:
        return self.level + self.half

    @property
    def multiple(self) -> float:
        """Blended return multiple across every press that funded this box."""
        return self.payout / self.stake if self.stake else 0.0

    def contains(self, price: float) -> bool:
        # Boundary counts as inside.
        return self.low <= price <= self.high


@dataclass
class Result:
    """The outcome of one finished window."""
    hit: bool
    price: float
    stake: int
    payout: int
    multiple: float
    low: float = 0.0
    high: float = 0.0
    voided: bool = False

    @property
    def net(self) -> int:
        return self.payout - self.stake


class BoxModel:
    WINDOW_S = 10.0
    STAKE = 10 * MICRO       # micro-USDC added per press of A
    # Geometry in basis points of the window's opening price: constant, so the
    # box never changes size on screen or in dollars, and never rescales under
    # a bet that is already placed.
    #
    # These are quoted for a 20-second window and scaled by the square root of
    # time, because that is how far a price travels. Halving the window without
    # shrinking the box would make a box on spot a near-certainty paying 1.2x
    # and everything else a capped lottery ticket — a flatter game, not a
    # faster one. Scaled, any WINDOW_S keeps the same ladder of odds.
    REFERENCE_S = 20.0
    BOX_BPS = 8.0
    STEP_BPS = 1.0
    REACH_BPS = 12.0
    SCALE = (WINDOW_S / REFERENCE_S) ** 0.5
    # Half the visible price band. Exactly reach + half a box, so the cursor
    # can never be cranked out of view.
    VIEW_BPS = REACH_BPS + BOX_BPS / 2
    MAX_MULTIPLE = 25.0
    # Nothing is sold below this. A box quoting about 1.0x is one the model
    # thinks near-certain — on a line that has merely paused, it is — and a
    # certain win is not a bet anyone should be paid for.
    MIN_MULTIPLE = 1.05
    # A real venue must charge an edge and fund payouts from somewhere. This
    # demo quotes fair odds and says so rather than hiding a margin.
    HOUSE_EDGE = 0.0
    STALE_AFTER = 4.0
    # No expiry price within this long after the bell voids the window and
    # refunds the stake. Settling a real bet on the wrong minute's price, or on
    # a quote from before expiry, would be worse than not settling at all.
    VOID_AFTER = 4.0
    # Volatility is measured over this much wall time, not over a count of
    # ticks: a feed that sits still is a calm market and is priced as one.
    VOL_WINDOW_S = 60.0
    # The feed has been read once it has moved, with this many moves or this
    # much history behind it; before that nothing is sold. Short, because a
    # slow feed (the Coinbase ticker changes every few seconds) must not hold
    # the game up. It needs a move because a feed that has not moved yet
    # cannot be told apart from a dead one.
    MIN_MOVES = 10
    READ_S = 3.0
    # One move counts for at most this many median moves, so a flash spike or
    # a feed glitch cannot inflate the odds for the next minute.
    SPIKE_CAP = 4.0
    # Every estimate is made as if the window began with this many seconds of
    # ordinary ETH (DEFAULT_VARIANCE) ahead of what was actually seen.
    PRIOR_S = 10.0
    # No price change for this long and the market is asleep: a box on a line
    # that never moves is a certain win at any multiple over 1x, so nothing is
    # sold. Counted from the first tick while the price has never moved, so a
    # feed that merely pauses at start-up is not called asleep.
    QUIET_AFTER = 15.0

    def __init__(self, wallet: Wallet | None = None) -> None:
        self.wallet = wallet or Wallet()
        self.tick: PriceTick | None = None
        # Enough for VOL_WINDOW_S of the fastest feed (the sim, at 20 Hz).
        self.history: deque[tuple[float, float]] = deque(maxlen=2400)
        self.measured = False     # seen enough of the feed to price from it
        self.last_move_at = -math.inf  # when the price last actually changed
        self.aim = 0.0            # cursor level; 0 until the first price
        self.window_open = 0.0    # price this window started at; the chart anchor
        self.half = 0.0           # box half-height; constant within a window
        self.step = 0.0           # one detent, in price
        self.reach = 0.0          # how far the cursor may go from the anchor
        self.view_half = 0.0      # half the visible band, in price
        self._variance = 0.0      # cached; recomputed once per tick, not per read
        self.live: Order | None = None     # settles at window_end
        self.pending: Order | None = None  # bought for the window after that
        self.window_end = 0.0
        self.settling = False     # expired, waiting for a price to settle on
        self.started = False
        self.windows = 0          # bells rung; the game's heartbeat
        self.rounds = 0
        self.hits = 0
        self.last: Result | None = None

    # ---- state -----------------------------------------------------------
    @property
    def price(self) -> float:
        return self.tick.price if self.tick else 0.0

    def fresh(self, now: float) -> bool:
        return self.tick is not None and self.tick.age(now) <= self.STALE_AFTER

    def quiet(self, now: float) -> bool:
        """True when the price has sat on one value for QUIET_AFTER seconds."""
        return self.started and now - self.last_move_at >= self.QUIET_AFTER

    def remaining(self, now: float) -> float:
        return max(0.0, self.window_end - now)

    def can_buy(self) -> bool:
        return self.wallet.balance >= self.STAKE

    @property
    def locked(self) -> bool:
        """True once the next window is bought: position fixed, money still open."""
        return self.pending is not None

    def _set_geometry(self) -> None:
        """Size the box and the view from the window's opening price.

        Anchored to the open rather than to spot so nothing breathes tick by
        tick, and taken from the price rather than from volatility so a placed
        box is never redrawn at a different size than it was bought at.
        """
        base = self.window_open / 10_000 * self.SCALE
        self.half = base * self.BOX_BPS / 2
        self.step = base * self.STEP_BPS
        self.reach = base * self.REACH_BPS
        self.view_half = base * self.VIEW_BPS

    @property
    def inside(self) -> bool | None:
        """Is the price inside the live bet's box right now? None if no bet."""
        if self.live is None or not self.live.stake:
            return None
        return self.live.contains(self.price)

    @property
    def move(self) -> float:
        """How far the price has come since this window opened."""
        return self.price - self.window_open if self.started else 0.0

    @property
    def staked(self) -> int:
        """Money currently at risk across both windows."""
        return (self.live.stake if self.live else 0) + (self.pending.stake if self.pending else 0)

    # ---- volatility and pricing -----------------------------------------
    def variance_per_second(self) -> float:
        """Realized variance of the live tick stream, per second (cached).

        The renderer asks for this for every point it plots, so measuring here
        rather than caching would scan the whole tick history hundreds of times
        a frame — which the Pi cannot spare.
        """
        return self._variance or self._measure_variance()

    def _measure_variance(self) -> float:
        """Realized variance over the last minute of wall time, stillness included.

        Squared log returns, summed and divided by the time they span. Time
        spent on one price counts as exactly that: a pool nobody swapped in,
        or a ticker with no new trade, is a calm market — and the bell settles
        on that same price, so pricing it as a typical one sells a near-certain
        box at 2x. (This once skipped repeated prices and fell back to the
        default when it saw too few moves, which is precisely what a flat feed
        produces: parking a box on the line won 58 bets out of 58.)

        Each move is capped at SPIKE_CAP median moves, which keeps what a
        median estimator was for: one bad print cannot resize the odds.
        """
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
            self.measured = True      # and stays so: a later lull is calm, not unknown
        if not self.measured:
            return DEFAULT_VARIANCE
        total = 0.0
        if moves:
            cap = (self.SPIKE_CAP * statistics.median(abs(r) for r in moves)) ** 2
            total = sum(min(r * r, cap) for r in moves)
        # A few seconds of data, or a market just waking from a lull, is not
        # priced as if nothing could move; a minute of real data outweighs the
        # prior six to one.
        variance = (total + DEFAULT_VARIANCE * self.PRIOR_S) / (span + self.PRIOR_S)
        # Floor it: a feed that prints one price repeatedly must not collapse
        # the box to zero height or quote an infinite multiple.
        return max(variance, DEFAULT_VARIANCE / 20)

    def sigma(self, horizon: float) -> float:
        """One standard deviation of price movement over `horizon` seconds."""
        return self.price * math.sqrt(self.variance_per_second() * max(horizon, .001))

    def window_sigma(self) -> float:
        return self.sigma(self.WINDOW_S)

    def probability(self, level: float, half: float, horizon: float) -> float:
        """Chance the price sits inside the box when the window expires."""
        spread = self.sigma(horizon)
        if spread <= 0 or self.price <= 0:
            return 0.0
        low = normal_cdf((level - half - self.price) / spread)
        high = normal_cdf((level + half - self.price) / spread)
        return max(0.0, high - low)

    def quote(self, level: float, now: float, half: float | None = None) -> float:
        """Return multiple for a box bought right now, stake included.

        The horizon runs to the end of the window being bought, so buying early
        prices more drift than buying at the bell — a longer bet, not a free one.
        """
        horizon = self.remaining(now) + self.WINDOW_S
        chance = self.probability(level, self.half if half is None else half, horizon)
        if chance <= 0:
            return 0.0
        return min(self.MAX_MULTIPLE, (1 - self.HOUSE_EDGE) / chance)

    # ---- input -----------------------------------------------------------
    def crank(self, steps: int) -> bool:
        """Move the aim cursor. Returns False when there is nothing to move.

        A bought box cannot be repositioned, so the dial does nothing at all
        until the window rolls — no shrinking box, no second cursor.
        """
        if not steps or not self.started or self.locked:
            return False
        self.aim = self._in_reach(self.aim + steps * self.step)
        return True

    def _in_reach(self, level: float) -> float:
        return max(self.window_open - self.reach,
                   min(self.window_open + self.reach, level))

    def buy(self, now: float) -> bool:
        """Press A: put 10 USDC on the next window at the cursor.

        The first press fixes that window's level; later presses add stake at
        the odds available when they are made, so a box cannot be topped up at
        a stale multiple after the price walks toward it.
        """
        if (not self.started or not self.fresh(now) or self.settling
                or self.quiet(now) or not self.measured):
            return False
        level = self.aim if self.pending is None else self.pending.level
        half = self.half if self.pending is None else self.pending.half
        multiple = self.quote(level, now, half)
        if multiple < self.MIN_MULTIPLE or not self.wallet.debit(self.STAKE):
            return False
        if self.pending is None:
            self.pending = Order(level, half)
        self.pending.stake += self.STAKE
        self.pending.payout += self.STAKE * multiple
        return True

    # ---- time and prices -------------------------------------------------
    def on_tick(self, tick: PriceTick, now: float) -> None:
        if not math.isfinite(tick.price) or tick.price <= 0:
            return
        if not math.isfinite(tick.source_age) or tick.source_age < 0:
            return
        if self.tick is not None and tick.sequence <= self.tick.sequence:
            return
        if tick.age(now) > self.STALE_AFTER:
            return
        if self.tick is None or moved(self.tick.price, tick.price):
            self.last_move_at = tick.received_at
        self.tick = tick
        self.history.append((tick.received_at, tick.price))
        self._variance = self._measure_variance()
        if not self.started:
            self.started = True
            self.aim = self.window_open = tick.price
            self._set_geometry()
            self.window_end = now + self.WINDOW_S
        self.update(now)

    def settleable(self) -> bool:
        """True once a price stamped at or after the bell has arrived.

        A quote from before expiry is not an expiry price, however fresh it
        looks, so it cannot settle the window.
        """
        return self.tick is not None and self.tick.received_at >= self.window_end

    def update(self, now: float) -> None:
        """Roll the window clock. Safe to call every frame; time-driven only."""
        if not self.started:
            return
        while now >= self.window_end:
            order = self.live
            if order is not None and order.stake:
                if not self.settleable() or not self.fresh(now):
                    if now - self.window_end <= self.VOID_AFTER:
                        self.settling = True
                        return
                    self._void(order)
                else:
                    self._settle(order)
            self.settling = False
            self.live = self.pending
            self.pending = None
            self.windows += 1
            self.window_end += self.WINDOW_S
            # The new window opens here, and the cursor — free again — is
            # pulled back into reach of the new anchor.
            self.window_open = self.price
            self._set_geometry()
            self.aim = self._in_reach(self.aim)

    def _settle(self, order: Order) -> None:
        hit = order.contains(self.price)
        # Truncate to micro-USDC so a payout never rounds up into money the
        # book did not owe.
        payout = int(order.payout) if hit else 0
        self.wallet.credit(payout)
        self.rounds += 1
        self.hits += 1 if hit else 0
        self.last = Result(hit, self.price, order.stake, payout, order.multiple,
                           order.low, order.high)

    def _void(self, order: Order) -> None:
        """No usable expiry price: return the stake, record nothing as won."""
        self.wallet.credit(order.stake)
        self.rounds += 1
        self.last = Result(False, self.price, order.stake, order.stake,
                           order.multiple, order.low, order.high, voided=True)
