"""TICK launcher. One cartridge (BOX RUN) plus the money loader.

The launcher is an attract screen: the same night city as the game, with the
rider running a scripted demo over it — a hit, a backflip, a hat trick and a
greedy miss, on loop — so the machine shows what it does before you touch it.
The demo line is made up; the ETH ticker in the corner is the live feed.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

import pygame

from games.box import GLOW, POST, SHADE, dashed_rect, say, say_right
from games.box_model import BoxModel
from games.box_scene import Floaters, Rider, Skyline, Sparks, mix
from input import InputAction, event_position
from ui import NAVY, PANEL, GRID, CREAM, YELLOW, MINT, RED, MUTED, font, footer
from wallet import format_usdc


@dataclass(frozen=True)
class LauncherItem:
    id: str
    title: str


TITLES = {'box': ('BOX RUN', 'WHERE WILL ETH LAND?',
                  f'CRANK THE BOX. A BUYS {BoxModel.WINDOW_S:.0f}s.'),
          'rush': ('RUSH', 'KEEP IT TURNING.', 'THE DIAL IS THE BET.')}

HORIZON, STREET_BOTTOM = 242, 274
RIDER_X = 132
SPEED = 46.0            # px/s: livelier than the game's 16, it is a trailer
SPACING = 150           # one demo box every ~3 seconds
FIRST = 330             # where box 0 sits when the launcher opens
BASE = 202              # the demo line's resting height
BOX_W, BOX_HALF = 36, 11
MISS_OFF = 28
# hop, backflip, hat trick, then the greedy far box that misses and puts the fire out
MULTS = (2.1, 5.4, 2.6, 8.9)
STAKE = 10
LOGO_LOW = (196, 104, 28)


def noise(i: int) -> float:
    """Cheap repeatable jitter in [-.5, .5], so the line looks like ticks."""
    return (((i * 2654435761) & 0xffffffff) >> 16 & 0xff) / 255 - .5


def ground(wx: float, jag: bool = True) -> float:
    """Screen y of the demo price line at world x."""
    y = BASE + 11 * math.sin(wx * .021) + 7 * math.sin(wx * .0537 + 1.3)
    if not jag:
        return y
    i = math.floor(wx / 6)
    f = wx / 6 - i
    return y + 6 * (noise(i) * (1 - f) + noise(i + 1) * f)


def demo_box(k: int) -> tuple[float, float, bool, float]:
    """(world x, centre y, hit, multiple) of the k-th demo box."""
    wx = FIRST + k * SPACING
    y = ground(wx)
    hit = k % 4 != 3
    if not hit:
        y += MISS_OFF if y < BASE else -MISS_OFF
    return wx, y, hit, MULTS[k % 4]


class HomeScreen:
    def __init__(self, game_id: str = 'box', game=None) -> None:
        self.focus = 0
        self.game_id = game_id
        self.game = game                # for the live ticker and balance, if any
        self.t = 0.0
        self.streak = 0
        self.next_box = 0
        self.skyline = Skyline(480, HORIZON, STREET_BOTTOM, seed=3)
        self.rider = Rider()
        self.sparks = Sparks()
        self.floaters = Floaters()
        self.shade = pygame.Surface((RIDER_X + 8, HORIZON), pygame.SRCALPHA)
        self.glyphs: dict[tuple[str, tuple], pygame.Surface] = {}

    def row_rect(self, index: int) -> pygame.Rect:
        return pygame.Rect(16, 246, 216, 24) if index == 0 else pygame.Rect(248, 246, 216, 24)

    def focused_item(self) -> LauncherItem:
        if self.focus:
            return LauncherItem('wallet', 'Load USDC')
        return LauncherItem(self.game_id, TITLES[self.game_id][0])

    def handle_action(self, action: InputAction) -> str | None:
        if action in (InputAction.UP, InputAction.DOWN):
            self.focus = 1 - self.focus
        elif action == InputAction.A:
            return self.focused_item().id if self.focus else 'game'
        elif action in (InputAction.B, InputAction.QUIT):
            return 'quit'
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if self.row_rect(1).collidepoint(pos):
            return 'wallet'
        if self.row_rect(0).collidepoint(pos) or 30 <= pos[1] < HORIZON:
            return 'game'               # the whole scene is the play button
        if pos[1] >= 274:
            return self.handle_action(InputAction.A if pos[0] >= 240 else InputAction.B)
        return None

    # ---- the demo run ----------------------------------------------------
    @property
    def scroll(self) -> float:
        return self.t * SPEED

    @property
    def demo(self) -> bool:
        return self.game_id == 'box'

    def update(self, dt: float) -> None:
        self.t += dt
        wheel_x = self.scroll + RIDER_X
        while self.demo and demo_box(self.next_box)[0] <= wheel_x:
            self.settle(self.next_box)
            self.next_box += 1
        slope = math.degrees(math.atan2(ground(wheel_x - 12, False) - ground(wheel_x, False), 12))
        self.rider.update(dt, slope, self.streak >= 3)
        if self.streak >= 3:
            self.sparks.flame(*self.rider.back(RIDER_X, ground(wheel_x)), -SPEED)
        self.sparks.update(dt)
        self.floaters.update(dt)

    def settle(self, k: int) -> None:
        wx, _, hit, mult = demo_box(k)
        y = ground(wx)
        if hit:
            self.streak += 1
            self.sparks.burst(RIDER_X, y, 18, (YELLOW, YELLOW, CREAM), 170, 1.0, 5,
                              square=True, drift=-SPEED)
            self.floaters.add(f'+{STAKE * mult:.2f}', RIDER_X + 58, y - 30, MINT, 18, rise=18)
            if self.streak == 3:
                self.floaters.add('HAT TRICK!', 350, 166, YELLOW, 24, life=2.0, rise=10)
                self.sparks.burst(*self.rider.back(RIDER_X, y), 24,
                                  (YELLOW, (255, 138, 40), RED), 150, .6, 5, gravity=-60)
            self.rider.react('flip' if mult >= 5 else ('cheer' if self.streak == 3 else 'hop'))
            return
        if self.streak >= 3:
            self.sparks.burst(*self.rider.back(RIDER_X, y), 16, ((96, 104, 112), (70, 76, 84)),
                              60, 1.0, 6, gravity=-50)
        self.streak = 0
        self.sparks.burst(RIDER_X, y, 14, (RED, (140, 60, 56)), 150, .8, 4, square=True,
                          drift=-SPEED)
        self.floaters.add('MISS', RIDER_X + 58, y - 30, RED, 18, rise=18)
        self.rider.react('wobble')

    # ---- drawing ---------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        scroll = self.scroll
        self.skyline.draw(surface, scroll, self.t)
        self.draw_title(surface)
        if self.demo:
            self.draw_boxes(surface)
        self.draw_trace(surface)
        self.sparks.draw(surface)
        self.rider.draw(surface, RIDER_X, ground(scroll + RIDER_X), scroll / Rider.WHEEL)
        self.floaters.draw(surface)
        self.draw_top(surface)
        self.draw_menu(surface)
        footer(surface, '< QUIT', 'LOAD >' if self.focus else 'PLAY >')

    def glyph(self, ch: str, color: tuple) -> pygame.Surface:
        key = (ch, color)
        if key not in self.glyphs:
            self.glyphs[key] = font(46).render(ch, False, color)
        return self.glyphs[key]

    def draw_title(self, s: pygame.Surface) -> None:
        """Chunky arcade logo, each letter bobbing a beat behind the last."""
        title, line, hint = TITLES[self.game_id]
        big = font(46)
        x0 = 240 - big.size(title)[0] // 2
        for i, ch in enumerate(title):
            if ch == ' ':
                continue
            x = x0 + big.size(title[:i])[0]
            y = 32 + round(3 * math.sin(self.t * 3.2 - i * .55))
            s.blit(self.glyph(ch, (0, 0, 0)), (x + 3, y + 7))
            s.blit(self.glyph(ch, LOGO_LOW), (x, y + 4))
            s.blit(self.glyph(ch, YELLOW), (x, y))
        say(s, line, 240, 94, 16, CREAM, True)
        say(s, hint, 240, 116, 13, MUTED, True)

    def draw_top(self, s: pygame.Surface) -> None:
        say(s, 'TICK', 10, 5, 20, CREAM)
        say(s, 'ARCADE', 64, 11, 12, MUTED)
        m = getattr(self.game, 'model', None)
        if not self.demo or m is None or not getattr(m, 'started', False):
            say_right(s, 'READING ETH...' if self.demo else 'CRANK POWERED', 470, 10, 13, MUTED)
            return
        move = f'{m.move:+,.2f}'
        say_right(s, move, 470, 11, 13, MINT if m.move >= 0 else RED)
        price_right = 470 - font(13).size(move)[0] - 8
        price = f'ETH ${m.price:,.2f}'
        say_right(s, price, price_right, 8, 16, CREAM)
        if int(self.t * 2) % 2 == 0:            # the feed is live
            pygame.draw.circle(s, RED, (price_right - font(16).size(price)[0] - 9, 17), 4)

    def draw_trace(self, s: pygame.Surface) -> None:
        scroll = self.scroll
        ride_y = ground(scroll + RIDER_X)
        points = [(i * 6 - scroll, ground(i * 6))
                  for i in range(math.floor(scroll / 6) - 1, math.floor((scroll + RIDER_X - 3) / 6) + 1)]
        points.append((RIDER_X, ride_y))
        self.shade.fill((0, 0, 0, 0))
        pygame.draw.polygon(self.shade, SHADE,
                            points + [(RIDER_X, HORIZON), (points[0][0], HORIZON)])
        s.blit(self.shade, (0, 0))
        pygame.draw.lines(s, GLOW, False, points, 6)
        pygame.draw.lines(s, CREAM, False, points, 2)
        for x in range(RIDER_X + 16, 480, 8):
            pygame.draw.line(s, (150, 146, 128), (x, round(ride_y)), (x + 3, round(ride_y)))

    def draw_boxes(self, s: pygame.Surface) -> None:
        """Live box, the one bought behind it, then a cursor — like a real run."""
        scroll = self.scroll
        for k in range(max(0, self.next_box - 3), self.next_box + 4):
            wx, y, hit, mult = demo_box(k)
            x = wx - scroll
            if not -BOX_W < x < 480 + BOX_W:
                continue
            for py in range(150, HORIZON, 8):
                pygame.draw.line(s, POST, (round(x), py), (round(x), py + 3))
            rect = pygame.Rect(round(x - BOX_W / 2), round(y - BOX_HALF), BOX_W, 2 * BOX_HALF)
            if k < self.next_box:
                fade = min(1.0, max(0.0, (RIDER_X - x) / 140))
                color = mix(MINT if hit else RED, POST, fade)
                self.glass(s, rect, color, round(70 * (1 - fade)))
                pygame.draw.rect(s, color, rect, 3, border_radius=3)
                pygame.draw.circle(s, color, (round(x), round(ground(wx))), 3)
                continue
            ahead = k - self.next_box
            if ahead == 0:
                close = x - RIDER_X < 60
                urgent = close and int(self.t * 6) % 2 == 0
                self.glass(s, rect, YELLOW, 96 if close else 40)
                pygame.draw.rect(s, YELLOW, rect, 4 if urgent else 3, border_radius=3)
                self.tag(s, rect, f'{STAKE} @ {mult:.1f}x', YELLOW)
            elif ahead == 1:
                self.glass(s, rect, CREAM, 48)
                pygame.draw.rect(s, CREAM, rect, 3, border_radius=3)
                self.tag(s, rect, f'{STAKE} @ {mult:.1f}x', CREAM)
            else:
                self.glass(s, rect, YELLOW, 18)
                dashed_rect(s, rect, YELLOW)
                self.tag(s, rect, f'{mult:.1f}x', YELLOW)

    @staticmethod
    def glass(s: pygame.Surface, rect: pygame.Rect, color: tuple, alpha: int) -> None:
        if alpha > 0:
            pane = pygame.Surface(rect.size, pygame.SRCALPHA)
            pane.fill((*color, alpha))
            s.blit(pane, rect)

    @staticmethod
    def tag(s: pygame.Surface, rect: pygame.Rect, text: str, color: tuple) -> None:
        say(s, text, rect.centerx, rect.top - 16, 13, color, True)

    def draw_menu(self, s: pygame.Surface) -> None:
        """PLAY and LOAD sit on the street, where the game keeps its status line."""
        pulse = .5 + .5 * math.sin(self.t * 6)
        m = getattr(self.game, 'model', None)
        wallet = getattr(m, 'wallet', None)
        for index in (0, 1):
            rect = self.row_rect(index)
            on = self.focus == index
            if on:
                pygame.draw.rect(s, mix(YELLOW, CREAM, .3 * pulse), rect, border_radius=5)
            else:
                pygame.draw.rect(s, PANEL, rect, border_radius=5)
                pygame.draw.rect(s, GRID, rect, 1, border_radius=5)
            ink = NAVY if on else (CREAM if index == 0 else MINT)
            text = 'PLAY' if index == 0 else 'LOAD USDC'
            tx = rect.x + 30
            s.blit(font(16).render(text, False, ink), (tx, rect.y + 3))
            if index == 0:
                nudge = round(2 * pulse) if on else 0
                pygame.draw.polygon(s, ink, [(rect.x + 12 + nudge, rect.y + 6),
                                             (rect.x + 12 + nudge, rect.y + 18),
                                             (rect.x + 21 + nudge, rect.y + 12)])
                if on and int(self.t * 2) % 2 == 0:
                    press = font(12).render('PRESS A', False, NAVY)
                    s.blit(press, (rect.right - press.get_width() - 10, rect.y + 6))
            else:
                pygame.draw.circle(s, ink, (rect.x + 16, rect.centery), 6, 2)
                if wallet is not None:
                    bal = font(13).render(format_usdc(wallet.balance), False,
                                          NAVY if on else MUTED)
                    s.blit(bal, (rect.right - bal.get_width() - 10, rect.y + 5))


def handle_home_events(home: HomeScreen, events: list, actions: list[InputAction]) -> str | None:
    for event in events:
        pos = event_position(event)
        if pos is not None:
            target = home.handle_touch(pos)
            if target:
                return target
    for action in actions:
        target = home.handle_action(action)
        if target:
            return target
    return None
