"""Unify D-pad keys and touch/finger events into InputAction values."""

from __future__ import annotations

from enum import Enum, auto

import pygame

from theme import HEIGHT, WIDTH


class InputAction(Enum):
    UP = auto()
    DOWN = auto()
    A = auto()
    B = auto()
    QUIT = auto()


def event_position(event: pygame.event.Event) -> tuple[int, int] | None:
    if event.type == pygame.MOUSEBUTTONDOWN:
        return event.pos
    if event.type == pygame.FINGERDOWN:
        return int(event.x * WIDTH), int(event.y * HEIGHT)
    return None


def actions_from_event(event: pygame.event.Event) -> list[InputAction]:
    """Map a pygame event to zero or more high-level actions.

    Touch position is not converted here; callers use event_position for hit tests.
    Keyboard D-pad / A / B map directly.
    """
    if event.type == pygame.QUIT:
        return [InputAction.QUIT]

    if event.type != pygame.KEYDOWN:
        return []

    key = event.key
    if key in (pygame.K_UP, pygame.K_w):
        return [InputAction.UP]
    if key in (pygame.K_DOWN, pygame.K_s):
        return [InputAction.DOWN]
    if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_x):
        return [InputAction.A]
    if key in (pygame.K_ESCAPE, pygame.K_z, pygame.K_BACKSPACE):
        return [InputAction.B]
    return []
