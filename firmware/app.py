"""App shell: event loop and screen dispatch."""

from __future__ import annotations

import sys

import pygame

from encoder import EncoderInput
from games.box_run import BoxRunGame, handle_box_events
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
        self.game = BoxRunGame()
        self.encoder = EncoderInput.try_open()

    def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                if self.current == "game":
                    self.game.update(dt)
                events = list(pygame.event.get())
                actions: list[InputAction] = []
                for event in events:
                    actions.extend(actions_from_event(event))
                if self.encoder is not None:
                    actions.extend(self.encoder.poll())

                self._dispatch(events, actions)
                self._draw()
                pygame.display.flip()
        finally:
            if self.encoder is not None:
                self.encoder.close()

        pygame.quit()
        sys.exit(0)

    def _dispatch(
        self,
        events: list[pygame.event.Event],
        actions: list[InputAction],
    ) -> None:
        if self.current == "home":
            target = handle_home_events(self.home, events, actions)
            if target == "game":
                self.game.enter()
                self.current = "game"
            elif target == "quit":
                self.running = False
        elif self.current == "game":
            target = handle_box_events(self.game, events, actions)
            if target == "home":
                self.current = "home"
            elif target == "quit":
                self.running = False

    def _draw(self) -> None:
        if self.current == "home":
            self.home.draw(self.screen, self.fonts)
        else:
            self.game.draw(self.screen, self.fonts)
