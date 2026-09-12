"""Money, in integers, because floats lose it.

Everything here is **micro-USDC**: whole units of 0.000001 USDC, the real
on-chain unit. A balance that is an int cannot drift the way repeated float
addition does, and `0.1 + 0.2` never has to be explained to a player. Only
mark-to-market maths runs in floats, and it is truncated back to an int the
moment it becomes a balance -- truncated, never rounded, so a payout can never
round money into existence that the book did not owe.

The funding seam
----------------

`Wallet` holds the balance. *Where the balance comes from* is a separate object
with three members:

    name    what to put on screen        'DEMO' / 'USDC'
    live    is this real money?
    load(amount) -> Deposit

`DemoFunding` mints play money. `tick.escrow.EscrowFunding` is real testnet
USDC locked in a contract. A game imports neither: it reads `ctx.wallet`, and
the runtime picks the backend from TICK_FUNDING. That is why the same game is
both a demo and a real-money product without an `if` in it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import os
import time

MICRO = 1_000_000
LOAD_CHOICES = (10, 25, 100)      # the load buttons, in whole USDC
DEFAULT_STAKE_USDC = '10'
MAX_USDC = 10 ** 12          # a sanity bound, far above anything a session holds


def to_micro(usdc: float) -> int:
    """Whole/decimal USDC to micro-USDC, truncated."""
    return int(usdc * MICRO)


@lru_cache(maxsize=16)
def parse_usdc(text: str) -> int:
    """A typed USDC amount to micro-USDC, exactly.

    Decimal, not float: `float('0.57') * 1e6` is 569999.9999999999, and a book
    that credits 569_999 micro for 0.57 USDC is a book with a bug in it.
    """
    try:
        value = Decimal(str(text).strip())
    except InvalidOperation:
        raise ValueError(f'Not a USDC amount: {text!r}') from None
    if not value.is_finite():
        raise ValueError(f'Not a USDC amount: {text!r}')
    micro = value * MICRO
    if micro != micro.to_integral_value():
        raise ValueError(f'USDC has six decimals at most: {text!r}')
    # Nothing real is this large. An unbounded amount here becomes an unbounded
    # balance downstream, and a balance no escrow could ever pay.
    if abs(value) > MAX_USDC:
        raise ValueError(f'USDC amount out of range: {text!r}')
    return int(micro)


def stake_micro(default: str | None = None) -> int:
    """Micro-USDC per bet, from TICK_STAKE_USDC (10 USDC by default)."""
    micro = parse_usdc(os.environ.get('TICK_STAKE_USDC', default or DEFAULT_STAKE_USDC))
    if micro <= 0:
        raise ValueError('TICK_STAKE_USDC must be above zero')
    return micro


def places_for(micro: int) -> int:
    """Fewest decimals that show `micro` exactly: 0 for whole USDC, up to 6."""
    places = 6
    while places and micro % 10 ** (7 - places) == 0:
        places -= 1
    return places


def format_usdc(micro: int, places: int | None = None) -> str:
    """Two decimals, or as many as the stake needs, so a 0.001 bet is visible."""
    if places is None:
        places = max(2, places_for(stake_micro()))
    return f'{micro / MICRO:,.{places}f}'


@dataclass(frozen=True)
class Deposit:
    """One funding attempt. `reference` is a tx hash for real backends."""
    amount: int
    status: str                # 'confirmed' | 'pending' | 'failed'
    reference: str
    at: float = field(default_factory=time.time)


class DemoFunding:
    """Local play money. No address, no network, nothing to lose."""
    name = 'DEMO'
    live = False
    onchain = False

    def __init__(self) -> None:
        self.count = 0

    def load(self, amount: int) -> Deposit:
        self.count += 1
        return Deposit(amount, 'confirmed', f'demo-{self.count}')


class Wallet:
    """Spendable balance in micro-USDC, plus a log of every funding attempt."""

    def __init__(self, balance: int = 100 * MICRO, funding: object | None = None) -> None:
        if balance < 0:
            raise ValueError('Balance cannot start negative')
        self.balance = int(balance)
        self.funding = funding or DemoFunding()
        self.deposits: list[Deposit] = []
        self.staked_total = 0
        self.paid_total = 0

    @property
    def live(self) -> bool:
        return bool(getattr(self.funding, 'live', False))

    @property
    def onchain(self) -> bool:
        return bool(getattr(self.funding, 'onchain', False))

    @property
    def cap(self) -> int | None:
        """The most the balance may grow to and still be paid out, if anything limits it.

        Real escrow can only pay what it holds. A game must refuse a bet whose
        best case would win past this, or the screen promises what the contract
        will not send.
        """
        return getattr(self.funding, 'cap', None)

    def load(self, usdc: int) -> Deposit:
        """Fund the balance through the configured backend."""
        deposit = self.funding.load(usdc * MICRO)
        self.deposits.append(deposit)
        # Only a confirmed deposit is spendable: pending and failed leave the
        # balance alone, so a player never stakes money that never arrived.
        if deposit.status == 'confirmed':
            self.balance += deposit.amount
        return deposit

    def debit(self, amount: int) -> bool:
        if amount <= 0 or amount > self.balance:
            return False
        self.balance -= amount
        self.staked_total += amount
        return True

    def credit(self, amount: int) -> None:
        if amount < 0:
            raise ValueError('Cannot credit a negative amount')
        self.balance += amount
        self.paid_total += amount

    def can_afford(self, amount: int) -> bool:
        return self.balance >= amount

    def would_exceed_cap(self, best_case: int) -> bool:
        """Would a best case of `best_case` micro win past what can be paid out?"""
        cap = self.cap
        return cap is not None and best_case > cap

    def __repr__(self) -> str:
        return f'<Wallet {format_usdc(self.balance)} {getattr(self.funding, "name", "?")}>'
