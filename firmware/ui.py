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
    """Square-wave arcade beeps, synthesized locally. No assets, no deps.

    A clip is a list of (start_hz, end_hz, seconds) segments. Phase carries
    across segments so a glide is smooth and a note change does not click,
    which is what lets one clip swoop rather than just beep.
    """

    VOLUME = 2300          # of 32767; several clips can overlap
    DETENTS = 8            # crank pitches, low near spot to high at full reach

    def clips_wanted(self) -> dict[str, list[tuple[float, float, float]]]:
        beeps = {
            # BOX RUN
            'bell': [(880, 880, .035), (1320, 1320, .085)],
            'hot': [(600, 1020, .07)],          # price entered your box
            'cold': [(1020, 520, .09)],         # price left it
            'tick_in': [(920, 920, .035)],      # last seconds, currently winning
            'tick_out': [(400, 400, .05)],      # last seconds, currently losing
            'buy1': [(520, 780, .05)],
            'buy2': [(660, 990, .05)],
            'buy3': [(780, 1170, .06)],
            'win_small': [(523, 523, .08), (659, 659, .08), (784, 784, .14)],
            'win_big': [(523, 523, .06), (659, 659, .06), (784, 784, .06),
                        (1047, 1047, .06), (1319, 1319, .22)],
            'void': [(200, 160, .18)],
            # kept for RUSH, and for anything still asking by these names
            'move': [(330, 330, .025)],
            'select': [(550, 550, .05), (740, 740, .07)],
            'lock': [(220, 220, .06), (440, 440, .06), (880, 880, .10)],
            'tick': [(660, 660, .055)],
            'hit': [(523, 523, .10), (659, 659, .10), (784, 784, .10), (1047, 1047, .18)],
            'miss': [(330, 330, .12), (247, 247, .12), (165, 165, .20)],
        }
        # A crank that rises in pitch as the box moves out to the risky end.
        for i in range(self.DETENTS):
            hz = 300 * (1.13 ** i)
            beeps[f'detent{i}'] = [(hz, hz, .018)]
        return beeps

    def __init__(self) -> None:
        self.clips: dict[str, pygame.mixer.Sound] = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            rate, sample_format, channels = pygame.mixer.get_init()
            if sample_format != -16:
                return
            for name, segments in self.clips_wanted().items():
                self.clips[name] = pygame.mixer.Sound(
                    buffer=self.render(segments, rate, channels))
        except pygame.error:
            # Audio is optional: a headless Pi, or a device with no speaker.
            pass

    def render(self, segments, rate: int, channels: int) -> array:
        samples = array('h')
        phase = 0.0
        step = 2 * math.pi / rate
        for start_hz, end_hz, duration in segments:
            count = int(rate * duration)
            for i in range(count):
                fade = i / max(1, count - 1)
                phase += step * (start_hz + (end_hz - start_hz) * fade)
                envelope = min(1, i / max(1, rate * .004), (count - i) / max(1, rate * .02))
                value = int(self.VOLUME * envelope * (1 if math.sin(phase) >= 0 else -1))
                samples.extend([value] * channels)
        return samples

    def detent(self, fraction: float) -> str:
        """Clip name for a crank click at `fraction` of full reach (0-1)."""
        index = int(min(1.0, max(0.0, fraction)) * (self.DETENTS - 1) + .5)
        return f'detent{index}'

    def play(self, name: str) -> None:
        if name in self.clips:
            self.clips[name].play()
