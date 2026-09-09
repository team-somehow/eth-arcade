"""TICK launcher for the first playable cartridge."""
from __future__ import annotations
from dataclasses import dataclass
import pygame
from games.box_run import NAVY, PANEL, CREAM, YELLOW, MINT, MUTED, label, diamond, footer
from input import InputAction, event_position


@dataclass(frozen=True)
class LauncherItem:
    id: str
    title: str


ITEMS = [LauncherItem('box_run', 'BOX RUN')]


class HomeScreen:
    def __init__(self) -> None:
        self.focus = 0

    def row_rect(self, _index: int) -> pygame.Rect:
        return pygame.Rect(16, 74, 448, 178)

    def focused_item(self) -> LauncherItem:
        return ITEMS[self.focus]

    def handle_action(self, action: InputAction) -> str | None:
        if action == InputAction.A:
            return 'game'
        if action in (InputAction.B, InputAction.QUIT):
            return 'quit'
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if self.row_rect(0).collidepoint(pos):
            return 'game'
        if pos[1] >= 274:
            return 'game' if pos[0] >= 240 else 'quit'
        return None

    def draw(self, surface: pygame.Surface, _fonts: dict) -> None:
        surface.fill(NAVY)
        label(surface, 'TICK', 16, 8, 27, CREAM)
        label(surface, 'POCKET MARKET ARCADE', 223, 16, 16, MUTED)
        pygame.draw.rect(surface, PANEL, self.row_rect(0), border_radius=6)
        label(surface, 'BOX RUN', 34, 86, 37, YELLOW)
        label(surface, 'Where will ETH land?', 34, 132, 18, CREAM)
        points = [(34,216),(63,202),(84,214),(111,187),(136,196),(162,179),(188,185),(214,167),(242,182),(271,177)]
        pygame.draw.lines(surface, CREAM, False, points, 3)
        pygame.draw.rect(surface, MINT, (309,158,111,67), 3)
        diamond(surface, 363, 190, MINT)
        label(surface, 'SIMULATED / PRACTICE CREDITS', 16, 47, 16, MINT)
        footer(surface, '< QUIT', 'PLAY >')


def handle_home_events(home: HomeScreen, events: list, actions: list[InputAction]) -> str | None:
    for event in events:
        pos = event_position(event)
        if pos is not None:
            target = home.handle_touch(pos)
            if target:
                return target
    for action in actions:
        target = home.handle_action(action)
        if target:
            return target
    return None
