"""App shell: event loop and screen dispatch."""

from __future__ import annotations

import sys

import pygame

from encoder import EncoderInput
from games.rush import RushGame, handle_rush_events
from input import InputAction, actions_from_event
from screens.home import HomeScreen, handle_home_events
from theme import FPS, init_display


class App:
    def __init__(self) -> None:
        self.screen = init_display()
        self.clock = pygame.time.Clock()
        self.running = True
        self.current = "home"
        self.home = HomeScreen()
        self.game = RushGame()
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
                    # In a ride every detent counts, so read raw motion. Menus
                    # (home, load) keep the rate-limited scrolling instead.
                    riding = self.current == "game" and not self.game.wallet_open
                    actions.extend(self.encoder.poll(continuous=riding))

                self._dispatch(events, actions)
                self._draw()
                pygame.display.flip()
        finally:
            self.game.close()
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
            if target in ("game", "wallet"):
                self.game.enter()
                if target == "wallet":
                    self.game.open_wallet()
                self.current = "game"
            elif target == "quit":
                self.running = False
        elif self.current == "game":
            target = handle_rush_events(self.game, events, actions)
            if target == "home":
                self.current = "home"
            elif target == "quit":
                self.running = False

    def _draw(self) -> None:
        if self.current == "home":
            self.home.draw(self.screen)
        else:
            self.game.draw(self.screen)
