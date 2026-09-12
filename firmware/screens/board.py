"""LEADERBOARD: every tick.eth player, best P&L first, read live from ENS.

The rows come from ENS alone (names.Standings): the names in tick.eth's
registry and the tick.* records the scorekeeper writes on them. The wallet
playing on this device is picked out, in the list or under it.
"""
from __future__ import annotations

from decimal import Decimal
import math
import threading
import time
from typing import Callable

import pygame

from games.box import say, say_right, short_address
from games.box_scene import mix
from input import InputAction, event_position
from ui import NAVY, PANEL, CREAM, YELLOW, MINT, RED, MUTED, font, footer
from wallet import MICRO, format_usdc, places_for

TOP = 7                         # rows that fit; one fewer when the player sits below
ROW_Y, ROW_H, PITCH = 58, 24, 26
YOU_Y = 246                     # the player's own row, when they are not in the top
BRONZE = (214, 140, 76)
MEDALS = {1: YELLOW, 2: CREAM, 3: BRONZE}
PNL_R, BEST_R, WINS_R, PLAYS_R = 300, 372, 420, 464     # right edges of the columns


def signed_usdc(amount: Decimal) -> str:
    """+0.005, -1.50: at least two decimals, a third when the amount needs it."""
    micro = int(amount * MICRO)
    text = format_usdc(abs(micro), max(2, min(places_for(abs(micro)), 3)))
    return ('+' if micro > 0 else '-' if micro < 0 else '') + text


class BoardFeed:
    """Reads the standings on its own thread, so a slow Sepolia never stalls a frame.

    Nothing is read until the board is first wanted; after that it refreshes
    while the board is on screen and sleeps while it is not.
    """
    REFRESH_S = 20.0
    RETRY_S = 5.0

    def __init__(self, read: Callable[[], list] | None = None) -> None:
        self.read = read
        self.rows: list | None = None       # None until the first read lands
        self.error = ''
        self.updated = 0.0                  # time.monotonic() of the last good read
        self.showing = False
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def want(self) -> None:
        """Read now, starting the reader the first time."""
        if self._thread is None:
            if self.read is None:
                import names    # needs eth-abi; demo play without the board does not
                self.read = names.Standings().read
            self._thread = threading.Thread(target=self._run, name='ens-board', daemon=True)
            self._thread.start()
        self._wake.set()

    def refresh(self) -> bool:
        try:
            self.rows, self.error, self.updated = self.read(), '', time.monotonic()
            return True
        except Exception as exc:    # Sepolia unreachable: keep the last rows, say so
            self.error = str(exc)[:80] or 'ENS UNREACHABLE'
            return False

    def _run(self) -> None:
        while True:
            self._wake.clear()
            ok = self.refresh()
            self._wake.wait((self.REFRESH_S if ok else self.RETRY_S) if self.showing else None)


class BoardScreen:
    def __init__(self, game=None, feed: BoardFeed | None = None) -> None:
        self.game = game                # whose funding says who is playing
        self.feed = feed or BoardFeed()
        self.t = 0.0

    def open(self) -> None:
        self.feed.showing = True
        self.feed.want()

    def close(self) -> None:
        self.feed.showing = False

    def update(self, dt: float) -> None:
        self.t += dt

    @property
    def funding(self):
        return getattr(getattr(getattr(self.game, 'model', None), 'wallet', None), 'funding', None)

    def me(self) -> str:
        """The wallet playing on this device, or the last one it paid out."""
        funding = self.funding
        last = getattr(funding, 'last_cashout', None)
        return getattr(funding, 'player', '') or (last[1] if last else '')

    def layout(self, rows: list, me: str) -> list[tuple[int, int, object, bool]]:
        """(y, rank, row, mine) per row drawn; row is None for a player not ranked yet."""
        mine = next((i for i, row in enumerate(rows) if row.player.lower() == me.lower()), None) \
            if me else None
        if not me or (mine is not None and mine < TOP):
            return [(ROW_Y + i * PITCH, i + 1, row, i == mine) for i, row in enumerate(rows[:TOP])]
        out = [(ROW_Y + i * PITCH, i + 1, row, False) for i, row in enumerate(rows[:TOP - 1])]
        out.append((YOU_Y, mine + 1 if mine is not None else 0,
                    rows[mine] if mine is not None else None, True))
        return out

    # ---- input -------------------------------------------------------------
    def handle_action(self, action: InputAction) -> str | None:
        if action == InputAction.QUIT:
            return 'quit'
        if action == InputAction.B:
            return 'home'
        if action == InputAction.A:
            self.feed.want()
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if pos[1] >= 274:
            return self.handle_action(InputAction.A if pos[0] >= 240 else InputAction.B)
        return None

    # ---- drawing -----------------------------------------------------------
    def draw(self, s: pygame.Surface) -> None:
        s.fill(NAVY)
        say(s, 'LEADERBOARD', 16, 8, 24, YELLOW)
        self.draw_source(s)
        rows = self.feed.rows
        if rows is None:
            if self.feed.error:
                self.note(s, 'ENS UNREACHABLE', 'RETRYING' + '.' * (int(self.t * 2) % 4), RED)
            else:
                self.note(s, 'READING tick.eth ON ENS' + '.' * (int(self.t * 2) % 4),
                          'SEPOLIA / UNIVERSAL RESOLVER', CREAM)
        elif not rows and not self.me():
            self.note(s, 'NO PLAYERS YET', 'ADD USDC AND PLAY TO GET A tick.eth NAME', CREAM)
        else:
            self.draw_heads(s)
            me = self.me()
            placed = self.layout(rows, me)
            if placed and placed[-1][0] == YOU_Y and len(rows) > TOP - 1:
                say(s, '. . .', 240, 220, 13, MUTED, True)
            for y, rank, row, mine in placed:
                if row is None:
                    self.draw_unranked(s, y, me)
                else:
                    self.draw_row(s, y, rank, row, mine)
        footer(s, '< BACK', 'REFRESH >')

    def draw_source(self, s: pygame.Surface) -> None:
        """Where the rows come from, and how fresh they are."""
        feed = self.feed
        source = 'LIVE FROM tick.eth ON ENS'
        say_right(s, source, 464, 8, 12, CREAM)
        if feed.rows is not None and not feed.error and int(self.t * 2) % 2 == 0:
            pygame.draw.circle(s, RED, (464 - font(12).size(source)[0] - 9, 15), 4)
        if feed.rows is None:
            return
        age = int(time.monotonic() - feed.updated)
        if feed.error:
            say_right(s, f'OFFLINE / LAST READ {age}s AGO', 464, 24, 11, RED)
        else:
            count = len(feed.rows)
            say_right(s, f'{count} PLAYER{"" if count == 1 else "S"} / {age}s AGO', 464, 24, 11, MUTED)

    def draw_heads(self, s: pygame.Surface) -> None:
        y = 42
        say_right(s, '#', 36, y, 11, MUTED)
        say(s, 'PLAYER', 46, y, 11, MUTED)
        for title, right in (('P&L', PNL_R), ('BEST', BEST_R), ('WINS', WINS_R), ('PLAYS', PLAYS_R)):
            say_right(s, title, right, y, 11, MUTED)

    def plate(self, s: pygame.Surface, y: int, mine: bool) -> None:
        rect = pygame.Rect(12, y, 456, ROW_H)
        if mine:    # the player's own row glows a little
            pulse = .5 + .5 * math.sin(self.t * 4)
            pygame.draw.rect(s, mix(PANEL, YELLOW, .14 + .08 * pulse), rect, border_radius=4)
            pygame.draw.rect(s, YELLOW, rect, 2, border_radius=4)
        else:
            pygame.draw.rect(s, PANEL, rect, border_radius=4)

    def you(self, s: pygame.Surface, handle: str, y: int) -> None:
        say(s, 'YOU', 46 + font(15).size(handle)[0] + 8, y + 7, 11, YELLOW)

    def draw_row(self, s: pygame.Surface, y: int, rank: int, row, mine: bool) -> None:
        self.plate(s, y, mine)
        handle = row.name.removesuffix('.tick.eth')
        say_right(s, str(rank), 36, y + 4, 15, MEDALS.get(rank, MUTED))
        say(s, handle, 46, y + 4, 15, CREAM)
        if mine:
            self.you(s, handle, y)
        pnl_color = MINT if row.pnl > 0 else RED if row.pnl < 0 else CREAM
        say_right(s, signed_usdc(row.pnl), PNL_R, y + 4, 15, pnl_color)
        say_right(s, signed_usdc(row.best), BEST_R, y + 5, 13, MUTED)
        say_right(s, str(row.wins), WINS_R, y + 4, 15, CREAM)
        say_right(s, str(row.sessions), PLAYS_R, y + 4, 15, CREAM)

    def draw_unranked(self, s: pygame.Surface, y: int, me: str) -> None:
        """The player on the device before the scorekeeper has scored a session."""
        self.plate(s, y, True)
        name = getattr(self.funding, 'names', {}).get(me)
        handle = name.removesuffix('.tick.eth') if name else short_address(me)
        say_right(s, '-', 36, y + 4, 15, MUTED)
        say(s, handle, 46, y + 4, 15, CREAM)
        self.you(s, handle, y)
        say_right(s, self.waiting_note(), PLAYS_R, y + 6, 11, MUTED)

    def waiting_note(self) -> str:
        """Why this player has no rank yet: still playing, or waiting to be scored."""
        if getattr(self.funding, 'in_session', False):
            return 'RANKED AFTER CASH OUT'
        return 'SCORING ON ENS' + '.' * (int(self.t * 2) % 4)

    def note(self, s: pygame.Surface, big: str, small: str, color: tuple) -> None:
        say(s, big, 240, 120, 18, color, True)
        say(s, small, 240, 148, 12, MUTED, True)


def handle_board_events(board: BoardScreen, events: list, actions: list[InputAction]) -> str | None:
    for event in events:
        pos = event_position(event)
        if pos is not None:
            target = board.handle_touch(pos)
            if target:
                return target
    for action in actions:
        target = board.handle_action(action)
        if target:
            return target
    return None
