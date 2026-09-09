"""Display constants and SDL surface setup."""

from __future__ import annotations

import pygame

WIDTH, HEIGHT = 480, 320
FPS = 30


def init_display() -> pygame.Surface:
    pygame.init()
    flags = pygame.FULLSCREEN | pygame.NOFRAME
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    except Exception:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("TICK / RUSH")
    pygame.mouse.set_visible(True)
    return screen
