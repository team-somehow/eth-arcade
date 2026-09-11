"""Player balance and the funding seam.

Money is held as integer **micro-USDC** (6 decimals, the real USDC unit) so a
balance can never drift the way repeated float addition does. Only the ride's
mark-to-market runs in floats, and it is rounded back to micro on settlement.

`DemoFunding` mints local play money. `arc.ArcFunding` is real testnet USDC:
the player sends it to the device, it is locked in the TickEscrow contract,
and the escrow limits how far the balance can grow and still be paid out
(`Wallet.cap`).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import os
import time

MICRO = 1_000_000
# Load buttons on the device, in whole USDC.
LOAD_CHOICES = (10, 25, 100)
# USDC staked per press of A in BOX RUN and per ride in RUSH, unless
# TICK_STAKE_USDC says otherwise. A stake like 0.001 keeps real-funds tests cheap.
DEFAULT_STAKE_USDC = '10'


def to_micro(usdc: float) -> int:
    """Whole/decimal USDC to micro-USDC, truncated (never credit a rounded-up cent)."""
    return int(usdc * MICRO)


@lru_cache(maxsize=8)
def parse_usdc(text: str) -> int:
    """A typed USDC amount to micro-USDC, exactly.

    Decimal rather than float: float arithmetic turns 0.57 into 569_999 micro.
    More than six decimals is refused, since USDC cannot hold it.
    """
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise ValueError(f'Not a USDC amount: {text!r}') from None
    if not value.is_finite():
        raise ValueError(f'Not a USDC amount: {text!r}')
    micro = value * MICRO
    if micro != micro.to_integral_value():
        raise ValueError(f'USDC has six decimals at most: {text!r}')
    return int(micro)


def stake_micro() -> int:
    """Micro-USDC staked per press, from TICK_STAKE_USDC (10 USDC by default)."""
    micro = parse_usdc(os.environ.get('TICK_STAKE_USDC', DEFAULT_STAKE_USDC))
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
    status: str  # 'confirmed' | 'pending' | 'failed'
    reference: str
    at: float = field(default_factory=time.time)


class DemoFunding:
    """Local play money. No address, no network, nothing to lose."""
    name = 'DEMO'
    live = False

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

    @property
    def live(self) -> bool:
        return bool(getattr(self.funding, 'live', False))

    @property
    def cap(self) -> int | None:
        """The most the balance can grow to and still be paid out, if anything limits it."""
        return getattr(self.funding, 'cap', None)

    def load(self, usdc: int) -> Deposit:
        """Fund the balance through the configured backend."""
        if usdc not in LOAD_CHOICES:
            raise ValueError('Unsupported load amount')
        deposit = self.funding.load(usdc * MICRO)
        self.deposits.append(deposit)
        # Only a confirmed deposit is spendable; pending/failed leave the
        # balance alone so the player never stakes money that never arrived.
        if deposit.status == 'confirmed':
            self.balance += deposit.amount
        return deposit

    def debit(self, amount: int) -> bool:
        if amount <= 0 or amount > self.balance:
            return False
        self.balance -= amount
        return True

    def credit(self, amount: int) -> None:
        if amount < 0:
            raise ValueError('Cannot credit a negative amount')
        self.balance += amount
