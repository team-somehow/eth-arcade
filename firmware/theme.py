"""Display constants, 1-bit palette, and fonts."""

from __future__ import annotations

import pygame

WIDTH, HEIGHT = 480, 320
FPS = 30

STATUS_HEIGHT = 36
FOOTER_HEIGHT = 28
ROW_HEIGHT = 36

# 1-bit palette (Playdate-like)
BG = (0, 0, 0)
FG = (255, 255, 255)
DIM = (140, 140, 140)


def init_display() -> pygame.Surface:
    pygame.init()
    flags = pygame.FULLSCREEN | pygame.NOFRAME
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    except Exception:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Playdate-like")
    pygame.mouse.set_visible(True)
    return screen


def load_fonts() -> dict[str, pygame.font.Font]:
    return {
        "title": pygame.font.SysFont("dejavusans", 18, bold=True),
        "body": pygame.font.SysFont("dejavusans", 16),
        "small": pygame.font.SysFont("dejavusans", 12),
        "clock": pygame.font.SysFont("dejavusansmono", 16, bold=True),
    }


def draw_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    pos: tuple[int, int],
) -> pygame.Rect:
    rendered = font.render(text, True, color)
    surface.blit(rendered, pos)
    return rendered.get_rect(topleft=pos)


def draw_text_center(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    center: tuple[int, int],
) -> pygame.Rect:
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=center)
    surface.blit(rendered, rect)
    return rect
