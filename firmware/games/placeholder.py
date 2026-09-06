"""Placeholder launched screen — B returns home."""

from __future__ import annotations

import pygame

from input import InputAction, event_position
from theme import BG, DIM, FG, HEIGHT, WIDTH, draw_text_center


class PlaceholderGame:
    def __init__(self, title: str = "Demo Game") -> None:
        self.title = title

    def set_title(self, title: str) -> None:
        self.title = title

    def handle_action(self, action: InputAction) -> str | None:
        if action == InputAction.B:
            return "home"
        if action == InputAction.QUIT:
            return "quit"
        return None

    def handle_touch(self, _pos: tuple[int, int]) -> str | None:
        # Tap anywhere acts like B — return home.
        return "home"

    def draw(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        surface.fill(BG)
        draw_text_center(surface, fonts["title"], self.title, FG, (WIDTH // 2, HEIGHT // 2 - 24))
        draw_text_center(
            surface,
            fonts["body"],
            "Press B or tap to return",
            DIM,
            (WIDTH // 2, HEIGHT // 2 + 16),
        )


def handle_game_events(
    game: PlaceholderGame,
    events: list[pygame.event.Event],
    keyboard_actions: list[InputAction],
) -> str | None:
    for event in events:
        pos = event_position(event)
        if pos is not None:
            target = game.handle_touch(pos)
            if target:
                return target

    for action in keyboard_actions:
        target = game.handle_action(action)
        if target:
            return target
    return None
