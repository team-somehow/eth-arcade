"""App shell: event loop and screen dispatch."""

from __future__ import annotations

import os
import sys

import pygame

from buttons import ButtonPad
from encoder import EncoderInput
from games.box import BoxGame, handle_box_events
from games.rush import RushGame, handle_rush_events
from input import InputAction, actions_from_event
from screens.board import BoardScreen, handle_board_events
from screens.home import HomeScreen, handle_home_events
from screens.money import MoneyScreen, handle_money_events
from theme import FPS, init_display, present


class App:
    def __init__(self, game_id: str | None = None) -> None:
        self.display = init_display()
        self.clock = pygame.time.Clock()
        self.running = True
        self.current = "home"
        self.game_id = game_id or os.environ.get("TICK_GAME", "box")
        if self.game_id not in ("box", "rush"):
            raise ValueError("TICK_GAME must be box or rush")
        self.game = BoxGame() if self.game_id == "box" else RushGame()
        self.home = HomeScreen(self.game_id, self.game)
        self.board = BoardScreen(self.game)
        self.money = MoneyScreen(self.game, skyline=self.home.skyline)
        self.handle = handle_box_events if self.game_id == "box" else handle_rush_events
        self.encoder = EncoderInput.try_open()
        self.pad = ButtonPad.try_open()

    def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                if self.current == "game":
                    self.game.update(dt)
                else:
                    self.screen_up().update(dt)
                    if hasattr(self.game, "watch"):
                        # Prices keep flowing behind the launcher, and the chain
                        # is still read, so money lands on whatever is up (BOX RUN).
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
                if self.pad is not None:
                    # Red and yellow panel buttons, if this device has them.
                    actions.extend(self.pad.poll())

                self._dispatch(events, actions)
                self._draw()
                present()
        finally:
            self.game.close()
            if self.encoder is not None:
                self.encoder.close()
            if self.pad is not None:
                self.pad.close()

        pygame.quit()
        sys.exit(0)

    def screen_up(self):
        """The non-game screen that is up. The game draws and updates itself."""
        return {"board": self.board, "money": self.money}.get(self.current, self.home)

    def to_money(self) -> None:
        """Real funds: one screen, whichever face the money calls for."""
        self.money.open()
        self.game.play("enter")
        self.current = "money"

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
                if self.home.focused_item().id == "board":
                    self.board.feed.want()      # start reading, so the board opens full
            if target == "board":
                self.board.open()
                self.game.play("enter")
                self.current = "board"
            elif target == "wallet" and getattr(self.game, "onchain", False):
                # Real money never goes through the game: coins in, cash out and
                # the ticket are all the money screen's, from the launcher.
                self.to_money()
            elif target in ("game", "wallet"):
                self.game.enter()
                if target == "wallet":
                    self.game.open_wallet()
                self.game.play("enter")
                self.current = "game"
            elif target == "quit":
                self.running = False
        elif self.current == "money":
            target = handle_money_events(self.money, events, actions)
            if target in ("home", "funded"):
                # After a deposit nobody acted on, PLAY is what they came for,
                # not the CASH OUT the money button has just turned into.
                if target == "funded":
                    self.home.focus = 0
                self.money.close()
                self.game.play("back")
                self.current = "home"
            elif target == "game":
                self.money.close()
                self.game.enter()
                self.game.play("enter")
                self.current = "game"
            elif target == "board":
                # The ticket hands the board what it cannot read from ENS yet:
                # who just cashed out and what the run was worth.
                ticket = getattr(self.game, "ticket", None)
                self.money.close()
                # Told to hold before it is opened: opening wakes the reader, and
                # a read that lands first would replace the picture we came to
                # show changing.
                if ticket is not None:
                    self.board.arrive(ticket.player, ticket.pnl)
                self.board.open()
                self.game.play("enter")
                self.current = "board"
            elif target == "quit":
                self.running = False
        elif self.current == "board":
            target = handle_board_events(self.board, events, actions)
            if target == "home":
                self.board.close()
                self.game.play("back")
                self.current = "home"
            elif target == "money" and getattr(self.game, "onchain", False):
                # PLAY AGAIN, after watching your row move: the loop closes.
                self.board.close()
                self.to_money()
            elif target == "quit":
                self.running = False
        elif self.current == "game":
            target = self.handle(self.game, events, actions)
            if target == "home":
                self.game.play("back")
                self.current = "home"
            elif target == "money":
                # Out of money mid-run, on real funds: straight to the QR.
                self.to_money()
            elif target == "quit":
                self.running = False

    def _draw(self) -> None:
        if self.current == "game":
            self.game.draw(self.display)
        else:
            # The bed keeps running behind the launcher.
            self.game.ambient()
            self.screen_up().draw(self.display)
