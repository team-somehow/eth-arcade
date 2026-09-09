"""Shared 480x320 pixel-UI kit: palette, bitmap-ish labels, chrome and beeps."""
from __future__ import annotations

from array import array
from functools import lru_cache
import math

import pygame

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
