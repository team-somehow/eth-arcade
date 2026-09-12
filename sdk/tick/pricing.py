"""Odds, from first principles, in about fifty lines.

The question every game on this device asks is the same one:

    the price is P now. What is the chance it is between LOW and HIGH in
    H seconds -- and what multiple should I pay someone who calls it?

**Chance.** Over a short horizon a price is a random walk in log space. The
distance it travels grows with the *square root* of time, not with time. So one
standard deviation over H seconds is `P * sqrt(variance_per_second * H)`, and
the chance of landing in a range is the normal CDF at the top minus the CDF at
the bottom. That is `probability()` below, and it is the whole model.

**Multiple.** Fair odds are `1 / chance`: a one-in-four shot pays 4x, and over
many rounds the book breaks even. A house edge is one multiplication -- pass
`edge=0.05` and the book keeps 5%. This SDK defaults to **zero edge and says
so**, because a demo that hides a margin teaches the player the wrong thing
about what they just played.

Three guards, each of which was a real bug before it was a rule:

* `cap` -- an unbounded multiple is a promise you cannot fund. Cap it.
* `floor` -- anything quoting near 1.0x is a near-certain win. Do not sell it;
  it is not a bet, it is a withdrawal.
* variance floor -- a feed printing one price repeatedly must not collapse the
  spread to zero and quote infinity.
"""
from __future__ import annotations

import math

SECONDS_PER_YEAR = 31_536_000
# Fallback volatility until enough ticks have arrived to measure any:
# ~55% annualized, as variance per second of relative return.
DEFAULT_VARIANCE = (0.55 ** 2) / SECONDS_PER_YEAR


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def sigma(price: float, variance_per_second: float, horizon: float) -> float:
    """One standard deviation of price movement over `horizon` seconds."""
    return price * math.sqrt(max(variance_per_second, 0.0) * max(horizon, 0.001))


def probability(price: float, low: float, high: float,
                variance_per_second: float, horizon: float) -> float:
    """Chance the price sits in [low, high] after `horizon` seconds."""
    spread = sigma(price, variance_per_second, horizon)
    if spread <= 0 or price <= 0 or high < low:
        return 0.0
    return max(0.0, normal_cdf((high - price) / spread) - normal_cdf((low - price) / spread))


def multiple(chance: float, edge: float = 0.0, cap: float = 25.0) -> float:
    """Fair return multiple (stake included) for a bet with this chance."""
    if chance <= 0:
        return cap
    return min(cap, (1.0 - edge) / chance)


def scale_to_window(value_bps: float, window_s: float, reference_s: float = 20.0) -> float:
    """Restate a geometry quoted for `reference_s` at a different window length.

    Prices travel with the square root of time, so a box that was a fair 2x
    over twenty seconds is a near-certainty over ten. Scale the *geometry* by
    sqrt(window / reference) and the ladder of odds holds at any window length:
    `WINDOW_S` becomes a knob you can turn without redesigning the game.
    """
    return value_bps * math.sqrt(max(window_s, 0.001) / max(reference_s, 0.001))


def annualized(variance_per_second: float) -> float:
    """Variance per second as an annualized volatility, for putting on screen."""
    return math.sqrt(max(variance_per_second, 0.0) * SECONDS_PER_YEAR)
