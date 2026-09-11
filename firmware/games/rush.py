"""RUSH: crank the dial and ride the market. Renderer, sound and input adapter."""
from __future__ import annotations
import math
import os
import time
from typing import Callable

import pygame

from games.rush_model import RushModel
from input import InputAction, event_position
from markets.feed import open_feed
from ui import NAVY, PANEL, GRID, CREAM, MUTED, YELLOW, MINT, RED, Sounds, label, diamond, footer
from wallet import LOAD_CHOICES, MICRO, DemoFunding, UsdcFunding, Wallet, format_usdc


def rider(s: pygame.Surface, x: int, y: int, boost: float, clock: float) -> None:
    """Tiny pixel motorbike; the exhaust plume tracks how hard the hand is going."""
    for wheel in (x-15, x+18):
        pygame.draw.circle(s, CREAM, (wheel, y), 8)
        pygame.draw.circle(s, NAVY, (wheel, y), 4)
        if int(clock*12) % 2:
            pygame.draw.line(s, MUTED, (wheel-4, y), (wheel+4, y), 2)
    pygame.draw.lines(s, YELLOW, False, [(x-15, y), (x-3, y-13), (x+8, y), (x-15, y)], 4)
    pygame.draw.line(s, YELLOW, (x+8, y), (x+18, y-15), 4)
    pygame.draw.line(s, CREAM, (x+12, y-18), (x+22, y-18), 3)
    pygame.draw.rect(s, MINT, (x-5, y-29, 12, 13))
    pygame.draw.line(s, MINT, (x+4, y-24), (x+15, y-18), 4)
    pygame.draw.rect(s, CREAM, (x-3, y-39, 13, 11))
    pygame.draw.rect(s, YELLOW, (x-5, y-41, 17, 6))
    pygame.draw.rect(s, NAVY, (x+5, y-34, 6, 3))
    if boost > .12:
        length = int(8 + boost*22 + 4*math.sin(clock*30))
        pygame.draw.polygon(s, YELLOW, [(x-15, y-14), (x-24-length, y-10), (x-20, y-4)])
        pygame.draw.polygon(s, RED, [(x-21, y-12), (x-20-length*.7, y-10), (x-22, y-6)])


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


class RushGame:
    def __init__(self, seed: int | None = None, sound: bool = True,
                 source: str | None = None, wallet: Wallet | None = None,
                 clock: Callable[[], float] | None = None) -> None:
        source = source or os.environ.get('TICK_MARKET_SOURCE', 'sim')
        self.feed = open_feed(source, seed)
        self.model = RushModel(wallet or build_wallet())
        self.sounds = Sounds() if sound else None
        self.source = source
        # Wall-clock monotonic in play: live ticks are stamped on the same
        # clock, so staleness stays honest. Tests inject their own.
        self._now = clock or time.monotonic
        self.clock = self._now()
        self.animation = 0.0
        self.distance = 0.0
        self.held: dict[int, float] = {}
        self.wallet_open = False
        self.amount_index = 1
        self.message = ''
        self.message_until = 0.0
        self.last_sound_at = 0.0

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
        # Never cover a live position with a menu.
        if not self.model.active:
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

    def crank(self, direction: int) -> None:
        """One detent of dial motion — the only gameplay input there is."""
        m = self.model
        if m.crank(direction, self.clock):
            self.play('lock')
            self.message = ''
        elif m.phase == 'ready' and not m.can_ride():
            self.note(f'LOAD USDC TO RIDE / NEED {format_usdc(m.STAKE, 0)}')
        elif m.phase == 'ready' and m.arm and not m.fresh(self.clock):
            self.note('WAITING FOR A FRESH PRICE')
        if m.active and self.clock - self.last_sound_at > .09:
            self.play('move')
            self.last_sound_at = self.clock

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
            self.open_wallet()
        elif action == InputAction.B:
            if self.model.active:
                self.model.bail(self.clock)
                self.held.clear()
            else:
                self.held.clear()
                return 'home'
        return None

    def update(self, dt: float) -> None:
        self.clock = self._now()
        self.animation += dt
        m = self.model
        rides_before = m.rides
        for key in list(self.held):
            self.held[key] -= dt
            if self.held[key] <= 0:
                self.crank(1 if key in (pygame.K_UP, pygame.K_w) else -1)
                if key in self.held:
                    self.held[key] = .06
        # Age the flywheel before new quotes arrive: a stopped hand must not
        # get one more repricing at the leverage it no longer holds.
        m.update(dt, self.clock)
        for tick in self.feed.poll(dt, self.clock):
            m.on_tick(tick, self.clock)
        if m.rides != rides_before:
            self.play('hit' if m.last_pnl is not None and m.last_pnl >= 0 else 'miss')
            self.held.clear()
        self.distance += dt * (12 + 115*m.throttle if m.active else 8)

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        x, y = pos
        if y >= 274:
            return self.handle_action(InputAction.B if x < 240 else InputAction.A)
        if self.wallet_open:
            return self.handle_action(InputAction.UP if x >= 240 else InputAction.DOWN)
        if y < 38 and x >= 260:
            self.open_wallet()
        elif 105 <= y < 242:
            # Top half of the plot cranks forward (long), bottom half back.
            return self.handle_action(InputAction.UP if y < 174 else InputAction.DOWN)
        return None

    # ---- drawing ---------------------------------------------------------
    def draw(self, s: pygame.Surface) -> None:
        m = self.model
        s.fill(NAVY)
        label(s, 'RUSH', 14, 6, 23, CREAM)
        funding = m.wallet.funding.name
        label(s, f'{format_usdc(m.wallet.balance)} {funding}', 239, 11, 16, MINT)
        pygame.draw.line(s, GRID, (14, 36), (466, 36))
        if self.wallet_open:
            self.draw_wallet(s)
            return
        label(s, f'{self.feed.name} / PAPER', 14, 43, 15, MUTED)
        if m.tick:
            asset = self.feed.asset
            label(s, f'{asset.symbol} ${asset.format(m.tick.price)}', 242, 43, 17, CREAM)
        else:
            label(s, 'CONNECTING...', 258, 43, 16, YELLOW)
        if m.active:
            label(s, f'{m.pnl:+.4f}', 14, 63, 29, MINT if m.pnl >= 0 else RED)
            label(s, 'USDC', 179, 77, 14, MUTED)
            label(s, f'{m.leverage:04.1f}x', 354, 64, 28, YELLOW)
        else:
            label(s, 'LONG' if m.side == 1 else 'SHORT', 14, 68, 23, YELLOW)
            label(s, 'CRANK TO RIDE', 266, 73, 17, CREAM)
        self.draw_world(s)
        self.draw_gauge(s)
        if m.tick and not m.fresh(self.clock):
            pygame.draw.rect(s, NAVY, (74, 135, 332, 36))
            label(s, 'PRICE STALE', 240, 140, 23, RED, True)

    def draw_gauge(self, s: pygame.Surface) -> None:
        """Flywheel while riding, arming charge while ready — same 20 cells."""
        m = self.model
        pygame.draw.rect(s, PANEL, (14, 211, 452, 24), border_radius=3)
        filled = round((m.throttle if m.active else m.arm_progress) * 20)
        for i in range(20):
            lit = (YELLOW if i < 15 else RED) if m.active else MINT
            pygame.draw.rect(s, lit if i < filled else GRID, (19+i*22, 215, 17, 16))
        if m.active:
            if m.phase == 'exit_pending':
                label(s, 'CLOSING AT NEXT PRICE', 240, 242, 16, RED, True)
            elif not m.fresh(self.clock):
                label(s, 'FEED STALE / EXPOSURE HELD', 240, 242, 16, RED, True)
            else:
                label(s, 'KEEP TURNING', 14, 243, 18, YELLOW)
                label(s, f'{int(m.elapsed):02d}s / MAX {m.MAX_LEVERAGE:.0f}x', 285, 246, 15, MUTED)
            footer(s, '< BAIL OUT', 'RIDING')
        else:
            if self.clock < self.message_until:
                text, color = self.message, MINT
            elif m.last_pnl is not None:
                text = f'{m.last_pnl:+.4f} @ {m.last_peak:.1f}x / {m.last_reason.upper()}'
                color = MINT if m.last_pnl >= 0 else RED
            else:
                text, color = 'FORWARD = LONG / BACK = SHORT', MUTED
            # Below the gauge: the meter itself says what the crank is doing.
            label(s, text[:32], 14, 243, 15, color)
            label(s, f'{format_usdc(m.STAKE, 0)} USDC IN', 355, 244, 14, CREAM)
            footer(s, '< HOME', 'LOAD >')

    def draw_world(self, s: pygame.Surface) -> None:
        m = self.model
        plot = pygame.Rect(14, 105, 452, 98)
        pygame.draw.rect(s, PANEL, plot)
        clip = s.get_clip()
        s.set_clip(plot)
        # Scenery scroll is arcade animation only, never extra price movement.
        for i in range(14):
            x = int((i*43 - self.distance*.3) % 560) - 40
            height = 15 + (i*17) % 52
            pygame.draw.rect(s, GRID, (x, 199-height, 27, height))
            if i % 3 == 0:
                pygame.draw.rect(s, (59, 74, 73), (x+9, 204-height, 4, 4))
        prices = list(m.history)
        if len(prices) > 1:
            lo, hi = min(prices), max(prices)
            span = max(hi-lo, prices[-1]*.001)
            mid = (lo+hi)/2
            points = [(14+int(i/(len(prices)-1)*451), round(170-(p-mid)/span*42))
                      for i, p in enumerate(prices)]
            pygame.draw.lines(s, CREAM, False, points, 3)
            road_y = min(points, key=lambda point: abs(point[0]-135))[1]
        else:
            road_y = 177
            pygame.draw.line(s, CREAM, (14, road_y), (466, road_y), 3)
        rider(s, 135, road_y-8, m.throttle, self.animation)
        if m.throttle > .2:
            for i in range(7):
                x = int((i*73 - self.distance*2) % 500)
                y = 110 + (i*19) % 70
                pygame.draw.line(s, MUTED, (x, y), (x+int(5+m.throttle*14), y), 1)
        if len(prices) > 1:
            diamond(s, 447, points[-1][1]-16, YELLOW)
        s.set_clip(clip)

    def draw_wallet(self, s: pygame.Surface) -> None:
        wallet = self.model.wallet
        label(s, f'LOAD {wallet.funding.name} USDC', 240, 53, 27, YELLOW, True)
        subtitle = ('Real deposit path is not wired yet.' if wallet.live
                    else 'LOCAL TEST BALANCE / NO REAL MONEY')
        label(s, subtitle, 240, 92, 15, MUTED, True)
        for i, amount in enumerate(LOAD_CHOICES):
            rect = pygame.Rect(16+i*155, 126, 140, 67)
            pygame.draw.rect(s, YELLOW if i == self.amount_index else PANEL, rect, border_radius=4)
            label(s, f'+{amount}', rect.centerx, 142, 28,
                  NAVY if i == self.amount_index else CREAM, True)
        label(s, 'UP / DOWN TO CHOOSE', 240, 208, 17, MUTED, True)
        label(s, f'{len(wallet.deposits)} LOADS THIS SESSION', 240, 240, 15, CREAM, True)
        footer(s, '< BACK', 'LOAD >')


def handle_rush_events(game: RushGame, events: list, actions: list[InputAction]) -> str | None:
    for event in events:
        if event.type == pygame.WINDOWFOCUSLOST:
            game.held.clear()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                game.open_wallet()
            elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s) and not game.wallet_open:
                # Held keys emulate a spun dial for desktop testing.
                game.held[event.key] = .10
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
