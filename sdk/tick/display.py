"""One canvas, 480x320, landscape, whatever the panel underneath is doing.

Your game draws on a 480x320 surface and never thinks about the display again.
If the actual panel is portrait -- like the 320x480 Waveshare SPI screen on
this handheld -- `present()` turns each finished frame onto it. Touch and mouse
positions are turned back the other way, so a tap lands where the player
pointed, not where the panel thinks they did.

That seam is worth its small cost: a game written against a rotating canvas is
a game with rotation maths smeared through its draw code and its input code,
and it is wrong in a different way on every device.

On the Pi
---------

`bootstrap()` runs before pygame is imported for real. It sets the SDL driver
for KMSDRM when nothing owns the display, and re-execs into the system Python
if the active pygame came from pip -- the pip wheel has no KMSDRM support, so
without this the game opens on nothing at all and the panel stays black.
"""
from __future__ import annotations

import importlib.util
import os
import sys

WIDTH, HEIGHT = 480, 320
FPS = 30

SYSTEM_PYTHON = '/usr/bin/python3'

_rotation = 0
_canvas = None


# ---- Pi bootstrap (call before importing pygame) --------------------------
def configure_sdl() -> None:
    # Prefer a running desktop (Wayland or X11); only claim DRM when nothing
    # else owns it.
    if not (os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY')):
        os.environ.setdefault('SDL_VIDEODRIVER', 'kmsdrm')
        # The card index of the panel varies by board: set
        # SDL_VIDEO_KMSDRM_DEVICE_INDEX for yours rather than trusting this.
        os.environ.setdefault('SDL_VIDEO_KMSDRM_DEVICE_INDEX', '2')
    os.environ.setdefault('SDL_MOUSE_RELATIVE', '0')


def _venv_free_env() -> dict:
    env = os.environ.copy()
    venv = env.pop('VIRTUAL_ENV', None)
    if venv:
        venv_bin = os.path.realpath(os.path.join(venv, 'bin'))
        env['PATH'] = ':'.join(p for p in env.get('PATH', '').split(':')
                               if p and os.path.realpath(p) != venv_bin)
    return env


def bootstrap() -> None:
    """Configure SDL and, on a Pi, re-exec under the system pygame if needed."""
    if not sys.platform.startswith('linux'):
        return
    configure_sdl()
    spec = importlib.util.find_spec('pygame')
    if not spec or not spec.origin:
        return
    origin = spec.origin
    if 'dist-packages' in origin or 'site-packages' not in origin:
        return
    if not os.path.exists(SYSTEM_PYTHON):
        return
    os.execve(SYSTEM_PYTHON, [SYSTEM_PYTHON, *sys.argv], _venv_free_env())


# ---- the canvas ----------------------------------------------------------
def _pick_rotation(pygame) -> int:
    # TICK_ROTATE=0/90/180/270 forces it; "auto" turns the canvas only when the
    # screen is portrait, and only on Linux (a desktop window is never turned).
    value = os.environ.get('TICK_ROTATE', 'auto').strip().lower()
    if value != 'auto':
        angle = int(value) % 360
        if angle not in (0, 90, 180, 270):
            raise ValueError('TICK_ROTATE must be auto, 0, 90, 180 or 270')
        return angle
    if not sys.platform.startswith('linux'):
        return 0
    sizes = pygame.display.get_desktop_sizes()
    return 90 if sizes and sizes[0][0] < sizes[0][1] else 0


def init_display(title: str = 'TICK'):
    """Return the 480x320 surface to draw on. Show it with `present()`."""
    import pygame
    global _rotation, _canvas
    pygame.init()
    _rotation = _pick_rotation(pygame)
    size = (HEIGHT, WIDTH) if _rotation in (90, 270) else (WIDTH, HEIGHT)
    # The Pi panel is the whole display; on a desktop keep a plain window so a
    # test run does not take over the screen.
    flags = pygame.FULLSCREEN | pygame.NOFRAME if sys.platform.startswith('linux') else 0
    try:
        screen = pygame.display.set_mode(size, flags)
    except Exception:
        screen = pygame.display.set_mode(size)
    pygame.display.set_caption(title)
    pygame.mouse.set_visible(True)
    if _rotation == 0:
        _canvas = None
        return screen
    _canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
    return _canvas


def present() -> None:
    """Put the finished frame on the panel, turned if the panel is portrait."""
    import pygame
    if _canvas is not None:
        display = pygame.display.get_surface()
        frame = pygame.transform.rotate(_canvas, _rotation)
        if frame.get_size() != display.get_size():
            frame = pygame.transform.scale(frame, display.get_size())
        display.blit(frame, (0, 0))
    pygame.display.flip()


def to_canvas(fx: float, fy: float) -> tuple[int, int]:
    """A point on the display, as fractions 0..1, to canvas pixels."""
    if _rotation == 90:
        fx, fy = 1.0 - fy, fx
    elif _rotation == 180:
        fx, fy = 1.0 - fx, 1.0 - fy
    elif _rotation == 270:
        fx, fy = fy, 1.0 - fx
    return (min(max(int(fx * WIDTH), 0), WIDTH - 1),
            min(max(int(fy * HEIGHT), 0), HEIGHT - 1))


def display_to_canvas(pos: tuple[int, int]) -> tuple[int, int]:
    """A mouse position in display pixels to canvas pixels."""
    import pygame
    if _canvas is None:
        return pos
    w, h = pygame.display.get_surface().get_size()
    return to_canvas(pos[0] / w, pos[1] / h)


def rotation() -> int:
    return _rotation
