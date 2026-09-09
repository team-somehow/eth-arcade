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

# Chart geometry. The trace ends where the two expiry columns begin, so time
# reads left to right: history, this window's bell, the next one's.
TRACE = pygame.Rect(14, 66, 274, 176)
THIS_COL = pygame.Rect(292, 66, 80, 176)
NEXT_COL = pygame.Rect(376, 66, 80, 176)
# With a bet already down, NEXT splits: the bought box left, the cursor right.
BET_COL = pygame.Rect(NEXT_COL.x, NEXT_COL.y, 40, NEXT_COL.height)
AIM_COL = pygame.Rect(NEXT_COL.x + 42, NEXT_COL.y, 38, NEXT_COL.height)
MID_Y = TRACE.centery
HALF_PX = TRACE.height // 2 - 8
TRACE_S = 30.0            # seconds of history across the trace


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
        before = m.aim
        m.crank(steps)
        if m.aim != before and self.clock - self.last_sound_at > .05:
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
        m = self.model
        span = m.AIM_RANGE_SIGMA * m.window_sigma()
        if span <= 0:
            return MID_Y
        return round(MID_Y - (price - m.price) / span * HALF_PX)

    def draw(self, s: pygame.Surface) -> None:
        m = self.model
        s.fill(NAVY)
        label(s, 'BOX RUN', 14, 6, 22, CREAM)
        label(s, f'{format_usdc(m.wallet.balance)} {m.wallet.funding.name}', 268, 11, 16, MINT)
        pygame.draw.line(s, GRID, (14, 34), (466, 34))
        if self.wallet_open:
            self.draw_wallet(s)
            return
        if not m.started:
            label(s, f'{self.feed.name} / PAPER', 14, 40, 15, MUTED)
            label(s, 'WAITING FOR THE FIRST PRICE...', 240, 150, 20, YELLOW, True)
            footer(s, '< HOME', 'BUY 10 >')
            return
        label(s, f'ETH ${m.price:,.2f}', 14, 40, 20, CREAM)
        left = m.remaining(self.clock)
        bell = RED if left <= 3 else YELLOW
        if m.settling:
            label(s, 'SETTLING', 356, 42, 18, RED)
        else:
            label(s, f'{int(left):02d}s', 402, 38, 26, bell)
            label(s, 'BELL', 356, 44, 14, MUTED)
        self.draw_chart(s)
        self.draw_status(s)
        footer(s, '< HOME', 'BUY 10 >' if m.can_buy() else 'LOAD >')

    def draw_chart(self, s: pygame.Surface) -> None:
        m = self.model
        for rect in (TRACE, THIS_COL, NEXT_COL):
            pygame.draw.rect(s, PANEL, rect)
        label(s, 'THIS 20s', THIS_COL.x + 4, 68, 12, MUTED)
        label(s, 'NEXT 20s', NEXT_COL.x + 4, 68, 12, MUTED)
        # Spot line across everything: the box is judged against this level.
        for x in range(TRACE.left, NEXT_COL.right, 8):
            pygame.draw.line(s, GRID, (x, MID_Y), (x + 4, MID_Y), 1)

        clip = s.get_clip()
        s.set_clip(TRACE)
        points = [(TRACE.right - round((self.clock - t) / TRACE_S * TRACE.width), self.y_of(p))
                  for t, p in m.history if self.clock - t <= TRACE_S]
        if len(points) > 1:
            pygame.draw.lines(s, CREAM, False, points, 2)
        s.set_clip(clip)

        flashing = self.clock < self.flash_until and m.last is not None
        if m.live is not None and m.live.stake:
            self.draw_box(s, THIS_COL, m.live.low, m.live.high, YELLOW,
                          stake=m.live.stake, multiple=m.live.multiple)
        elif flashing:
            self.draw_result(s)
        # The aim cursor is always live. With the next window already bought it
        # takes half the column and aims at the window after that.
        aim_col = NEXT_COL if m.pending is None else BET_COL
        if m.pending is not None:
            self.draw_box(s, BET_COL, m.pending.low, m.pending.high, CREAM,
                          stake=m.pending.stake, multiple=m.pending.multiple)
            aim_col = AIM_COL
            label(s, 'AIM', AIM_COL.x + 2, 82, 12, MUTED)
        aim = pygame.Rect(aim_col.x + 2, self.y_of(m.aim + m.half), aim_col.width - 4,
                          max(6, self.y_of(m.aim - m.half) - self.y_of(m.aim + m.half)))
        dashed_rect(s, aim, YELLOW if m.pending is None else MUTED)
        # Multiples sit on the column floor, never on a box that may be anywhere.
        quote = m.quote(m.aim, self.clock)
        label(s, f'{quote:.1f}x', aim_col.x + 2, aim_col.bottom - 18, 14,
              YELLOW if m.pending is None else MUTED)

    def draw_box(self, s: pygame.Surface, col: pygame.Rect, low: float, high: float,
                 color: tuple, stake: int = 0, multiple: float = 0.0) -> None:
        top = self.y_of(high)
        rect = pygame.Rect(col.x + 2, top, col.width - 4, max(6, self.y_of(low) - top))
        tint = tuple(int(c * .18 + PANEL[i] * .82) for i, c in enumerate(color))
        pygame.draw.rect(s, tint, rect)
        pygame.draw.rect(s, color, rect, 3)
        if stake:
            label(s, format_usdc(stake, 0), rect.x + 4, rect.centery - 8, 15, color)
            label(s, f'{multiple:.1f}x', col.x + 2, col.bottom - 18, 14, color)

    def draw_result(self, s: pygame.Surface) -> None:
        """Flash the box that just settled, so you see where the price landed."""
        result = self.model.last
        color = MUTED if result.voided else (MINT if result.hit else RED)
        self.draw_box(s, THIS_COL, result.low, result.high, color)
        word = 'VOID' if result.voided else ('HIT' if result.hit else 'MISS')
        # A landed price sits inside the box, so put the word above it there and
        # at the price itself when the box was missed.
        y = self.y_of(result.high) - 22 if result.hit else self.y_of(result.price) - 9
        label(s, word, THIS_COL.centerx, max(THIS_COL.y + 16, y), 19, color, True)

    def draw_status(self, s: pygame.Surface) -> None:
        m = self.model
        result = m.last
        if self.clock < self.message_until:
            text, color = self.message, MINT
        elif result is not None and self.clock < self.flash_until + 3:
            if result.voided:
                text, color = f'VOID / STAKE {format_usdc(result.stake, 0)} BACK', MUTED
            else:
                text = (f'HIT {format_usdc(result.payout)} @ {result.multiple:.1f}x'
                        if result.hit else f'MISS -{format_usdc(result.stake, 0)}')
                color = MINT if result.hit else RED
        elif m.pending is None:
            text, color = 'CRANK / A BUYS THE NEXT 20s', MUTED
        else:
            text, color = 'A ADDS 10 TO THE NEXT BOX', MUTED
        label(s, text[:30], 14, 244, 14, color)
        label(s, f'AT RISK {format_usdc(m.staked, 0)}', 14, 259, 13, CREAM)
        if m.rounds:
            label(s, f'HITS {m.hits}/{m.rounds}', 170, 259, 13, MUTED)
        label(s, f'BOX {2 * m.half:,.2f} WIDE', 300, 259, 13, MUTED)

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
