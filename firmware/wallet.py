"""Player balance and the funding seam.

Money is held as integer **micro-USDC** (6 decimals, the real USDC unit) so a
balance can never drift the way repeated float addition does. Only the ride's
mark-to-market runs in floats, and it is rounded back to micro on settlement.

`DemoFunding` is the only backend wired up today: it mints local play money.
`UsdcFunding` is the shape a real deposit takes and deliberately does not move
funds — see its docstring for what has to be implemented before it can.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import time

MICRO = 1_000_000
# Load buttons on the device, in whole USDC.
LOAD_CHOICES = (10, 25, 100)


def to_micro(usdc: float) -> int:
    """Whole/decimal USDC to micro-USDC, truncated (never credit a rounded-up cent)."""
    return int(usdc * MICRO)


def format_usdc(micro: int, places: int = 2) -> str:
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


class UsdcFunding:
    """Placeholder for a real USDC deposit. Intentionally credits nothing.

    A working version needs, in order: a session key held on the device, an
    ERC-20 `transfer`/`permit` of `amount` (6 decimals) from the player's
    account to that key on a chosen chain, and confirmation polling before the
    balance moves. Credit only on a receipt: an optimistic credit here would be
    play money that later disappears.
    """
    name = 'USDC'
    live = True

    def __init__(self, chain: str = 'base', token: str = '', account: str = '') -> None:
        self.chain = chain
        self.token = token
        self.account = account

    def load(self, amount: int) -> Deposit:
        return Deposit(amount, 'failed', 'usdc-backend-not-implemented')


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
