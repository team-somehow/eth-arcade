"""BOX RUN: crank the box, buy the next 20 seconds. Renderer and input adapter."""
from __future__ import annotations
import os
import time
from typing import Callable

import pygame

from games.box_model import BoxModel
from input import InputAction, event_position
from markets.feed import CoinbaseFeed, SimulatedFeed
from ui import NAVY, PANEL, GRID, CREAM, MUTED, YELLOW, MINT, RED, Sounds, label, footer
from wallet import LOAD_CHOICES, MICRO, DemoFunding, UsdcFunding, Wallet, format_usdc

# Chart geometry. Time reads left to right: history, this window's bell, the
# next one's — then your hand. A placed bet visibly jumps left out of the AIM
# lane, which is the only signal that says "you cannot crank this any more".
TRACE = pygame.Rect(14, 72, 192, 166)
NOW_COL = pygame.Rect(210, 72, 82, 166)
NEXT_COL = pygame.Rect(296, 72, 82, 166)
AIM_COL = pygame.Rect(382, 72, 82, 166)
MID_Y = TRACE.centery
HALF_PX = TRACE.height // 2 - 9
# Boxes are drawn inside this band, which has to cover the whole price range a
# box can legally reach — squeeze it and a box at full crank gets clipped and
# flagged off-scale when it is really on screen. Labels draw over it instead.
BAND_TOP = TRACE.top + 4
BAND_BOTTOM = TRACE.bottom - 4
TRACE_S = BoxModel.WINDOW_S * 1.2   # history across the trace: this window, plus a lead-in
OPEN_LINE = (74, 96, 103)
DEAD = (17, 30, 41)       # the AIM lane once the bet is locked


def build_wallet() -> Wallet:
    """TICK_FUNDING=usdc swaps in the real deposit shape (which credits nothing)."""
    kind = os.environ.get('TICK_FUNDING', 'demo')
    if kind not in ('demo', 'usdc'):
        raise ValueError('TICK_FUNDING must be demo or usdc')
    if kind == 'usdc':
        return Wallet(0, UsdcFunding(
            chain=os.environ.get('TICK_CHAIN', 'base'),
            token=os.environ.get('TICK_USDC_ADDRESS', ''),
            account=os.environ.get('TICK_ACCOUNT', ''),
        ))
    return Wallet(100 * MICRO, DemoFunding())


def dashed_rect(s: pygame.Surface, rect: pygame.Rect, color: tuple, dash: int = 6) -> None:
    for x in range(rect.left, rect.right, dash * 2):
        end = min(x + dash, rect.right)
        pygame.draw.line(s, color, (x, rect.top), (end, rect.top), 2)
        pygame.draw.line(s, color, (x, rect.bottom - 1), (end, rect.bottom - 1), 2)
    for y in range(rect.top, rect.bottom, dash * 2):
        end = min(y + dash, rect.bottom)
        pygame.draw.line(s, color, (rect.left, y), (rect.left, end), 2)
        pygame.draw.line(s, color, (rect.right - 1, y), (rect.right - 1, end), 2)


class BoxGame:
    def __init__(self, seed: int | None = None, sound: bool = True,
                 source: str | None = None, wallet: Wallet | None = None,
                 clock: Callable[[], float] | None = None) -> None:
        source = source or os.environ.get('TICK_MARKET_SOURCE', 'sim')
        if source not in ('sim', 'coinbase'):
            raise ValueError('TICK_MARKET_SOURCE must be sim or coinbase')
        self.feed = CoinbaseFeed() if source == 'coinbase' else SimulatedFeed(seed)
        self.model = BoxModel(wallet or build_wallet())
        self.sounds = Sounds() if sound else None
        # Wall-clock monotonic in play: live ticks are stamped on the same
        # clock, so the window bell and staleness stay honest. Tests inject.
        self._now = clock or time.monotonic
        self.clock = self._now()
        self.held: dict[int, float] = {}
        self.wallet_open = False
        self.amount_index = 1
        self.message = ''
        self.message_until = 0.0
        self.last_sound_at = 0.0
        self.flash_until = 0.0
        self.last_bell = 0

    def enter(self) -> None:
        self.held.clear()
        self.wallet_open = False

    def close(self) -> None:
        self.feed.close()

    def play(self, name: str) -> None:
        if self.sounds:
            self.sounds.play(name)

    def note(self, text: str, seconds: float = 2.0) -> None:
        self.message, self.message_until = text, self.clock + seconds

    def open_wallet(self) -> None:
        self.wallet_open = True
        self.held.clear()

    def load_selected(self) -> None:
        amount = LOAD_CHOICES[self.amount_index]
        deposit = self.model.wallet.load(amount)
        self.wallet_open = False
        if deposit.status == 'confirmed':
            self.note(f'+{amount} {self.model.wallet.funding.name} USDC IN')
            self.play('select')
        else:
            self.note(f'DEPOSIT {deposit.status.upper()} / NOT CREDITED', 3)

    # ---- input -----------------------------------------------------------
    def crank(self, steps: int) -> None:
        m = self.model
        if m.locked:
            # The bet is placed: the dial does nothing until the bell.
            self.note('BOX LOCKED / A ADDS 10', 1.5)
            return
        if m.crank(steps) and self.clock - self.last_sound_at > .05:
            self.play('move')
            self.last_sound_at = self.clock

    def buy(self) -> None:
        m = self.model
        if not m.can_buy():
            self.open_wallet()
            return
        if m.buy(self.clock):
            self.play('lock')
            self.message = ''
        elif not m.fresh(self.clock):
            self.note('NO LIVE PRICE / NOT PLACED')
        elif m.settling:
            self.note('SETTLING LAST WINDOW')

    def handle_action(self, action: InputAction) -> str | None:
        if action == InputAction.QUIT:
            return 'quit'
        if self.wallet_open:
            if action in (InputAction.UP, InputAction.DOWN):
                step = 1 if action == InputAction.UP else -1
                self.amount_index = (self.amount_index + step) % len(LOAD_CHOICES)
            elif action == InputAction.A:
                self.load_selected()
            elif action == InputAction.B:
                self.wallet_open = False
            return None
        if action in (InputAction.UP, InputAction.DOWN):
            self.crank(1 if action == InputAction.UP else -1)
        elif action == InputAction.A:
            self.buy()
        elif action == InputAction.B:
            self.held.clear()
            return 'home'
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        x, y = pos
        if y >= 274:
            return self.handle_action(InputAction.B if x < 240 else InputAction.A)
        if self.wallet_open:
            return self.handle_action(InputAction.UP if x >= 240 else InputAction.DOWN)
        if TRACE.top <= y < TRACE.bottom:
            # Tap above or below the middle of the chart to crank the box.
            return self.handle_action(InputAction.UP if y < MID_Y else InputAction.DOWN)
        return None

    def update(self, dt: float) -> None:
        self.clock = self._now()
        m = self.model
        rounds_before = m.rounds
        for key in list(self.held):
            self.held[key] -= dt
            if self.held[key] <= 0:
                self.crank(1 if key in (pygame.K_UP, pygame.K_w) else -1)
                if key in self.held:
                    self.held[key] = .05
        for tick in self.feed.poll(dt, self.clock):
            m.on_tick(tick, self.clock)
        m.update(self.clock)
        if m.rounds != rounds_before and m.last is not None:
            self.play('miss' if m.last.voided else ('hit' if m.last.hit else 'miss'))
            self.flash_until = self.clock + 1.6
        # Count down the last seconds of a window that has money on it.
        left = int(m.remaining(self.clock))
        if m.live is not None and m.live.stake and 0 < left <= 3 and left != self.last_bell:
            self.play('tick')
        self.last_bell = left

    # ---- drawing ---------------------------------------------------------
    def y_of(self, price: float) -> int:
        """Price to screen, anchored on the window's opening price.

        Anchoring on spot instead would re-centre the chart on every tick and
        pin the latest point to the middle, which makes movement invisible.
        """
        m = self.model
        if m.view_half <= 0:
            return MID_Y
        return round(MID_Y - (price - m.window_open) / m.view_half * HALF_PX)

    def draw(self, s: pygame.Surface) -> None:
        m = self.model
        s.fill(NAVY)
        label(s, 'BOX RUN', 14, 5, 20, CREAM)
        label(s, f'{format_usdc(m.wallet.balance)} {m.wallet.funding.name}', 336, 9, 16, MINT)
        pygame.draw.line(s, GRID, (14, 32), (466, 32))
        if self.wallet_open:
            self.draw_wallet(s)
            return
        if not m.started:
            label(s, f'{self.feed.name} / PAPER', 14, 40, 16, MUTED)
            label(s, 'WAITING FOR THE', 240, 130, 22, YELLOW, True)
            label(s, 'FIRST PRICE...', 240, 165, 22, YELLOW, True)
            footer(s, '< HOME', 'BUY 10 >')
            return
        label(s, f'${m.price:,.2f}', 14, 38, 22, CREAM)
        label(s, 'MOVE', 172, 47, 13, MUTED)
        label(s, f'{m.move:+,.2f}', 218, 38, 22, MINT if m.move >= 0 else RED)
        if m.settling:
            label(s, 'SETTLING', 348, 44, 18, RED)
        else:
            left = m.remaining(self.clock)
            label(s, 'BELL', 352, 47, 13, MUTED)
            label(s, f'{int(left):02d}s', 402, 36, 26, RED if left <= 3 else YELLOW)
        self.draw_chart(s)
        self.draw_status(s)
        footer(s, '< HOME', 'BUY 10 >' if m.can_buy() else 'LOAD >')

    def draw_chart(self, s: pygame.Surface) -> None:
        m = self.model
        locked = m.locked
        for rect in (TRACE, NOW_COL, NEXT_COL):
            pygame.draw.rect(s, PANEL, rect)
        pygame.draw.rect(s, DEAD if locked else PANEL, AIM_COL)
        # A ruler in box-heights: the band is exactly two boxes either way, so
        # "the price has moved one box" is something you can see at a glance.
        for step in (-2, -1, 1, 2):
            y = self.y_of(m.window_open + step * 2 * m.half)
            pygame.draw.line(s, GRID, (TRACE.left, y), (TRACE.right, y), 1)
        open_y = self.y_of(m.window_open)
        for x in range(TRACE.left, AIM_COL.right, 10):
            pygame.draw.line(s, OPEN_LINE, (x, open_y), (x + 5, open_y), 1)

        clip = s.get_clip()
        s.set_clip(TRACE)
        points = [(TRACE.right - round((self.clock - t) / TRACE_S * TRACE.width), self.y_of(p))
                  for t, p in m.history if self.clock - t <= TRACE_S]
        if len(points) > 1:
            pygame.draw.lines(s, CREAM, False, points, 3)
        s.set_clip(clip)

        # Where spot sits relative to the boxes, carried across the columns.
        spot_y = max(TRACE.top + 1, min(TRACE.bottom - 2, self.y_of(m.price)))
        for x in range(TRACE.right - 10, AIM_COL.right, 7):
            pygame.draw.line(s, CREAM, (x, spot_y), (x + 3, spot_y), 1)
        label(s, 'OPEN', TRACE.left + 3, open_y + 3, 12, MUTED)
        if not TRACE.top < self.y_of(m.price) < TRACE.bottom:
            label(s, 'OFF SCALE', TRACE.left + 40, spot_y - 14, 13, YELLOW)

        flashing = self.clock < self.flash_until and m.last is not None
        if m.live is not None and m.live.stake:
            self.draw_box(s, NOW_COL, m.live.low, m.live.high, YELLOW,
                          stake=m.live.stake, multiple=m.live.multiple)
        elif flashing:
            self.draw_result(s)
        if locked:
            self.draw_box(s, NEXT_COL, m.pending.low, m.pending.high, CREAM,
                          stake=m.pending.stake, multiple=m.pending.multiple)
            label(s, 'LOCKED', AIM_COL.x + 4, AIM_COL.bottom - 23, 14, MUTED)
        else:
            dashed_rect(s, self.box_rect(AIM_COL, m.aim - m.half, m.aim + m.half), YELLOW)
            label(s, f'{m.quote(m.aim, self.clock):.1f}x',
                  AIM_COL.x + 4, AIM_COL.bottom - 24, 17, YELLOW)
        label(s, 'NOW', NOW_COL.x + 5, 76, 13, MUTED)
        label(s, 'NEXT', NEXT_COL.x + 5, 76, 13, MUTED)
        label(s, 'AIM', AIM_COL.x + 5, 76, 13, GRID if locked else MUTED)

    def box_rect(self, col: pygame.Rect, low: float, high: float) -> pygame.Rect:
        top = max(BAND_TOP, min(BAND_BOTTOM - 8, self.y_of(high)))
        bottom = max(top + 8, min(BAND_BOTTOM, self.y_of(low)))
        return pygame.Rect(col.x + 3, top, col.width - 6, bottom - top)

    def draw_box(self, s: pygame.Surface, col: pygame.Rect, low: float, high: float,
                 color: tuple, stake: int = 0, multiple: float = 0.0) -> None:
        rect = self.box_rect(col, low, high)
        tint = tuple(int(c * .18 + PANEL[i] * .82) for i, c in enumerate(color))
        pygame.draw.rect(s, tint, rect)
        pygame.draw.rect(s, color, rect, 3)
        # The box stays a clean shape; its numbers live on the column floor.
        if self.y_of(high) < BAND_TOP:
            pygame.draw.polygon(s, color, [(col.centerx, col.y + 6),
                                           (col.centerx - 7, col.y + 15),
                                           (col.centerx + 7, col.y + 15)])
        if self.y_of(low) > BAND_BOTTOM:
            pygame.draw.polygon(s, color, [(col.centerx, BAND_BOTTOM + 12),
                                           (col.centerx - 7, BAND_BOTTOM + 3),
                                           (col.centerx + 7, BAND_BOTTOM + 3)])
        if stake:
            label(s, f'{format_usdc(stake, 0)} @ {multiple:.1f}x',
                  col.x + 4, col.bottom - 22, 14, color)

    def draw_result(self, s: pygame.Surface) -> None:
        """Flash the box that just settled, so you see where the price landed."""
        result = self.model.last
        color = MUTED if result.voided else (MINT if result.hit else RED)
        self.draw_box(s, NOW_COL, result.low, result.high, color)
        word = 'VOID' if result.voided else ('HIT' if result.hit else 'MISS')
        y = self.y_of(result.high) - 24 if result.hit else self.y_of(result.price) - 10
        label(s, word, NOW_COL.centerx, max(NOW_COL.y + 18, min(NOW_COL.bottom - 26, y)),
              21, color, True)

    def status(self) -> tuple[str, tuple]:
        """The one line of words at the bottom, as text and colour.

        Separate from drawing so the money it quotes can be asserted; the
        payout is micro-USDC like every other balance in the game.
        """
        m = self.model
        result = m.last
        if self.clock < self.message_until:
            return self.message, MINT
        if result is not None and self.clock < self.flash_until + 3:
            if result.voided:
                return f'VOID / {format_usdc(result.stake, 0)} BACK', MUTED
            if result.hit:
                return f'HIT / PAID {format_usdc(result.payout)}', MINT
            return f'MISS / -{format_usdc(result.stake, 0)}', RED
        if m.live is not None and m.live.stake:
            return (f'{format_usdc(m.live.stake, 0)} IN / PAYS '
                    f'{format_usdc(int(m.live.payout))}'), YELLOW
        if m.pending is not None:
            return 'PLACED / A ADDS 10 MORE', CREAM
        return f'CRANK / A BUYS NEXT {self.model.WINDOW_S:.0f}s', MUTED

    def draw_status(self, s: pygame.Surface) -> None:
        m = self.model
        text, color = self.status()
        label(s, text[:27], 14, 244, 17, color)
        if m.rounds:
            label(s, f'HITS {m.hits}/{m.rounds}', 380, 246, 15, MUTED)

    def draw_wallet(self, s: pygame.Surface) -> None:
        wallet = self.model.wallet
        label(s, f'LOAD {wallet.funding.name} USDC', 240, 50, 26, YELLOW, True)
        subtitle = ('Real deposit path is not wired yet.' if wallet.live
                    else 'LOCAL TEST BALANCE / NO REAL MONEY')
        label(s, subtitle, 240, 88, 15, MUTED, True)
        for i, amount in enumerate(LOAD_CHOICES):
            rect = pygame.Rect(16 + i * 155, 122, 140, 66)
            pygame.draw.rect(s, YELLOW if i == self.amount_index else PANEL, rect, border_radius=4)
            label(s, f'+{amount}', rect.centerx, 138, 28,
                  NAVY if i == self.amount_index else CREAM, True)
        label(s, 'UP / DOWN TO CHOOSE', 240, 204, 17, MUTED, True)
        label(s, f'{len(wallet.deposits)} LOADS THIS SESSION', 240, 236, 15, CREAM, True)
        footer(s, '< BACK', 'LOAD >')


def handle_box_events(game: BoxGame, events: list, actions: list[InputAction]) -> str | None:
    for event in events:
        if event.type == pygame.WINDOWFOCUSLOST:
            game.held.clear()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                game.open_wallet()
            elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s) and not game.wallet_open:
                # Held keys emulate a spun dial for desktop testing.
                game.held[event.key] = .12
        elif event.type == pygame.KEYUP:
            game.held.pop(event.key, None)
        pos = event_position(event)
        if pos is not None:
            target = game.handle_touch(pos)
            if target:
                return target
    for action in actions:
        target = game.handle_action(action)
        if target:
            return target
    return None
