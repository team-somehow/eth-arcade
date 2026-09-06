"""Home launcher: clock status bar + focusable game list."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pygame

from input import InputAction, event_position
from theme import (
    BG,
    DIM,
    FG,
    FOOTER_HEIGHT,
    HEIGHT,
    ROW_HEIGHT,
    STATUS_HEIGHT,
    WIDTH,
    draw_text,
    draw_text_center,
)


@dataclass(frozen=True)
class LauncherItem:
    id: str
    title: str


ITEMS: list[LauncherItem] = [
    LauncherItem("demo", "Demo Game"),
    LauncherItem("blank", "Blank App"),
    LauncherItem("settings", "Settings (stub)"),
]

LIST_TOP = STATUS_HEIGHT + 12
LIST_LEFT = 16
LIST_WIDTH = WIDTH - 32


class HomeScreen:
    def __init__(self) -> None:
        self.focus = 0

    def row_rect(self, index: int) -> pygame.Rect:
        return pygame.Rect(LIST_LEFT, LIST_TOP + index * ROW_HEIGHT, LIST_WIDTH, ROW_HEIGHT)

    def handle_action(self, action: InputAction) -> str | None:
        """Return a navigation target screen name, or None."""
        if action == InputAction.UP:
            self.focus = (self.focus - 1) % len(ITEMS)
        elif action == InputAction.DOWN:
            self.focus = (self.focus + 1) % len(ITEMS)
        elif action == InputAction.A:
            return "game"
        elif action == InputAction.B:
            return "quit"
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        for i, _item in enumerate(ITEMS):
            if self.row_rect(i).collidepoint(pos):
                if i == self.focus:
                    return "game"
                self.focus = i
                return None
        return None

    def focused_item(self) -> LauncherItem:
        return ITEMS[self.focus]

    def draw(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        surface.fill(BG)
        self._draw_status(surface, fonts)
        self._draw_list(surface, fonts)
        self._draw_footer(surface, fonts)

    def _draw_status(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        pygame.draw.line(surface, FG, (0, STATUS_HEIGHT - 1), (WIDTH, STATUS_HEIGHT - 1), 1)
        draw_text(surface, fonts["title"], "PLAYDATE-LIKE", FG, (12, 8))
        clock = datetime.now().strftime("%H:%M")
        clock_surf = fonts["clock"].render(clock, True, FG)
        surface.blit(clock_surf, (WIDTH - clock_surf.get_width() - 12, 9))

    def _draw_list(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        for i, item in enumerate(ITEMS):
            rect = self.row_rect(i)
            focused = i == self.focus
            if focused:
                pygame.draw.rect(surface, FG, rect)
                text_color = BG
                label = f"> {item.title}"
            else:
                text_color = FG
                label = f"  {item.title}"
            draw_text(
                surface,
                fonts["body"],
                label,
                text_color,
                (rect.x + 10, rect.y + (ROW_HEIGHT - fonts["body"].get_height()) // 2),
            )

    def _draw_footer(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        y = HEIGHT - FOOTER_HEIGHT
        pygame.draw.line(surface, FG, (0, y), (WIDTH, y), 1)
        draw_text_center(
            surface,
            fonts["small"],
            "A Launch   B Quit   D-pad Navigate",
            DIM,
            (WIDTH // 2, y + FOOTER_HEIGHT // 2),
        )


def handle_home_events(
    home: HomeScreen,
    events: list[pygame.event.Event],
    keyboard_actions: list[InputAction],
) -> str | None:
    """Process touch then keyboard; return navigation target if any."""
    for event in events:
        pos = event_position(event)
        if pos is not None:
            target = home.handle_touch(pos)
            if target:
                return target

    for action in keyboard_actions:
        if action == InputAction.QUIT:
            return "quit"
        target = home.handle_action(action)
        if target:
            return target
    return None
