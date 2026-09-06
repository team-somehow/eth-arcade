"""App shell: event loop and screen dispatch."""

from __future__ import annotations

import sys

import pygame

from games.placeholder import PlaceholderGame, handle_game_events
from input import InputAction, actions_from_event
from screens.home import HomeScreen, handle_home_events
from theme import FPS, init_display, load_fonts


class App:
    def __init__(self) -> None:
        self.screen = init_display()
        self.fonts = load_fonts()
        self.clock = pygame.time.Clock()
        self.running = True
        self.current = "home"
        self.home = HomeScreen()
        self.game = PlaceholderGame()

    def run(self) -> None:
        while self.running:
            events = list(pygame.event.get())
            keyboard_actions: list[InputAction] = []
            for event in events:
                keyboard_actions.extend(actions_from_event(event))

            self._dispatch(events, keyboard_actions)
            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit(0)

    def _dispatch(
        self,
        events: list[pygame.event.Event],
        keyboard_actions: list[InputAction],
    ) -> None:
        if self.current == "home":
            target = handle_home_events(self.home, events, keyboard_actions)
            if target == "game":
                self.game.set_title(self.home.focused_item().title)
                self.current = "game"
            elif target == "quit":
                self.running = False
        elif self.current == "game":
            target = handle_game_events(self.game, events, keyboard_actions)
            if target == "home":
                self.current = "home"
            elif target == "quit":
                self.running = False

    def _draw(self) -> None:
        if self.current == "home":
            self.home.draw(self.screen, self.fonts)
        else:
            self.game.draw(self.screen, self.fonts)
