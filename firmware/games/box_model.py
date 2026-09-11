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
# median(|X|) = 0.6745 sigma for a zero-mean normal, so this scales a median
# absolute return back to a standard deviation.
MEDIAN_TO_SIGMA = 1.4826


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


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
    # A real venue must charge an edge and fund payouts from somewhere. This
    # demo quotes fair odds and says so rather than hiding a margin.
    HOUSE_EDGE = 0.0
    STALE_AFTER = 4.0
    # No expiry price within this long after the bell voids the window and
    # refunds the stake. Settling a real bet on the wrong minute's price, or on
    # a quote from before expiry, would be worse than not settling at all.
    VOID_AFTER = 4.0

    def __init__(self, wallet: Wallet | None = None) -> None:
        self.wallet = wallet or Wallet()
        self.tick: PriceTick | None = None
        self.history: deque[tuple[float, float]] = deque(maxlen=400)
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
        """Median-based, so one bad print cannot resize the game.

        A mean of squared returns would let a single flash spike (or a feed
        glitch) inflate the box for the next several windows. The median of
        per-second absolute returns ignores an outlier tick entirely.

        Only moves count, measured from the previous move. A feed that repeats
        its price between trades — every block of an on-chain feed without a
        swap — would otherwise fill the median with zeros and read as calm.
        """
        points = list(self.history)
        if len(points) < 20:
            return DEFAULT_VARIANCE
        rates = []
        t0, p0 = points[0]
        for t1, p1 in points[1:]:
            if p1 == p0:
                continue
            gap = t1 - t0
            if gap > 0 and p0 > 0:
                rates.append(abs(p1 / p0 - 1) / math.sqrt(gap))
            t0, p0 = t1, p1
        if len(rates) < 10:
            return DEFAULT_VARIANCE
        sigma = MEDIAN_TO_SIGMA * statistics.median(rates)
        # Floor it: a feed that prints one price repeatedly must not collapse
        # the box to zero height or quote an infinite multiple.
        return max(sigma ** 2, DEFAULT_VARIANCE / 20)

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
        if not self.started or not self.fresh(now) or self.settling:
            return False
        level = self.aim if self.pending is None else self.pending.level
        half = self.half if self.pending is None else self.pending.half
        multiple = self.quote(level, now, half)
        if multiple <= 0 or not self.wallet.debit(self.STAKE):
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
