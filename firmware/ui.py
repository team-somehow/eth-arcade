"""Shared 480x320 pixel-UI kit: palette, bitmap-ish labels, chrome and beeps."""
from __future__ import annotations

from array import array
from functools import lru_cache
import math
import random

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
    """Square-wave arcade audio, synthesized at startup. No assets, no deps.

    Two things live here. **Clips** are one-shot cues: a clip is a list of
    (start_hz, end_hz, seconds) segments, and phase carries across segments so
    a clip can glide rather than only beep.

    **Beds** are looping music, assembled from a cached palette of notes so a
    two-second loop costs a few note renders and a lot of cheap copying — a
    per-sample pass over every bar would be too slow to do at boot on a Pi.
    Each bed layer is monophonic and plays on its own reserved channel, so the
    mixer does the polyphony and Python never mixes a sample (which matters:
    `audioop` is gone in 3.13).

    Layers across all modes are the same length, so switching mode restarts the
    bar rather than drifting the parts apart.
    """

    # Of 32767. Sized so three overlapping cues plus the bed stay inside the
    # range: 3x6000 + ~3000 is about 21k, so nothing clips.
    VOLUME = 6000
    MUSIC_LEVEL = .5       # beds sit at about half the level of the cues
    DETENTS = 8            # crank pitches, low near spot to high at full reach
    STEP = .125            # one sixteenth at 120 BPM
    BARS = 16              # steps per loop: a two-second bar
    LAYERS = 3             # reserved channels for the music

    # A minor: brooding when idle, driving when there is money on the table.
    A2, C3, E3, G3 = 110.00, 130.81, 164.81, 196.00
    A4, C5, E5, G5, A5 = 440.00, 523.25, 659.25, 784.00, 880.00
    N = None

    def beds_wanted(self):
        bass_idle = [self.A2, self.N, self.N, self.N, self.E3, self.N, self.N, self.N,
                     self.A2, self.N, self.N, self.N, self.G3, self.N, self.N, self.N]
        bass_drive = [self.A2, self.N, self.A2, self.N, self.E3, self.N, self.E3, self.N,
                      self.A2, self.N, self.A2, self.N, self.G3, self.N, self.G3, self.E3]
        arp_slow = [self.A4, self.N, self.N, self.N, self.C5, self.N, self.N, self.N,
                    self.E5, self.N, self.N, self.N, self.C5, self.N, self.N, self.N]
        arp_fast = [self.A4, self.C5, self.E5, self.A5, self.E5, self.C5, self.A4, self.C5,
                    self.E5, self.A5, self.C5, self.E5, self.A4, self.C5, self.E5, self.A5]
        arp_tense = [self.A5, self.G5, self.E5, self.G5, self.A5, self.G5, self.E5, self.C5,
                     self.A5, self.G5, self.E5, self.G5, self.A5, self.E5, self.C5, self.A4]
        hats = [1 if i % 2 == 0 else None for i in range(self.BARS)]
        drive_hats = [1 if i % 1 == 0 else None for i in range(self.BARS)]
        return {
            'idle': [(bass_idle, 'square', .45), (arp_slow, 'square', .30)],
            'live': [(bass_drive, 'square', .50), (arp_fast, 'square', .30),
                     (hats, 'noise', .18)],
            'final': [(bass_drive, 'square', .55), (arp_tense, 'square', .34),
                      (drive_hats, 'noise', .22)],
        }

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
            'jackpot': [(523, 523, .05), (784, 784, .05), (1047, 1047, .05),
                        (1319, 1319, .05), (1568, 1568, .05), (2093, 2093, .28)],
            'hattrick': [(392, 392, .06), (523, 523, .06), (659, 659, .06),
                         (784, 1568, .32)],     # third hit in a row: rider catches fire
            'fizzle': [(900, 180, .3)],         # the streak ends
            'void': [(200, 160, .18)],
            'warn': [(240, 200, .06), (240, 200, .06)],
            'stale': [(520, 300, .16)],
            'crossline': [(1500, 1500, .012)],  # the box passing over spot
            'nav': [(440, 440, .02)],
            'enter': [(392, 588, .07), (784, 784, .10)],
            'back': [(588, 392, .09)],
            'coin': [(988, 988, .04), (1319, 1319, .10)],
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
        self.beds: dict[str, list[pygame.mixer.Sound]] = {}
        self.mode = 'off'
        self.rng = random.Random(7)
        self._notes: dict[tuple, array] = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            rate, sample_format, channels = pygame.mixer.get_init()
            if sample_format != -16:
                return
            pygame.mixer.set_num_channels(24)
            pygame.mixer.set_reserved(self.LAYERS)
            for name, segments in self.clips_wanted().items():
                self.clips[name] = pygame.mixer.Sound(
                    buffer=self.render(segments, rate, channels))
            for mode, layers in self.beds_wanted().items():
                self.beds[mode] = [
                    pygame.mixer.Sound(buffer=self.pattern(steps, wave, level, rate, channels))
                    for steps, wave, level in layers
                ]
            self._notes.clear()
        except pygame.error:
            # Audio is optional: a headless Pi, or a device with no speaker.
            pass

    # ---- synthesis --------------------------------------------------------
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

    def note(self, hz, count: int, wave: str, level: float, rate: int, channels: int) -> array:
        """One note of the music palette, cached: patterns then just copy it."""
        key = (hz, count, wave, level, channels)
        cached = self._notes.get(key)
        if cached is not None:
            return cached
        samples = array('h')
        peak = self.VOLUME * level
        for i in range(count):
            # Percussive decay, so a repeated note reads as a pulse not a drone.
            envelope = min(1, i / max(1, rate * .003)) * (1 - i / count) ** .7
            if wave == 'noise':
                shape = self.rng.choice((1, -1))
            else:
                shape = 1 if math.sin(2 * math.pi * hz * i / rate) >= 0 else -1
            samples.extend([int(peak * envelope * shape)] * channels)
        self._notes[key] = samples
        return samples

    def pattern(self, steps, wave: str, level: float, rate: int, channels: int) -> array:
        span = int(rate * self.STEP)
        sounding = int(span * (.55 if wave == 'noise' else .92))
        rest = array('h', bytes(2 * (span - sounding) * channels))
        silence = array('h', bytes(2 * span * channels))
        out = array('h')
        for hz in steps:
            if hz is None:
                out.extend(silence)
                continue
            out.extend(self.note(6000 if wave == 'noise' else hz,
                                 sounding, wave, level, rate, channels))
            out.extend(rest)
        return out

    # ---- playback ---------------------------------------------------------
    def detent(self, fraction: float) -> str:
        """Clip name for a crank click at `fraction` of full reach (0-1)."""
        index = int(min(1.0, max(0.0, fraction)) * (self.DETENTS - 1) + .5)
        return f'detent{index}'

    def music(self, mode: str) -> None:
        """Switch the bed. Cheap to call every frame; only a change acts."""
        if mode == self.mode or (mode != 'off' and mode not in self.beds):
            return
        self.mode = mode
        for index in range(self.LAYERS):
            pygame.mixer.Channel(index).stop()
        for index, sound in enumerate(self.beds.get(mode, [])):
            channel = pygame.mixer.Channel(index)
            channel.set_volume(self.MUSIC_LEVEL)
            channel.play(sound, loops=-1)

    def play(self, name: str) -> None:
        if name in self.clips:
            self.clips[name].play()
