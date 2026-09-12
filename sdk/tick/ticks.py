"""The one unit every layer above passes around: a price, stamped and numbered.

A tick is not a float. A float cannot tell you *when* it was true, whether it
arrived out of order, or how long it sat in a relay before it reached you --
and a game that settles money on a stale number is broken in a way no amount
of UI polish fixes. So every feed in this SDK produces `PriceTick`, and nothing
downstream accepts a bare number.
"""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class PriceTick:
    """One reading of the market.

    price        the number, in quote currency (USD)
    sequence     rises by one per reading from a given feed; lets a consumer
                 drop a duplicate or an out-of-order arrival without guessing
    received_at  monotonic seconds, on *this* machine's clock, when it landed
    source_age   seconds the reading was already old when it landed: a block
                 time, an exchange timestamp, a relay hop. Zero for the sim.
    """

    price: float
    sequence: int
    received_at: float
    source_age: float = 0.0

    def age(self, now: float) -> float:
        """Total staleness: time since arrival, plus how old it was on arrival."""
        return max(0.0, now - self.received_at) + self.source_age


@dataclass(frozen=True)
class Asset:
    """A coin the games can be played on.

    `sigma` is volatility per square-root second, set to roughly what the coin
    actually does. Testing a game against a feed an order of magnitude wilder
    than the real one teaches the wrong thing about your own odds.
    """

    key: str
    symbol: str
    coinbase: str          # Coinbase product id
    start: float           # the simulated feed's opening price
    sigma: float           # volatility per square-root second
    places: int = 2        # decimals shown on screen; a sub-dollar coin needs more

    def format(self, price: float, sign: bool = False) -> str:
        return f'{price:{"+" if sign else ""},.{self.places}f}'


ASSETS = {
    'eth': Asset('eth', 'ETH', 'ETH-USD', 2500.0, 0.00009),
    'btc': Asset('btc', 'BTC', 'BTC-USD', 77_000.0, 0.00007),
    'sol': Asset('sol', 'SOL', 'SOL-USD', 100.0, 0.00013),
    'hbar': Asset('hbar', 'HBAR', 'HBAR-USD', 0.075, 0.00015, places=5),
}


def current_asset() -> Asset:
    """The coin named by TICK_ASSET, ETH by default."""
    key = os.environ.get('TICK_ASSET', 'eth').strip().lower()
    if key not in ASSETS:
        raise ValueError(f"TICK_ASSET must be one of {', '.join(ASSETS)}")
    return ASSETS[key]
