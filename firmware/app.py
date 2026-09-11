"""App shell: event loop and screen dispatch."""

from __future__ import annotations

import os
import sys

import pygame

from encoder import EncoderInput
from games.box import BoxGame, handle_box_events
from games.rush import RushGame, handle_rush_events
from input import InputAction, actions_from_event
from screens.home import HomeScreen, handle_home_events
from theme import FPS, init_display


class App:
    def __init__(self, game_id: str | None = None) -> None:
        self.screen = init_display()
        self.clock = pygame.time.Clock()
        self.running = True
        self.current = "home"
        self.game_id = game_id or os.environ.get("TICK_GAME", "box")
        if self.game_id not in ("box", "rush"):
            raise ValueError("TICK_GAME must be box or rush")
        self.game = BoxGame() if self.game_id == "box" else RushGame()
        self.home = HomeScreen(self.game_id, self.game)
        self.handle = handle_box_events if self.game_id == "box" else handle_rush_events
        self.encoder = EncoderInput.try_open()

    def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                if self.current == "game":
                    self.game.update(dt)
                else:
                    self.home.update(dt)
                    if hasattr(self.game, "watch"):
                        # Prices keep flowing behind the launcher (BOX RUN only).
                        self.game.watch(dt)
                events = list(pygame.event.get())
                actions: list[InputAction] = []
                for event in events:
                    actions.extend(actions_from_event(event))
                if self.encoder is not None:
                    # In play every detent counts, so read raw motion. Menus
                    # (home, load) keep the rate-limited scrolling instead.
                    playing = self.current == "game" and not self.game.wallet_open
                    actions.extend(self.encoder.poll(continuous=playing))

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
            focus = self.home.focus
            target = handle_home_events(self.home, events, actions)
            if self.home.focus != focus:
                self.game.play("nav")
            if target in ("game", "wallet"):
                self.game.enter()
                if target == "wallet":
                    self.game.open_wallet()
                self.game.play("enter")
                self.current = "game"
            elif target == "quit":
                self.running = False
        elif self.current == "game":
            target = self.handle(self.game, events, actions)
            if target == "home":
                self.game.play("back")
                self.current = "home"
            elif target == "quit":
                self.running = False

    def _draw(self) -> None:
        if self.current == "home":
            # The bed keeps running behind the launcher.
            self.game.ambient()
            self.home.draw(self.screen)
        else:
            self.game.draw(self.screen)
