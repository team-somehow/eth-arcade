"""Continuous-crank paper trading. All balances are DUMMY USDC in memory."""
from __future__ import annotations
from collections import deque
import math
from markets.feed import PriceTick


class DummyWallet:
    """A local demo ledger, deliberately not a deposit address or real wallet."""
    def __init__(self, balance: float = 100):
        self.balance = balance
        self.deposits: list[float] = []

    def load(self, amount: float):
        if amount not in (10, 25, 100):
            raise ValueError('Unsupported demo load amount')
        self.balance += amount
        self.deposits.append(amount)


class RushModel:
    STAKE = 10.0
    MAX_LEVERAGE = 10.0
    STALE_AFTER = 4.0
    STOP_AFTER = 2.0

    def __init__(self, wallet: DummyWallet | None = None):
        self.wallet = wallet or DummyWallet()
        self.phase = 'ready'
        self.side = 1
        self.tick: PriceTick | None = None
        self.history: deque[float] = deque(maxlen=240)
        self.throttle = 0.0
        self.leverage = 0.0
        self.units = 0.0
        self.pnl = 0.0
        self.last_pnl: float | None = None
        self.last_reason = ''
        self.last_pump = 0.0
        self.started_at = 0.0
        self.elapsed = 0.0
        self.rides = 0
        self.peak_leverage = 0.0

    def fresh(self, now: float) -> bool:
        return self.tick is not None and self.tick.age(now) <= self.STALE_AFTER

    @property
    def equity(self) -> float:
        return max(0, self.STAKE + self.pnl)

    @property
    def target_leverage(self) -> float:
        return 1 + self.throttle * (self.MAX_LEVERAGE - 1)

    @property
    def active(self) -> bool:
        return self.phase in ('riding', 'exit_pending')

    def choose_side(self, side: int):
        if not self.active:
            self.side = 1 if side > 0 else -1

    def start(self, now: float) -> bool:
        if self.phase != 'ready' or not self.fresh(now) or self.wallet.balance < self.STAKE:
            return False
        self.wallet.balance -= self.STAKE
        self.phase = 'riding'
        self.pnl = 0.0
        self.throttle = 0.0
        self.leverage = 1.0
        self.peak_leverage = 1.0
        self.units = self.side * self.STAKE / self.tick.price
        self.last_pump = self.started_at = now
        self.elapsed = 0.0
        return True

    def crank(self, direction: int, now: float):
        if self.phase == 'ready':
            self.choose_side(direction)
        elif self.phase == 'riding' and self.fresh(now):
            if direction > 0:
                self.throttle = min(1.0, self.throttle + .13)
                self.last_pump = now
            else:
                self.throttle = max(0.0, self.throttle - .25)

    def update(self, dt: float, now: float):
        if not self.active:
            self.throttle = 0
            return
        self.elapsed = max(0, now - self.started_at)
        self.throttle = max(0.0, self.throttle - max(0, dt) * .55)
        if self.phase == 'riding' and (not self.fresh(now) or now - self.last_pump >= self.STOP_AFTER):
            self.request_exit(now, 'Feed interrupted' if not self.fresh(now) else 'Crank released')

    def on_tick(self, tick: PriceTick, now: float):
        if not math.isfinite(tick.price) or tick.price <= 0 or not math.isfinite(tick.source_age) or tick.source_age < 0:
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
        # Mark previous quantity BEFORE changing exposure. Never multiply prior
        # gains by a newly cranked leverage, and never invent money for spinning.
        self.pnl += self.units * (tick.price - previous.price)
        self.pnl = max(-self.STAKE, self.pnl)
        if self.equity <= 0:
            self._settle('Demo stake exhausted')
        elif self.phase == 'exit_pending':
            self._settle(self.last_reason)
        else:
            self.leverage = self.target_leverage
            self.peak_leverage = max(self.peak_leverage, self.leverage)
            self.units = self.side * self.equity * self.leverage / tick.price

    def request_exit(self, now: float, reason: str = 'Red button'):
        if not self.active:
            return
        self.last_reason = reason
        if self.fresh(now):
            self._settle(reason)
        else:
            # Never pretend a stale quote executed an exit. Mark the gap and
            # settle at the first fresh quote; no synthetic fallback price.
            self.phase = 'exit_pending'
            self.throttle = 0

    def _settle(self, reason: str):
        if not self.active:
            return
        self.wallet.balance += self.equity
        self.last_pnl = self.pnl
        self.last_reason = reason
        self.rides += 1
        self.units = self.leverage = self.throttle = 0
        self.phase = 'ready'
