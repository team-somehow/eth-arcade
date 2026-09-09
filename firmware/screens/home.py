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
    def __init__(self, game_id: str = "rush") -> None:
        self.focus = 0
        self.game_id = game_id

    def row_rect(self, index: int) -> pygame.Rect:
        if self.game_id == 'rush':
            return pygame.Rect(16, 74, 448, 138) if index == 0 else pygame.Rect(16, 224, 448, 40)
        return pygame.Rect(16, 74, 448, 178)

    def focused_item(self) -> LauncherItem:
        if self.game_id == 'rush':
            return LauncherItem('rush', 'RUSH') if self.focus == 0 else LauncherItem('wallet','Demo wallet')
        return ITEMS[self.focus]

    def handle_action(self, action: InputAction) -> str | None:
        if self.game_id == 'rush' and action in (InputAction.UP,InputAction.DOWN):
            self.focus = 1-self.focus
        if action == InputAction.A:
            return 'wallet' if self.game_id == 'rush' and self.focus == 1 else 'game'
        if action in (InputAction.B, InputAction.QUIT):
            return 'quit'
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if self.game_id == 'rush' and self.row_rect(1).collidepoint(pos):
            return 'wallet'
        if self.row_rect(0).collidepoint(pos):
            return 'game'
        if pos[1] >= 274:
            return self.handle_action(InputAction.A if pos[0]>=240 else InputAction.B)
        return None

    def draw(self, surface: pygame.Surface, _fonts: dict) -> None:
        if self.game_id == 'rush':
            self.draw_rush(surface)
            return
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

    def draw_rush(self, surface: pygame.Surface):
        from games.rush import rider
        surface.fill(NAVY)
        label(surface,'TICK',16,8,27,CREAM)
        label(surface,'CRANK POWERED ARCADE',223,16,16,MUTED)
        label(surface,'SIM MARKET / DEMO USDC',16,47,16,MINT)
        pygame.draw.rect(surface,PANEL,self.row_rect(0),border_radius=6)
        if self.focus == 0:
            pygame.draw.rect(surface,YELLOW,self.row_rect(0),2,border_radius=6)
        label(surface,'RUSH',34,81,40,YELLOW)
        label(surface,'KEEP IT TURNING.',34,136,19,CREAM)
        label(surface,'ONE BUTTON. THEN RIDE.',34,175,15,MUTED)
        rider(surface,376,183,.8,0)
        pygame.draw.rect(surface,YELLOW if self.focus else PANEL,self.row_rect(1),border_radius=4)
        label(surface,'LOAD DEMO USDC',34,234,18,NAVY if self.focus else MINT)
        label(surface,'UP / DOWN',348,235,15,NAVY if self.focus else MUTED)
        footer(surface,'< QUIT','LOAD >' if self.focus else 'PLAY >')


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
