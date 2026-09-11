"""BOX RUN scenery: a night city, a one-wheel rider, and the bits that fly off.

Everything is drawn in code, like the sound: no image assets. Nothing here
knows about money or prices — box.py says where things are and what happened.

The rider balances on a single wheel because the price line is jagged. Legs or
a two-wheeled base need flat ground and would visibly clip into the line; one
wheel touches it at exactly one point, so it always looks planted.
"""
from __future__ import annotations
import math
import random

import pygame

from ui import CREAM, YELLOW, RED, font

SKY_TOP = (5, 10, 22)
SKY_LOW = (24, 40, 66)
FAR = (17, 31, 49)
NEAR = (11, 21, 34)
STREET = (8, 14, 22)
KERB = (38, 56, 70)
LANE = (52, 68, 80)
WARM = (150, 122, 58)
COOL = (66, 116, 138)
DIM = (62, 64, 54)
FLAME = (255, 138, 40)
SMOKE = (96, 104, 112)

TYRE = (30, 32, 38)
RIM = (86, 96, 106)
HUB = (176, 184, 190)
STEEL = (160, 168, 176)
GRIP = (38, 42, 48)
PANTS = (84, 130, 196)
SHIRT = (214, 74, 68)
SHIRT_FAR = (160, 52, 50)
SKIN = (240, 196, 158)
HAIR = (112, 72, 44)
SHOE = (24, 26, 30)
KEY = (255, 0, 255)


def mix(a: tuple, b: tuple, f: float) -> tuple:
    return tuple(round(x + (y - x) * f) for x, y in zip(a, b))


def rotate_point(dx: float, dy: float, degrees: float) -> tuple[float, float]:
    """Where (dx, dy) lands after pygame.transform.rotate by `degrees` (CCW)."""
    r = math.radians(degrees)
    return dx * math.cos(r) + dy * math.sin(r), -dx * math.sin(r) + dy * math.cos(r)


class Skyline:
    """Sky, two parallax rows of buildings and a street, rendered once at boot.

    Per frame this is a handful of blits, which the Pi can afford; drawing the
    buildings every frame would not be.
    """

    def __init__(self, width: int, horizon: int, street_bottom: int, seed: int = 7) -> None:
        rng = random.Random(seed)
        self.width, self.horizon, self.street_bottom = width, horizon, street_bottom
        self.sky = pygame.Surface((width, horizon))
        for y in range(horizon):
            color = mix(SKY_TOP, SKY_LOW, y / max(1, horizon - 1))
            pygame.draw.line(self.sky, color, (0, y), (width, y))
        self.stars = [(rng.randrange(width), rng.randrange(horizon // 2), rng.random())
                      for _ in range(50)]
        for x, y, b in self.stars:
            self.sky.set_at((x, y), mix(SKY_TOP, CREAM, .25 + .5 * b))
        moon = (400, 64)
        pygame.draw.circle(self.sky, (226, 220, 196), moon, 13)
        pygame.draw.circle(self.sky, mix(SKY_TOP, SKY_LOW, (moon[1] - 5) / horizon),
                           (moon[0] - 6, moon[1] - 4), 12)
        # (surface, parallax speed, windows that blink)
        self.layers = [self._row(rng, FAR, 60, 136, DIM, DIM, .12, .2),
                       self._row(rng, NEAR, 30, 96, WARM, COOL, .3, .45)]

    def _row(self, rng: random.Random, color: tuple, low: int, high: int,
             warm: tuple, cool: tuple, lit: float, speed: float):
        surface = pygame.Surface((self.width, self.horizon))
        surface.fill(KEY)
        surface.set_colorkey(KEY)
        blinkers = []
        x = 0
        while x < self.width:
            w, h = rng.randint(18, 46), rng.randint(low, high)
            for ox in (x, x - self.width):            # wrap so the tile seams
                top = self.horizon - h
                pygame.draw.rect(surface, color, (ox, top, w, h))
                if rng.random() < .3:                  # antenna
                    pygame.draw.line(surface, color, (ox + w // 2, top), (ox + w // 2, top - 8))
            wr = random.Random(x * 31 + low)           # same windows on both copies
            for wx in range(x + 4, x + w - 3, 5):
                for wy in range(self.horizon - h + 5, self.horizon - 4, 7):
                    roll = wr.random()
                    if roll < lit:
                        tone = warm if roll < lit * .7 else cool
                        for ox in (0, -self.width):
                            pygame.draw.rect(surface, tone, (wx + ox, wy, 2, 3))
                    elif roll > .985:
                        blinkers.append((wx, wy, warm))
            x += w + rng.randint(0, 6)
        return surface, speed, blinkers

    def draw(self, s: pygame.Surface, travel: float, clock: float) -> None:
        """`travel` is how far the world has scrolled, in pixels."""
        s.blit(self.sky, (0, 0))
        for i, (x, y, b) in enumerate(self.stars[:12]):
            if math.sin(clock * (1.5 + b) + i) > .7:
                s.set_at((x, y), CREAM)
        for surface, speed, blinkers in self.layers:
            off = int(travel * speed) % self.width
            s.blit(surface, (-off, 0))
            s.blit(surface, (self.width - off, 0))
            for i, (x, y, tone) in enumerate(blinkers):
                if int(clock * .7 + i * 1.7) % 3 == 0:
                    pygame.draw.rect(s, tone, ((x - off) % self.width, y, 2, 3))
        pygame.draw.rect(s, STREET, (0, self.horizon, self.width, self.street_bottom - self.horizon))
        pygame.draw.line(s, KERB, (0, self.horizon), (self.width, self.horizon), 2)
        # The street is nearer than the price line, so it runs faster than it.
        lane_y = self.street_bottom - 5
        for x in range(-int(travel * 1.6) % 32 - 32, self.width, 32):
            pygame.draw.line(s, LANE, (x, lane_y), (x + 14, lane_y), 2)


class Rider:
    """A kid in a cap on a one-wheeler. Feet over the wheel, wheel on the price.

    Poses are functions of time since a reaction started, so the renderer can
    ask for the rider at any moment without the rider keeping a timeline.
    """

    WHEEL = 8
    MOVES = {'hop': .7, 'flip': .9, 'wobble': 1.4, 'cheer': 2.2}

    def __init__(self) -> None:
        self.tilt = 0.0
        self.age = 0.0
        self.fire = False
        self.move: tuple[str, float] | None = None
        self.canvas = pygame.Surface((120, 120), pygame.SRCALPHA)

    def react(self, kind: str) -> None:
        self.move = (kind, 0.0)

    def update(self, dt: float, slope: float, fire: bool) -> None:
        """`slope` is the line's angle under the wheel, degrees, uphill positive."""
        self.age += dt
        if self.move is not None:
            kind, t = self.move
            t += dt
            self.move = (kind, t) if t < self.MOVES[kind] else None
        # Lean into the slope, capped so a spike cannot stand him on his head.
        # On fire he rides leaned back: the one-wheel version of a wheelie.
        target = max(-22.0, min(22.0, slope * .7)) + (16.0 if fire else 0.0)
        self.tilt += (target - self.tilt) * (1 - math.exp(-dt * 7))
        self.fire = fire

    def pose(self) -> tuple[float, float, float, str]:
        """(lift px, extra rotation, pivot height above the hub, arms)."""
        balance = 2.4 * math.sin(self.age * 2.3)       # never quite still
        if self.move is None:
            return 0.0, balance, 0.0, 'bars'
        kind, t = self.move
        p = t / self.MOVES[kind]
        if kind == 'hop':
            return 22 * 4 * p * (1 - p), balance, 0.0, 'up'
        if kind == 'flip':
            spin = 360 * (3 * p * p - 2 * p * p * p)     # eased, lands upright
            return 38 * 4 * p * (1 - p), spin, 22.0, 'up'
        if kind == 'cheer':
            lift = 30 * 4 * min(1, p * 2.5) * (1 - min(1, p * 2.5))
            return lift, balance, 0.0, 'up'
        # wobble: nearly thrown off, arms windmilling, settling back down
        return 0.0, 18 * math.sin(t * 17) * math.exp(-2.6 * t), 0.0, 'flail'

    def placement(self, x: float, y: float) -> tuple[float, float, float]:
        """Hub position and total rotation for a wheel resting on (x, y)."""
        lift, extra, pivot, _ = self.pose()
        angle = self.tilt + extra
        hub_x, hub_y = x, y - self.WHEEL - lift
        if pivot:
            # Spin about the body, not the axle, or the flip swings him under the wheel.
            px, py = rotate_point(0, pivot, angle)
            hub_x, hub_y = x + px, y - self.WHEEL - lift - pivot + py
        return hub_x, hub_y, angle

    def back(self, x: float, y: float) -> tuple[float, float]:
        """The jetpack nozzle in screen space, for the flames."""
        hub_x, hub_y, angle = self.placement(x, y)
        dx, dy = rotate_point(-9, -24, angle)
        return hub_x + dx, hub_y + dy

    def draw(self, s: pygame.Surface, x: float, y: float, spin: float) -> None:
        _, _, _, arms = self.pose()
        hub_x, hub_y, angle = self.placement(x, y)
        c = self.canvas
        c.fill((0, 0, 0, 0))
        cx, cy = c.get_width() // 2, c.get_height() // 2

        def at(dx: float, dy: float) -> tuple[int, int]:
            return round(cx + dx), round(cy + dy)

        # Wheel: tyre, rim, a hub and spokes that turn with the scroll.
        r = self.WHEEL
        pygame.draw.circle(c, TYRE, (cx, cy), r)
        pygame.draw.circle(c, RIM, (cx, cy), r, 2)
        for k in range(6):
            a = spin + k * math.pi / 3
            c.set_at(at(math.cos(a) * (r - 1), math.sin(a) * (r - 1)), (58, 64, 72))
        for k in range(2):
            a = spin + k * math.pi / 2
            pygame.draw.line(c, (120, 130, 138), at(-math.cos(a) * 5, -math.sin(a) * 5),
                             at(math.cos(a) * 5, math.sin(a) * 5), 1)
        pygame.draw.circle(c, HUB, (cx, cy), 2)
        pygame.draw.arc(c, (110, 122, 132), (cx - 11, cy - 11, 22, 22), .35, math.pi - .35, 2)

        # Deck and steering post.
        pygame.draw.line(c, (96, 106, 116), at(-8, -11), at(8, -11), 3)
        pygame.draw.line(c, STEEL, at(4, -11), at(9, -33), 2)
        pygame.draw.line(c, GRIP, at(7, -34), at(12, -34), 3)

        shoulder = at(3, -35)
        grip = at(9, -33)
        if arms == 'up':
            near_hand, far_hand = at(7, -52), at(-3, -51)
        elif arms == 'flail':
            a = self.age * 22
            near_hand = at(3 + 9 * math.cos(a), -35 - 9 * math.sin(a))
            far_hand = at(3 - 9 * math.cos(a + 1), -35 + 9 * math.sin(a + 1))
        else:
            near_hand = far_hand = grip
        pygame.draw.line(c, SHIRT_FAR, shoulder, far_hand, 3)

        if self.fire:
            pygame.draw.rect(c, (126, 134, 142), (*at(-9, -37), 5, 12), border_radius=2)
            pygame.draw.rect(c, (70, 76, 84), (*at(-10, -26), 6, 3))

        # Legs, shoes, body.
        pygame.draw.line(c, PANTS, at(-3, -12), at(-1, -25), 4)
        pygame.draw.line(c, PANTS, at(2, -12), at(1, -25), 4)
        pygame.draw.rect(c, SHOE, (*at(-6, -14), 5, 3))
        pygame.draw.rect(c, SHOE, (*at(1, -14), 5, 3))
        pygame.draw.line(c, SHIRT, at(0, -24), at(2, -36), 7)
        pygame.draw.line(c, SHIRT, shoulder, near_hand, 3)
        pygame.draw.circle(c, GRIP, near_hand, 2)

        # Head: face, big nose, a tuft of hair and a red cap with a brim.
        pygame.draw.circle(c, SKIN, at(4, -43), 5)
        pygame.draw.circle(c, SKIN, at(9, -42), 2)
        pygame.draw.line(c, HAIR, at(-1, -44), at(0, -39), 2)
        c.set_at(at(6, -44), SHOE)
        pygame.draw.circle(c, SHIRT, at(4, -45), 5, draw_top_left=True, draw_top_right=True)
        pygame.draw.line(c, SHIRT, at(6, -45), at(12, -45), 2)

        art = pygame.transform.rotate(c, angle)
        s.blit(art, art.get_rect(center=(round(hub_x), round(hub_y))))


class Sparks:
    """Short-lived particles: coins, shards, flames and smoke."""

    def __init__(self, seed: int = 5) -> None:
        self.items: list[list] = []
        self.rng = random.Random(seed)

    def emit(self, x: float, y: float, vx: float, vy: float, color: tuple,
             life: float, size: float, gravity: float = 0.0, square: bool = False) -> None:
        # x, y, vx, vy, age, life, color, size, gravity, square
        self.items.append([x, y, vx, vy, 0.0, life, color, size, gravity, square])

    def burst(self, x: float, y: float, count: int, colors: tuple, speed: float,
              life: float, size: float, gravity: float = 320.0, square: bool = False,
              drift: float = 0.0) -> None:
        for _ in range(count):
            a = self.rng.uniform(0, 2 * math.pi)
            v = self.rng.uniform(.35, 1) * speed
            self.emit(x, y, math.cos(a) * v + drift, math.sin(a) * v - speed * .4,
                      self.rng.choice(colors), life * self.rng.uniform(.7, 1.1), size,
                      gravity, square)

    def flame(self, x: float, y: float, drift: float) -> None:
        for _ in range(2):
            self.emit(x, y + self.rng.uniform(-2, 2), -self.rng.uniform(70, 120) + drift,
                      self.rng.uniform(-18, 14), self.rng.choice((YELLOW, FLAME, FLAME, RED)),
                      self.rng.uniform(.22, .38), self.rng.uniform(3, 5))

    def update(self, dt: float) -> None:
        for p in self.items:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[8] * dt
            p[4] += dt
        self.items = [p for p in self.items if p[4] < p[5]]

    def draw(self, s: pygame.Surface) -> None:
        for x, y, _, _, age, life, color, size, _, square in self.items:
            left = 1 - age / life
            if square:
                # Coins flicker edge-on as they tumble.
                w = max(1, round(size * abs(math.cos(age * 14))))
                pygame.draw.rect(s, color, (round(x) - w // 2, round(y), w, round(size)))
            else:
                pygame.draw.circle(s, color, (round(x), round(y)), max(1, round(size * left)))


class Floaters:
    """Words that pop up and drift away: payouts, HIT/MISS, HAT TRICK."""

    def __init__(self) -> None:
        self.items: list[list] = []

    def add(self, text: str, x: float, y: float, color: tuple, size: int = 18,
            life: float = 1.4, rise: float = 26.0) -> None:
        self.items.append([text, x, y, rise, 0.0, life, color, size])

    def update(self, dt: float) -> None:
        for f in self.items:
            f[2] -= f[3] * dt
            f[4] += dt
        self.items = [f for f in self.items if f[4] < f[5]]

    def draw(self, s: pygame.Surface) -> None:
        for text, x, y, _, age, life, color, size in self.items:
            fade = min(1.0, (life - age) / .4)
            pop = 1 + .5 * max(0.0, 1 - age / .15)     # lands with a punch
            art = font(round(size * pop)).render(text, False, color)
            shadow = font(round(size * pop)).render(text, False, (0, 0, 0))
            for surf in (shadow, art):
                surf.set_alpha(round(255 * fade))
            rect = art.get_rect(center=(round(x), round(y)))
            s.blit(shadow, rect.move(2, 2))
            s.blit(art, rect)
