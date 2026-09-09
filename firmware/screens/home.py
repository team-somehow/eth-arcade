"""TICK launcher. One cartridge (RUSH) plus the money loader."""
from __future__ import annotations
from dataclasses import dataclass

import pygame

from input import InputAction, event_position
from ui import NAVY, PANEL, CREAM, YELLOW, MINT, MUTED, label, footer


@dataclass(frozen=True)
class LauncherItem:
    id: str
    title: str


ITEMS = [LauncherItem('rush', 'RUSH'), LauncherItem('wallet', 'Load USDC')]


class HomeScreen:
    def __init__(self) -> None:
        self.focus = 0

    def row_rect(self, index: int) -> pygame.Rect:
        return pygame.Rect(16, 74, 448, 138) if index == 0 else pygame.Rect(16, 224, 448, 40)

    def focused_item(self) -> LauncherItem:
        return ITEMS[self.focus]

    def handle_action(self, action: InputAction) -> str | None:
        if action in (InputAction.UP, InputAction.DOWN):
            self.focus = 1 - self.focus
        elif action == InputAction.A:
            return self.focused_item().id if self.focus else 'game'
        elif action in (InputAction.B, InputAction.QUIT):
            return 'quit'
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if self.row_rect(1).collidepoint(pos):
            return 'wallet'
        if self.row_rect(0).collidepoint(pos):
            return 'game'
        if pos[1] >= 274:
            return self.handle_action(InputAction.A if pos[0] >= 240 else InputAction.B)
        return None

    def draw(self, surface: pygame.Surface) -> None:
        from games.rush import rider
        surface.fill(NAVY)
        label(surface, 'TICK', 16, 8, 27, CREAM)
        label(surface, 'CRANK POWERED ARCADE', 223, 16, 16, MUTED)
        label(surface, 'PAPER MARKET / DEMO USDC', 16, 47, 16, MINT)
        pygame.draw.rect(surface, PANEL, self.row_rect(0), border_radius=6)
        if self.focus == 0:
            pygame.draw.rect(surface, YELLOW, self.row_rect(0), 2, border_radius=6)
        label(surface, 'RUSH', 34, 81, 40, YELLOW)
        label(surface, 'KEEP IT TURNING.', 34, 136, 19, CREAM)
        label(surface, 'THE DIAL IS THE BET.', 34, 175, 15, MUTED)
        rider(surface, 376, 183, .8, 0)
        pygame.draw.rect(surface, YELLOW if self.focus else PANEL, self.row_rect(1), border_radius=4)
        label(surface, 'LOAD USDC', 34, 234, 18, NAVY if self.focus else MINT)
        label(surface, 'UP / DOWN', 348, 235, 15, NAVY if self.focus else MUTED)
        footer(surface, '< QUIT', 'LOAD >' if self.focus else 'PLAY >')


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
