"""RUSH rules: one continuous crank drives an entire leveraged ride.

There is no aim step, no size step and no confirmation screen. Turning the
dial *is* the bet: the first couple of detents open a position in the direction
you turned, and after that every detent pumps a flywheel whose level is the
leverage. Stop turning and the flywheel bleeds down; let it die and the ride
closes itself. Rides settle back to `ready`, so cranking straight through the
result opens the next one.

Prices come from a market feed (simulated or live); this file never invents
one. Balances live in the wallet as integer micro-USDC.
"""
from __future__ import annotations
from collections import deque
import math

from markets.feed import PriceTick
from wallet import MICRO, Wallet, to_micro


class RushModel:
    STAKE = 10 * MICRO           # micro-USDC risked per ride
    MAX_LEVERAGE = 10.0
    # Detents needed to open a ride. Two keeps a brushed dial from staking,
    # and is still under a tenth of a second of real cranking.
    ARM_STEPS = 2
    ARM_WINDOW = 0.6
    PUMP_PER_STEP = 0.13
    THROTTLE_DECAY = 0.55        # per second, once the hand stops
    COAST_S = 1.6                # silence this long closes the ride
    STALE_AFTER = 4.0            # a quote older than this cannot price anything

    def __init__(self, wallet: Wallet | None = None) -> None:
        self.wallet = wallet or Wallet()
        self.phase = 'ready'
        self.side = 1
        self.tick: PriceTick | None = None
        self.history: deque[float] = deque(maxlen=240)
        self.throttle = 0.0
        self.leverage = 0.0
        self.units = 0.0         # signed position size, in the quoted asset
        self.stake = 0.0         # this ride's stake, in whole USDC
        self.pnl = 0.0
        self.arm = 0
        self.arm_at = 0.0
        self.last_pump = 0.0
        self.started_at = 0.0
        self.elapsed = 0.0
        self.peak_leverage = 0.0
        self.rides = 0
        self.last_pnl: float | None = None
        self.last_reason = ''
        self.last_peak = 0.0

    # ---- state -----------------------------------------------------------
    @property
    def active(self) -> bool:
        return self.phase in ('riding', 'exit_pending')

    @property
    def equity(self) -> float:
        """Whole USDC still backing the position; 0 means liquidated."""
        return max(0.0, self.stake + self.pnl)

    @property
    def target_leverage(self) -> float:
        return 1 + self.throttle * (self.MAX_LEVERAGE - 1)

    @property
    def arm_progress(self) -> float:
        return min(1.0, self.arm / self.ARM_STEPS)

    def fresh(self, now: float) -> bool:
        return self.tick is not None and self.tick.age(now) <= self.STALE_AFTER

    def can_ride(self) -> bool:
        return self.wallet.balance >= self.STAKE

    # ---- the one input ---------------------------------------------------
    def crank(self, steps: int, now: float) -> bool:
        """Feed this frame's signed detent count. Returns True if a ride opened.

        Direction only matters before a ride opens; once riding, motion either
        way keeps the flywheel alive, because the hand never reverses mid-rush.
        """
        if steps == 0:
            return False
        if self.phase == 'riding':
            if self.fresh(now):
                self.throttle = min(1.0, self.throttle + self.PUMP_PER_STEP * abs(steps))
                self.last_pump = now
            return False
        if self.phase != 'ready':
            return False

        side = 1 if steps > 0 else -1
        # A reversal is a change of mind, not progress toward the same ride.
        if side != self.side or now - self.arm_at > self.ARM_WINDOW:
            self.arm = 0
        self.side = side
        self.arm_at = now
        self.arm += abs(steps)
        if self.arm < self.ARM_STEPS:
            return False
        return self._open(now)

    def _open(self, now: float) -> bool:
        if not self.fresh(now) or not self.wallet.debit(self.STAKE):
            # Keep the charge: a hand still turning opens on the next quote.
            return False
        self.arm = 0
        self.phase = 'riding'
        self.stake = self.STAKE / MICRO
        self.pnl = 0.0
        # Open at 1x: the flywheel is empty until the hand keeps going.
        self.throttle = 0.0
        self.leverage = self.peak_leverage = 1.0
        self.units = self.side * self.stake / self.tick.price
        self.last_pump = self.started_at = now
        self.elapsed = 0.0
        return True

    def bail(self, now: float, reason: str = 'Bailed out') -> None:
        """Red button. Closes at the next usable quote, never at a stale one."""
        if not self.active:
            return
        self.last_reason = reason
        if self.fresh(now):
            self._settle(reason)
        else:
            self.phase = 'exit_pending'
            self.throttle = 0.0

    # ---- time and prices -------------------------------------------------
    def update(self, dt: float, now: float) -> None:
        if not self.active:
            self.throttle = 0.0
            if self.arm and now - self.arm_at > self.ARM_WINDOW:
                self.arm = 0
            return
        self.elapsed = max(0.0, now - self.started_at)
        self.throttle = max(0.0, self.throttle - max(0.0, dt) * self.THROTTLE_DECAY)
        if self.phase == 'riding':
            if not self.fresh(now):
                self.bail(now, 'Feed interrupted')
            elif now - self.last_pump >= self.COAST_S:
                self.bail(now, 'Crank stopped')

    def on_tick(self, tick: PriceTick, now: float) -> None:
        if not math.isfinite(tick.price) or tick.price <= 0:
            return
        if not math.isfinite(tick.source_age) or tick.source_age < 0:
            return
        if self.tick is not None and tick.sequence <= self.tick.sequence:
            return
        if tick.age(now) > self.STALE_AFTER:
            return
        previous = self.tick
        self.tick = tick
        self.history.append(tick.price)
        if not self.active or previous is None:
            return
        # Mark the quantity held *before* this move, then reprice. Cranking
        # must never retroactively multiply a gain that is already banked.
        self.pnl += self.units * (tick.price - previous.price)
        self.pnl = max(-self.stake, self.pnl)
        if self.equity <= 0:
            self._settle('Liquidated')
        elif self.phase == 'exit_pending':
            self._settle(self.last_reason)
        else:
            self.leverage = self.target_leverage
            self.peak_leverage = max(self.peak_leverage, self.leverage)
            self.units = self.side * self.equity * self.leverage / tick.price

    def _settle(self, reason: str) -> None:
        if not self.active:
            return
        # Truncate to micro-USDC: sub-micro dust is dropped, never rounded up
        # into money the ride did not make.
        self.wallet.credit(max(0, to_micro(self.equity)))
        self.last_pnl = self.pnl
        self.last_reason = reason
        self.last_peak = self.peak_leverage
        self.rides += 1
        self.units = self.leverage = self.throttle = 0.0
        self.stake = 0.0
        self.arm = 0
        self.phase = 'ready'
