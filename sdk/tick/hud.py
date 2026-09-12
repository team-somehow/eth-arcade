"""A screen that already looks like the device, so your game can be one file.

Three pieces, all optional:

* `draw_hud(ctx, screen)` -- the top bar (game, price, balance) and the bottom
  bar (button hints and the status line). Two calls and your game is legible.
* `Ladder` -- price to pixels and back. Every game here is a claim about where
  a number will be, so every game needs a vertical price scale; this is it.
* `draw_bet` / `draw_cursor` -- the SDK's drawing convention for bets, so a
  player who has used one of these games can read the next one: **dashed means
  not committed, solid means money is on it.**

Anchoring
---------

Anchor the ladder on the round's **opening price**, not on spot. Anchoring on
spot re-centres the view every tick and pins the newest point to the middle of
the screen, which makes movement impossible to see -- the price looks still
while the world slides around it. Against a reference that holds still for the
whole round, a move reads instantly.
"""
from __future__ import annotations

import pygame

from .ui import CREAM, GRID, MINT, MUTED, NAVY, PANEL, RED, YELLOW, dashed_rect, font, label, say

TOP_H = 30
BOTTOM_Y = 274


def draw_hud(ctx, s: pygame.Surface, back: str = 'HOME', go: str = 'BUY',
             top: bool = True, bottom: bool = True) -> None:
    """The standard top and bottom bars. Draw your game between them."""
    if top:
        pygame.draw.rect(s, PANEL, (0, 0, 480, TOP_H))
        label(s, ctx.game.title[:18], 8, 7, 16, CREAM)
        asset = getattr(ctx.market.asset, 'symbol', 'ETH')
        price = getattr(ctx.market.asset, 'format', lambda p: f'{p:,.2f}')(ctx.price)
        label(s, f'{asset} {price}', 168, 7, 16, MINT if ctx.market.fresh(ctx.now) else RED)
        balance = ctx.usdc(ctx.wallet.balance)
        art = font(16).size(balance + ' USDC')[0]
        label(s, balance + ' USDC', 472 - art, 7, 16, YELLOW)
    if bottom:
        pygame.draw.rect(s, PANEL, (0, BOTTOM_Y, 480, 320 - BOTTOM_Y))
        pygame.draw.circle(s, RED, (20, 297), 6)
        pygame.draw.circle(s, YELLOW, (254, 297), 6)
        label(s, back, 34, 289, 15, MUTED)
        label(s, go, 268, 289, 15, MUTED)
        line = ctx.status_line()
        if line:
            art = font(15).size(line)[0]
            label(s, line, 472 - art, 289, 15, CREAM)


def draw_clock(ctx, s: pygame.Surface, x: int = 240, y: int = 36) -> None:
    """Seconds to the bell, big, centred -- the one number a player must see."""
    left = ctx.remaining
    colour = RED if left <= 3 else CREAM
    say(s, f'{left:04.1f}s', x, y, 22, colour, center=True)


class Ladder:
    """A vertical price scale: price in, pixels out.

    `half` is half the visible band in quote currency. Size it to the round's
    reachable range and no wider: widen it to fit every possible bet and a
    dollar of real movement becomes an invisible wobble.
    """

    def __init__(self, centre: float, half: float, top: int = 34, bottom: int = 268) -> None:
        self.centre = centre
        self.half = max(half, 1e-9)
        self.top = top
        self.bottom = bottom

    @property
    def middle(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def pixels(self) -> float:
        return (self.bottom - self.top) / 2

    def y_of(self, price: float) -> float:
        return self.middle - (price - self.centre) / self.half * self.pixels

    def price_at(self, y: float) -> float:
        return self.centre + (self.middle - y) / self.pixels * self.half

    def clamped_y(self, price: float) -> tuple[float, bool]:
        """(y, off_scale). Clamp rather than draw a bet off the screen edge."""
        y = self.y_of(price)
        if y < self.top:
            return self.top, True
        if y > self.bottom:
            return self.bottom, True
        return y, False

    def rect(self, low: float, high: float, x: int, width: int) -> pygame.Rect:
        top, _ = self.clamped_y(high)
        bottom, _ = self.clamped_y(low)
        return pygame.Rect(x, int(top), width, max(3, int(bottom - top)))


def draw_grid(s: pygame.Surface, ladder: Ladder, step: float, colour=GRID) -> None:
    """Faint horizontal lines every `step` of price, so movement has a scale."""
    if step <= 0:
        return
    price = ladder.centre - ladder.half
    price -= price % step
    while price <= ladder.centre + ladder.half:
        y = ladder.y_of(price)
        if ladder.top <= y <= ladder.bottom:
            pygame.draw.line(s, colour, (0, int(y)), (480, int(y)))
        price += step


def draw_open_line(s: pygame.Surface, ladder: Ladder, price: float) -> None:
    """The round's opening price: the reference everything else is read against."""
    y = int(ladder.y_of(price))
    for x in range(0, 480, 10):
        pygame.draw.line(s, (74, 96, 103), (x, y), (x + 5, y))


def draw_bet(s: pygame.Surface, ladder: Ladder, bet, x: int, width: int,
             colour=YELLOW, solid: bool = True, glow: bool = False) -> pygame.Rect:
    """A placed bet: solid means the money is committed."""
    rect = ladder.rect(bet.low, bet.high, x, width)
    if glow:
        pygame.draw.rect(s, (44, 80, 98), rect)
    if solid:
        pygame.draw.rect(s, colour, rect, 2)
    else:
        dashed_rect(s, rect, colour)
    return rect


def draw_cursor(s: pygame.Surface, ladder: Ladder, low: float, high: float,
                x: int, width: int, colour=YELLOW) -> pygame.Rect:
    """The aim box: dashed, because nothing has been bought yet."""
    rect = ladder.rect(low, high, x, width)
    dashed_rect(s, rect, colour)
    return rect


def draw_price_line(s: pygame.Surface, ladder: Ladder, history, now: float,
                    seconds: float = 12.0, px_per_s: float = 16.0,
                    right_x: int = 240, colour=MINT) -> None:
    """The recent price trace, time running left to right into `right_x`."""
    points = []
    for t, p in history:
        age = now - t
        if age > seconds:
            continue
        y = ladder.y_of(p)
        points.append((right_x - age * px_per_s, max(ladder.top, min(ladder.bottom, y))))
    if len(points) > 1:
        pygame.draw.lines(s, colour, False, points, 2)


def clear(s: pygame.Surface, colour=NAVY) -> None:
    s.fill(colour)
