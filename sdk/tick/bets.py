"""One bet type, because there is only one bet.

Every game on this device -- box on a ladder, over/under, coin flip, hi-lo --
is the same claim wearing different clothes:

    the price will be between LOW and HIGH when round N rings.

A coin flip is `(spot, +inf)`. An over/under is a one-sided range. A box is a
two-sided one. So the SDK has exactly one `Bet`, and your game's job is to
decide which range the player is pointing at and what it looks like on screen.

Topping up
----------

Pressing buy again on a bet already placed **adds stake at the odds available
at that moment**, not at the odds of the first press. If the price has walked
toward the box since, the second press is genuinely cheaper to win and must
cost accordingly. `payout` therefore accumulates per press, and `multiple` is
the blended return across every press that funded the bet. Charging the first
press's odds for the fifth is a free option, and players find free options.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class Bet:
    """A claim on a price range at a given round's bell.

    `payout` is the total returned if it lands, stake included.
    """
    round_index: int
    low: float
    high: float
    stake: int = 0
    payout: float = 0.0
    presses: int = 0
    label: str = ''

    @property
    def level(self) -> float:
        """Centre of the range. Infinite on a one-sided bet."""
        return (self.low + self.high) / 2

    @property
    def half(self) -> float:
        return (self.high - self.low) / 2

    @property
    def multiple(self) -> float:
        """Blended return multiple across every press that funded this bet."""
        return self.payout / self.stake if self.stake else 0.0

    def contains(self, price: float) -> bool:
        """Boundary counts as inside -- state it once, here, and never argue."""
        return self.low <= price <= self.high

    def add(self, stake: int, multiple: float) -> None:
        self.stake += stake
        self.payout += stake * multiple
        self.presses += 1


@dataclass(frozen=True)
class Settlement:
    """What one bet did when its round rang."""
    bet: Bet
    hit: bool
    price: float
    stake: int
    payout: int
    multiple: float
    voided: bool = False
    round_index: int = 0

    @property
    def net(self) -> int:
        return self.payout - self.stake

    @property
    def low(self) -> float:
        return self.bet.low

    @property
    def high(self) -> float:
        return self.bet.high


class BetBook:
    """Every bet not yet settled, and the rules for settling them.

    The book, not the game, moves money: `place` debits, `settle` credits.
    Keeping both on one object is what makes it impossible to pay out a bet
    that was never charged for.
    """

    def __init__(self, wallet) -> None:
        self.wallet = wallet
        self.open: list[Bet] = []
        self.history: list[Settlement] = []
        self.rounds = 0
        self.hits = 0

    # ---- placing ---------------------------------------------------------
    def find(self, round_index: int, low: float, high: float) -> Bet | None:
        for bet in self.open:
            if bet.round_index == round_index and bet.low == low and bet.high == high:
                return bet
        return None

    def for_round(self, round_index: int) -> list[Bet]:
        return [bet for bet in self.open if bet.round_index == round_index]

    def place(self, round_index: int, low: float, high: float,
              stake: int, multiple: float, label: str = '') -> Bet | None:
        """Debit `stake` and put it on that range for that round. None if refused.

        Refused when the wallet cannot cover it -- nothing else is decided here.
        Whether the *market* allows a bet at all is `market.sellable`, and
        whether the odds are worth selling is the game's floor: both are checked
        before this is called, so this stays a pure money operation.
        """
        if stake <= 0 or high < low or not math.isfinite(multiple) or multiple <= 0:
            return None
        if not self.wallet.debit(stake):
            return None
        bet = self.find(round_index, low, high)
        if bet is None:
            bet = Bet(round_index, low, high, label=label)
            self.open.append(bet)
        bet.add(stake, multiple)
        return bet

    def staked(self) -> int:
        """Money currently at risk across every open bet."""
        return sum(bet.stake for bet in self.open)

    def best_case(self) -> float:
        """What the book owes if every open bet lands. Feeds the escrow cap check."""
        return sum(bet.payout for bet in self.open)

    # ---- settling --------------------------------------------------------
    def settle(self, round_) -> list[Settlement]:
        """Settle every bet on that round against its close price. Credits the wallet."""
        out: list[Settlement] = []
        for bet in list(self.open):
            if bet.round_index != round_.index:
                continue
            self.open.remove(bet)
            if round_.voided:
                # No usable bell price: return the stake, record nothing as won.
                self.wallet.credit(bet.stake)
                out.append(Settlement(bet, False, round_.close_price, bet.stake,
                                      bet.stake, bet.multiple, True, round_.index))
            else:
                hit = bet.contains(round_.close_price)
                # Truncate to whole micro-USDC: a payout must never round up
                # into money the book did not owe.
                payout = int(bet.payout) if hit else 0
                self.wallet.credit(payout)
                self.hits += 1 if hit else 0
                out.append(Settlement(bet, hit, round_.close_price, bet.stake,
                                      payout, bet.multiple, False, round_.index))
            self.rounds += 1
        self.history.extend(out)
        return out

    def refund(self, round_index: int) -> int:
        """Cancel every bet on a round that has not started yet; returns the stake.

        Only ever call this for a round still ahead. Refunding a live bet is
        an early exit, and an early exit is a free option on the rest of the
        round -- take it away and the game is honest by construction.
        """
        given = 0
        for bet in list(self.open):
            if bet.round_index == round_index:
                self.open.remove(bet)
                self.wallet.credit(bet.stake)
                given += bet.stake
        return given

    def refund_all(self) -> int:
        given = 0
        for bet in list(self.open):
            self.open.remove(bet)
            self.wallet.credit(bet.stake)
            given += bet.stake
        return given

    # ---- reading ---------------------------------------------------------
    @property
    def last(self) -> Settlement | None:
        return self.history[-1] if self.history else None

    @property
    def streak(self) -> int:
        """Consecutive hits at the end of history. Three of these is a hat trick."""
        run = 0
        for settlement in reversed(self.history):
            if settlement.voided:
                continue
            if not settlement.hit:
                break
            run += 1
        return run
