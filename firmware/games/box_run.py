"""Native 480×320 BOX RUN renderer, sound and input adapter."""
from __future__ import annotations

from array import array
from functools import lru_cache
import math

import pygame

from games.box_run_model import BoxRunModel
from input import InputAction, event_position

NAVY = (12, 25, 36)
PANEL = (22, 40, 51)
GRID = (30, 50, 61)
CREAM = (244, 236, 210)
MUTED = (144, 167, 173)
YELLOW = (255, 204, 72)
MINT = (127, 228, 184)
RED = (233, 100, 91)


@lru_cache(maxsize=12)
def font(size: int) -> pygame.font.Font:
    return pygame.font.SysFont('menlo,dejavusansmono,monospace', size, bold=True)


def label(s: pygame.Surface, words: str, x: int, y: int, size: int = 16,
          color: tuple = CREAM, center: bool = False) -> None:
    art = font(size).render(words, False, color)
    s.blit(art, art.get_rect(midtop=(x, y)) if center else (x, y))


def diamond(s: pygame.Surface, x: int, y: int, color: tuple = CREAM) -> None:
    pygame.draw.polygon(s, color, [(x, y-11), (x+7, y), (x, y+4), (x-7, y)])
    pygame.draw.polygon(s, color, [(x-7, y+3), (x, y+13), (x+7, y+3), (x, y+7)])


def footer(s: pygame.Surface, back: str, go: str) -> None:
    pygame.draw.rect(s, PANEL, (0, 274, 480, 46))
    pygame.draw.circle(s, RED, (20, 297), 6)
    pygame.draw.circle(s, YELLOW, (254, 297), 6)
    label(s, back, 34, 286, 16)
    label(s, go, 268, 286, 16)


class Sounds:
    def __init__(self) -> None:
        self.clips: dict[str, pygame.mixer.Sound] = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            rate, sample_format, channels = pygame.mixer.get_init()
            if sample_format != -16:
                return
            for name, notes in {
                'move': [(330, .025)], 'select': [(550, .05), (740, .07)],
                'lock': [(220, .06), (440, .06), (880, .10)],
                'tick': [(660, .055)],
                'hit': [(523, .10), (659, .10), (784, .10), (1047, .18)],
                'miss': [(330, .12), (247, .12), (165, .20)],
            }.items():
                samples = array('h')
                for hz, duration in notes:
                    count = int(rate * duration)
                    for i in range(count):
                        envelope = min(1, i / max(1, rate*.004), (count-i) / max(1, rate*.02))
                        v = int(1800 * envelope * (1 if math.sin(2*math.pi*hz*i/rate) >= 0 else -1))
                        samples.extend([v] * channels)
                self.clips[name] = pygame.mixer.Sound(buffer=samples)
        except pygame.error:
            # Audio is optional on a headless Pi or a device without a speaker.
            pass

    def play(self, name: str) -> None:
        if name in self.clips:
            self.clips[name].play()


class BoxRunGame:
    def __init__(self, seed: int | None = None, sound: bool = True) -> None:
        self.model = BoxRunModel(seed)
        self.sounds = Sounds() if sound else None
        self.animation = 0.0
        self.result_age = 0.0
        self.held: dict[int, float] = {}
        # Decoration only, never reused as a real price/history or outcome.
        self.preview = [math.sin(i*.43)*2.6 + math.sin(i*1.47)*.8 for i in range(50)]

    def enter(self) -> None:
        self.held.clear()
        if self.model.phase != 'running':
            self.model.reset_prediction()

    def play(self, name: str) -> None:
        if self.sounds:
            self.sounds.play(name)

    def handle_action(self, action: InputAction) -> str | None:
        m = self.model
        before = m.phase
        if action == InputAction.QUIT:
            return 'quit'
        if action in (InputAction.UP, InputAction.DOWN):
            previous = (m.center, m.half_width)
            m.adjust(1 if action == InputAction.UP else -1)
            if previous != (m.center, m.half_width):
                self.play('move')
        elif action == InputAction.A:
            # Don't carry a held confirmation into the result screen.
            if m.phase == 'result' and self.result_age < .5:
                return None
            m.confirm()
        elif action == InputAction.B:
            if m.back():
                self.held.clear()
                return 'home'
        if before != m.phase:
            self.held.clear()
            self.play('lock' if m.phase == 'running' else 'select')
        return None

    def update(self, dt: float) -> None:
        self.animation += dt
        for key in list(self.held):
            self.held[key] -= dt
            if self.held[key] <= 0:
                self.handle_action(InputAction.UP if key in (pygame.K_UP, pygame.K_w) else InputAction.DOWN)
                if key in self.held:
                    self.held[key] = .07
        before = self.model.phase
        remaining = self.model.remaining
        self.model.update(dt)
        if before == 'running' and self.model.phase == 'result':
            self.result_age = 0
            self.play('hit' if self.model.hit else 'miss')
        elif self.model.phase == 'result':
            self.result_age += dt
        elif self.model.phase == 'running' and self.model.remaining != remaining and 0 < self.model.remaining <= 3:
            self.play('tick')

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        x, y = pos
        if y >= 274:
            return self.handle_action(InputAction.B if x < 240 else InputAction.A)
        if 90 <= y < 255 and self.model.phase in ('aim', 'size'):
            return self.handle_action(InputAction.UP if y < 174 else InputAction.DOWN)
        return None

    def draw(self, s: pygame.Surface, _fonts: dict | None = None) -> None:
        m = self.model
        s.fill(NAVY)
        label(s, 'BOX RUN', 14, 7, 20)
        label(s, 'SIM / PRACTICE', 280, 11, 16, MINT)
        pygame.draw.line(s, GRID, (14, 35), (466, 35))
        if m.phase == 'review':
            self.draw_review(s)
        elif m.phase == 'empty':
            diamond(s, 240, 87, YELLOW)
            label(s, 'OUT OF CREDITS', 240, 120, 28, center=True)
            label(s, 'Refill 100 practice credits?', 240, 164, 16, MUTED, True)
            label(s, 'No money. No automatic refill.', 240, 195, 15, MUTED, True)
            footer(s, '< HOME', 'REFILL >')
        else:
            self.draw_chart(s)

    def draw_review(self, s: pygame.Surface) -> None:
        m = self.model
        label(s, 'LOCK YOUR BOX', 240, 45, 25, YELLOW, True)
        pygame.draw.rect(s, PANEL, (16, 87, 448, 135), border_radius=5)
        for x, title, value in [(34, 'STAKE', '10'), (181, 'SECONDS', '20'), (326, 'RETURN', str(m.total_return))]:
            label(s, title, x, 101, 16, MUTED)
            label(s, value, x, 122, 39, CREAM)
        label(s, 'CREDITS', 34, 172, 15, MUTED)
        label(s, 'TOTAL IF HIT', 326, 172, 15, MINT)
        label(s, f'BAL {m.balance}   HIT +{m.total_return-10} / MISS -10', 240, 231, 16, CREAM, True)
        footer(s, '< CHANGE', 'LOCK >')

    def draw_chart(self, s: pygame.Surface) -> None:
        m = self.model
        running = m.phase == 'running'
        result = m.phase == 'result'
        setup = not running and not result
        color = MINT if result and m.hit else (RED if result else YELLOW)
        if setup:
            title = '01 / AIM YOUR BOX' if m.phase == 'aim' else '02 / SET BOX SIZE'
            label(s, title, 14, 45, 21, YELLOW)
            label(s, 'UP / DOWN', 354, 49, 15, MUTED)
            label(s, 'Predict the end price' if m.phase == 'aim' else 'Narrower box = bigger return', 14, 74, 15, MUTED)
        elif running:
            label(s, 'BOX LOCKED', 14, 45, 22, YELLOW)
            label(s, 'ETH / SIMULATED', 14, 75, 15, MUTED)
            label(s, f'{m.remaining:02d}s', 369, 40, 36, YELLOW)
        else:
            label(s, 'HIT!' if m.hit else 'MISS', 14, 43, 31, color)
            label(s, f'{m.net:+d} CREDITS', 241, 48, 25, color)
            label(s, 'Inside at expiry.' if m.hit else 'Outside at expiry.', 14, 79, 15, MUTED)
        plot = pygame.Rect(14, 104, 452, 130)
        pygame.draw.rect(s, PANEL, plot)
        center = m.center if setup else m.locked_center
        half_width = m.half_width if setup else m.locked_width
        # Fit the chosen box during setup, then freeze scale with the locked box.
        # A rare excursion outside the view gets an explicit OFF SCALE marker.
        scale = 58 / max(20, abs(center) + half_width + 3)
        price_y = lambda price: round(169 - price * scale)
        for y in (121, 169, 217):
            pygame.draw.line(s, GRID, (14, y), (465, y))
        for x in (74, 154, 234, 314):
            pygame.draw.line(s, GRID, (x, 104), (x, 233))
        target = pygame.Rect(365, price_y(center+half_width), 76, max(8, round(2*half_width*scale)))
        tint = tuple(int(c*.16 + PANEL[i]*.84) for i,c in enumerate(color))
        pygame.draw.rect(s, tint, target)
        pygame.draw.rect(s, color, target, 3)
        for y in range(104, 234, 10):
            pygame.draw.line(s, MUTED, (403, y), (403, y+4))
        clip = s.get_clip()
        s.set_clip(plot)
        if setup:
            points = [(24+i*5, price_y(v)) for i,v in enumerate(self.preview)]
            pygame.draw.lines(s, CREAM, False, points, 3)
            for x in range(279, 362, 12):
                pygame.draw.rect(s, MUTED, (x, 168, 4, 3))
            diamond(s, 27, 123, MUTED)
        else:
            points = [(24+round(i/m.TICKS*379), price_y(p)) for i,p in enumerate(m.path)]
            if len(points) > 1:
                pygame.draw.lines(s, CREAM, False, points, 3)
            x,y = points[-1]
            diamond(s, x, max(116, min(221,y)), color if result else CREAM)
            if y < 116 or y > 221:
                label(s, 'OFF SCALE', 22, 108 if y < 116 else 212, 13, YELLOW)
        s.set_clip(clip)
        if setup:
            # Clear direction cues, without requiring a keyboard glyph font.
            x = 451
            pygame.draw.polygon(s, YELLOW, [(x,146),(x-5,154),(x+5,154)])
            pygame.draw.polygon(s, YELLOW, [(x,192),(x-5,184),(x+5,184)])
            label(s, f'10 IN / {m.total_return} BACK IF HIT', 14, 245, 16, CREAM)
            label(s, f'BAL {m.balance}', 366, 245, 15, MINT)
            footer(s, '< HOME' if m.phase == 'aim' else '< AIM', 'SIZE >' if m.phase == 'aim' else 'REVIEW >')
        elif running:
            label(s, f'10 IN / {m.locked_return} BACK IF HIT', 14, 245, 16)
            pygame.draw.rect(s, GRID, (16, 284, 448, 5))
            pygame.draw.rect(s, YELLOW, (16, 284, round(448*m.elapsed/m.DURATION), 5))
            label(s, 'LOCKED UNTIL EXPIRY', 240, 296, 15, MUTED, True)
        else:
            label(s, f'BALANCE {m.balance}', 14, 245, 17, MINT)
            label(s, f'HITS {m.hits}/{m.rounds}', 345, 245, 16, MUTED)
            footer(s, '< HOME', 'AGAIN >')
            if m.hit and self.result_age < 1.6:
                for i in range(14):
                    x = 30 + (i*79)%424
                    y = 105 + int((i*29 + self.result_age*55)%120)
                    pygame.draw.rect(s, MINT if i%2 else YELLOW, (x,y,3,3))


def handle_box_events(game: BoxRunGame, events: list, actions: list[InputAction]) -> str | None:
    for event in events:
        if event.type == pygame.WINDOWFOCUSLOST:
            game.held.clear()
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
            game.held[event.key] = .30
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
