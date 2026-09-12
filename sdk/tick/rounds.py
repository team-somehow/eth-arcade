"""The clock that never stops.

A round is a fixed slice of time with a price at each end. Rounds follow each
other with no gap and no button: when one ends the next has already started, in
the same frame. There is no "ready?" screen, because a clock you can pause is a
clock you can wait out, and waiting out the market is not a game.

    round 7          round 8          round 9
    |----------------|----------------|----------------|
    open           bell/open        bell/open        bell
    2500.00        2500.41          2499.88

Each round records the price it **opened** at. Draw movement against that, not
against spot: anchoring a chart on spot re-centres it every tick, pins the
newest point to the middle of the screen, and makes a moving market look
perfectly still while the world slides around it.

Settling honestly
-----------------

A round settles on the price **at the bell**. A quote from *before* the bell
cannot settle it, however fresh it looks -- so the clock enters `settling` and
waits for a tick stamped at or after the bell. If none arrives within
`VOID_AFTER` seconds, the round is **voided** and every stake is refunded.
Settling real money against the wrong moment's price is worse than not settling
it at all.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Round:
    index: int
    open_price: float
    opened_at: float
    ends_at: float
    close_price: float = 0.0
    closed_at: float = 0.0
    voided: bool = False

    @property
    def move(self) -> float:
        """How far the price came across the round."""
        return self.close_price - self.open_price

    def remaining(self, now: float) -> float:
        return max(0.0, self.ends_at - now)

    def elapsed(self, now: float) -> float:
        return max(0.0, now - self.opened_at)

    def progress(self, now: float) -> float:
        span = self.ends_at - self.opened_at
        return 0.0 if span <= 0 else min(1.0, self.elapsed(now) / span)


class RoundClock:
    """Rolls rounds on wall time. Time-driven only: safe to call every frame."""

    VOID_AFTER = 4.0     # no usable bell price within this long and the round voids

    def __init__(self, window_s: float = 10.0, void_after: float | None = None) -> None:
        if window_s <= 0:
            raise ValueError('window_s must be above zero')
        self.window_s = float(window_s)
        self.VOID_AFTER = self.VOID_AFTER if void_after is None else void_after
        self.started = False
        self.settling = False
        self.index = 0
        self.open_price = 0.0
        self.opened_at = 0.0
        self.ends_at = 0.0
        self.current: Round | None = None
        self.closed: list[Round] = []        # every round that finished, newest last

    # ---- reading ---------------------------------------------------------
    def remaining(self, now: float) -> float:
        return max(0.0, self.ends_at - now)

    def elapsed(self, now: float) -> float:
        return max(0.0, now - self.opened_at)

    def progress(self, now: float) -> float:
        return 0.0 if not self.started else min(1.0, self.elapsed(now) / self.window_s)

    def bell_at(self, rounds_ahead: int = 0) -> float:
        """When the round `rounds_ahead` from now rings."""
        return self.ends_at + rounds_ahead * self.window_s

    def horizon(self, now: float, rounds_ahead: int = 0) -> float:
        """Seconds from now to that bell -- the true horizon of a bet placed now.

        Buying a round early prices *more* drift, not less: a bet bought fifteen
        seconds before a ten-second round's bell is a twenty-five-second bet. A
        game that quotes the window length instead of this sells long bets at
        short-bet prices, and that is the whole loss.
        """
        return max(0.0, self.remaining(now) + rounds_ahead * self.window_s)

    def move(self, price: float) -> float:
        """How far the price has come since this round opened."""
        return price - self.open_price if self.started else 0.0

    # ---- driving ---------------------------------------------------------
    def start(self, price: float, now: float) -> Round:
        self.started = True
        self.index += 1
        self.open_price = price
        self.opened_at = now
        self.ends_at = now + self.window_s
        self.current = Round(self.index, price, now, self.ends_at)
        return self.current

    def update(self, now: float, price: float, settleable: bool = True) -> list[Round]:
        """Roll the clock. Returns the rounds that just closed, oldest first.

        `settleable` is the caller's answer to "do you have a price stamped at
        or after the bell, and is it fresh?". False holds the round in
        `settling` until it is True or the void deadline passes.
        """
        if not self.started:
            return []
        done: list[Round] = []
        while now >= self.ends_at:
            if not settleable:
                if now - self.ends_at <= self.VOID_AFTER:
                    self.settling = True
                    return done
                voided = True
            else:
                voided = False
            self.settling = False
            finished = self.current
            if finished is not None:
                finished.close_price = price
                finished.closed_at = now
                finished.voided = voided
                self.closed.append(finished)
                done.append(finished)
            # The next round opens at the bell price, in the same frame.
            self.index += 1
            self.open_price = price
            self.opened_at = self.ends_at
            self.ends_at += self.window_s
            self.current = Round(self.index, price, self.opened_at, self.ends_at)
        return done
