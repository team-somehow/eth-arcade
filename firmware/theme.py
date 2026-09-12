"""Display constants and SDL surface setup."""

from __future__ import annotations

import os
import sys

import pygame

WIDTH, HEIGHT = 480, 320
FPS = 30

# Degrees the landscape canvas is turned (counter-clockwise) onto a portrait
# panel. 0 means the canvas is the display itself.
_rotation = 0
_canvas: pygame.Surface | None = None


def _pick_rotation() -> int:
    # TICK_ROTATE=0/90/180/270 forces it; "auto" turns the game only when the
    # screen is portrait, like the 320x480 Waveshare panel, and only on Linux.
    value = os.environ.get("TICK_ROTATE", "auto").strip().lower()
    if value != "auto":
        angle = int(value) % 360
        if angle not in (0, 90, 180, 270):
            raise ValueError("TICK_ROTATE must be auto, 0, 90, 180 or 270")
        return angle
    if not sys.platform.startswith("linux"):
        return 0
    sizes = pygame.display.get_desktop_sizes()
    if sizes and sizes[0][0] < sizes[0][1]:
        return 90
    return 0


def init_display() -> pygame.Surface:
    """Return the 480x320 surface the game draws on; show it with present()."""
    global _rotation, _canvas
    pygame.init()
    _rotation = _pick_rotation()
    size = (HEIGHT, WIDTH) if _rotation in (90, 270) else (WIDTH, HEIGHT)
    # The Pi panel is the whole display; on a desktop keep a plain window so a
    # test run does not take over the screen.
    flags = pygame.FULLSCREEN | pygame.NOFRAME if sys.platform.startswith("linux") else 0
    try:
        screen = pygame.display.set_mode(size, flags)
    except Exception:
        screen = pygame.display.set_mode(size)
    pygame.display.set_caption("ETH ARCADE")
    pygame.mouse.set_visible(True)
    if _rotation == 0:
        _canvas = None
        return screen
    # The game keeps drawing landscape; present() turns each frame.
    _canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
    return _canvas


def present() -> None:
    """Put the finished frame on the panel, turned if the panel is portrait."""
    if _canvas is not None:
        display = pygame.display.get_surface()
        frame = pygame.transform.rotate(_canvas, _rotation)
        if frame.get_size() != display.get_size():
            frame = pygame.transform.scale(frame, display.get_size())
        display.blit(frame, (0, 0))
    pygame.display.flip()


def to_canvas(fx: float, fy: float) -> tuple[int, int]:
    """Map a point on the display, as fractions 0..1, to canvas pixels."""
    if _rotation == 90:
        fx, fy = 1.0 - fy, fx
    elif _rotation == 180:
        fx, fy = 1.0 - fx, 1.0 - fy
    elif _rotation == 270:
        fx, fy = fy, 1.0 - fx
    x = min(max(int(fx * WIDTH), 0), WIDTH - 1)
    y = min(max(int(fy * HEIGHT), 0), HEIGHT - 1)
    return x, y


def display_to_canvas(pos: tuple[int, int]) -> tuple[int, int]:
    """Map a mouse position in display pixels to canvas pixels."""
    if _canvas is None:
        return pos
    w, h = pygame.display.get_surface().get_size()
    return to_canvas(pos[0] / w, pos[1] / h)
