"""Display constants and SDL surface setup."""

from __future__ import annotations

import sys

import pygame

WIDTH, HEIGHT = 480, 320
FPS = 30


def init_display() -> pygame.Surface:
    pygame.init()
    # The Pi panel is the whole display; on a desktop keep a plain window so a
    # test run does not take over the screen.
    flags = pygame.FULLSCREEN | pygame.NOFRAME if sys.platform.startswith("linux") else 0
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    except Exception:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("TICK / RUSH")
    pygame.mouse.set_visible(True)
    return screen
