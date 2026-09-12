"""LEADERBOARD: every tick.eth player, best P&L first, read live from ENS.

The rows come from ENS alone (names.Standings): the names in tick.eth's
registry and the tick.* records the scorekeeper writes on them. The wallet
playing on this device is picked out, in the list or under it.
"""
from __future__ import annotations

from decimal import Decimal
import math
import random
import threading
import time
from typing import Callable

import pygame

from games.box import say, say_right, short_address
from games.box_scene import mix
from input import InputAction, event_position
from ui import NAVY, PANEL, CREAM, YELLOW, MINT, RED, MUTED, font, footer
from wallet import MICRO, format_usdc, places_for

TOP = 6                         # rows that fit; one fewer when the player sits below
ROW_Y, ROW_H, PITCH = 70, 26, 30
YOU_Y = ROW_Y + (TOP - 1) * PITCH   # the player's own row, when they are not in the top
MOVE_X = 190                    # the narrow column the ghost and the UP/DOWN mark use
BRONZE = (214, 140, 76)
MEDALS = {1: YELLOW, 2: CREAM, 3: BRONZE}
STRIP = pygame.Rect(12, 250, 456, 22)
PNL_R, BEST_R, WINS_R, PLAYS_R = 326, 386, 420, 462     # right edges of the columns
BAR_UP, BAR_DOWN = (24, 58, 48), (58, 30, 32)           # the plate's own P&L fill
NOTE_FILL = (50, 44, 18)


def place_y(place: int | None) -> int:
    """Where a rank is drawn: its own slot if the list reaches that far, and the
    pinned row under the list if it does not."""
    return slot_y(place) if place is not None and place < TOP else YOU_Y


def slot_y(index: int) -> int:
    """Top of the nth row of the list."""
    return ROW_Y + index * PITCH


def crown(s: pygame.Surface, x: int, y: int, color: tuple = YELLOW) -> None:
    pygame.draw.polygon(s, color, [(x - 7, y + 5), (x - 7, y - 4), (x - 3, y), (x, y - 6),
                                   (x + 3, y), (x + 7, y - 4), (x + 7, y + 5)])


def chevron(s: pygame.Surface, x: int, y: int, up: bool, color: tuple, size: int = 6) -> None:
    if up:
        pygame.draw.polygon(s, color, [(x, y - size), (x + size, y + size // 2),
                                       (x - size, y + size // 2)])
    else:
        pygame.draw.polygon(s, color, [(x, y + size), (x + size, y - size // 2),
                                       (x - size, y - size // 2)])


def signed_usdc(amount: Decimal) -> str:
    """+0.005, -1.50: at least two decimals, a third when the amount needs it."""
    micro = int(amount * MICRO)
    text = format_usdc(abs(micro), max(2, min(places_for(abs(micro)), 3)))
    return ('+' if micro > 0 else '-' if micro < 0 else '') + text


class BoardFeed:
    """Reads the standings on its own thread, so a slow Sepolia never stalls a frame.

    Nothing is read until the board is first wanted; after that it refreshes
    while the board is on screen and sleeps while it is not.

    While `hold` is set a good read is parked in `pending` instead of replacing
    `rows`, so the board can keep showing the old picture until it has run the
    movement from one to the other. Holding also polls hard: the scorekeeper
    writes a few seconds after the escrow closes, and twenty is a long time to
    stand in front of a board that is about to change.
    """
    REFRESH_S = 20.0
    RETRY_S = 5.0
    PENDING_S = 3.0

    def __init__(self, read: Callable[[], list] | None = None) -> None:
        self.read = read
        self.rows: list | None = None       # None until the first read lands
        self.pending: list | None = None    # a newer picture, held back for the movement
        self.hold = False
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
            rows, self.error, self.updated = self.read(), '', time.monotonic()
            if self.hold and self.rows is not None:
                self.pending = rows
            else:
                self.rows = rows
            return True
        except Exception as exc:    # Sepolia unreachable: keep the last rows, say so
            self.error = str(exc)[:80] or 'ENS UNREACHABLE'
            return False

    def take(self) -> list | None:
        """Let the held picture through, now that it has been shown arriving."""
        self.hold = False
        if self.pending is not None:
            self.rows, self.pending = self.pending, None
        return self.rows

    def _run(self) -> None:
        while True:
            self._wake.clear()
            ok = self.refresh()
            if not self.showing:
                wait = None
            elif not ok:
                wait = self.RETRY_S
            elif self.hold and self.pending is None:
                wait = self.PENDING_S
            else:
                wait = self.REFRESH_S
            self._wake.wait(wait)


def ease(p: float) -> float:
    return 1 - (1 - p) ** 3


def rank_of(rows: list, me: str) -> int | None:
    """The player's 0-based place in a list of standings, if they are in it."""
    if not me:
        return None
    me = me.lower()
    return next((i for i, row in enumerate(rows) if row.player.lower() == me), None)


class Move:
    """A rank change as a timeline, so the board is seen to change rather than
    found already changed.

    One adjacent swap per beat, up or down. Three shapes, because three things
    can actually happen to a player: they climb or slide inside the visible six
    (the swap, which is the one worth watching), they move while pinned below it
    (nothing to swap with, so the number itself counts), or they appear for the
    first time (nothing to move from, so the row drops in and stamps).
    """
    HOLD_S = 0.7            # the old picture, before anything moves
    STEP_S = 0.52           # one place, when there is a row to trade it with
    FLY_S = 0.9             # the same beat for a move with nothing to swap
    SETTLE_S = 1.7          # celebration for a climb, a quiet beat for a slide

    def __init__(self, before: list, after: list, me: str) -> None:
        self.before, self.after, self.me = before, after, me
        self.start = rank_of(before, me)         # 0-based, or None for a first run
        self.end = rank_of(after, me)
        self.new = self.start is None
        old_row = before[self.start] if self.start is not None else None
        new_row = after[self.end] if self.end is not None else None
        self.old_pnl = old_row.pnl if old_row else Decimal(0)
        self.new_pnl = new_row.pnl if new_row else self.old_pnl
        # A swap can only be drawn where both ends are on screen. Off the
        # bottom of the list there is no row to trade places with.
        self.swapping = (not self.new and self.end is not None
                         and self.start < TOP and self.end < TOP)
        self.steps = abs(self.end - self.start) if self.swapping else 0
        self.up = self.end < self.start if self.start is not None and self.end is not None else True
        # The beat the movement itself gets. A swap is paid for by the place:
        # anything else — a number counting, a row flying in — is one beat, so
        # the celebration still lands after the movement rather than over it.
        self.span = (self.steps * self.STEP_S) if self.swapping and self.steps else self.FLY_S
        self.length = self.HOLD_S + self.span + self.SETTLE_S
        self.t = 0.0

    def update(self, dt: float) -> None:
        self.t = min(self.length, self.t + dt)

    @property
    def done(self) -> bool:
        return self.t >= self.length

    @property
    def landed(self) -> float:
        """Seconds since the row came to rest; negative while it is still moving."""
        return self.t - (self.HOLD_S + self.span)

    @property
    def holding(self) -> bool:
        """The old picture is still up and the score has not been shown landing."""
        return self.t < self.HOLD_S

    def at(self) -> tuple[list, int | None, float]:
        """(rows in their order right now, the player's slot, how far through the
        beat between that slot and the next one)."""
        moving = max(0.0, self.t - self.HOLD_S)
        done = min(self.steps, int(moving // self.STEP_S))
        p = 0.0 if done >= self.steps else (moving - done * self.STEP_S) / self.STEP_S
        rows = list(self.before)
        at = self.start
        for _ in range(done):
            to = at - 1 if self.up else at + 1
            rows[at], rows[to] = rows[to], rows[at]
            at = to
        return rows, at, p

    def rank_now(self) -> int:
        """The rank the board is showing this instant, 1-based; 0 for a player
        with no rank to show yet."""
        if self.end is None:
            return 0
        if self.holding:
            # Nothing has been shown changing yet: the old number, or none at
            # all for a player who has never been on the board.
            return 0 if self.start is None else self.start + 1
        if self.start is None:              # first ever run: no old rank to leave
            return self.end + 1
        if self.swapping:
            _, at, p = self.at()
            rolled = p > .25
            return at + 1 + (-1 if self.up and rolled else 1 if not self.up and rolled else 0)
        # Nothing on screen to trade places with, so the number itself counts.
        return self.start + 1 + round((self.end - self.start) * ease(self.share))

    @property
    def share(self) -> float:
        """How far through the movement, 0 to 1."""
        return min(1.0, max(0.0, (self.t - self.HOLD_S) / self.span))

    def moved(self) -> int:
        """Places changed so far, read off the rank the board is showing, so the
        UP 2 mark and the number beside it can never disagree."""
        if self.start is None or self.holding:
            return 0
        return abs(self.rank_now() - (self.start + 1))

    def pnl_now(self) -> Decimal:
        """The player's P&L, counting up over the whole movement.

        Rounded to cents while it counts — a tenth of a cent flickering through
        a third decimal is noise — and exact the moment it comes to rest, so the
        number the board settles on is the one ENS actually holds.
        """
        if self.holding:
            return self.old_pnl
        share = self.share
        if share >= 1.0:
            return self.new_pnl
        value = self.old_pnl + (self.new_pnl - self.old_pnl) * Decimal(str(share))
        return value.quantize(Decimal('0.01'))


class BoardScreen:
    # How long to stand in front of an unchanged board before admitting the
    # scorekeeper is not coming. It writes seconds after the escrow closes, so
    # this is patience for a bad day, not the normal case.
    SCORE_WAIT_S = 45.0

    def __init__(self, game=None, feed: BoardFeed | None = None) -> None:
        self.game = game                # whose funding says who is playing
        self.feed = feed or BoardFeed()
        self.t = 0.0
        # Arrival mode: who just cashed out, what their run was worth, the
        # picture the board had before it, and the movement once it can run.
        self.arrived = ''
        self.pending_pnl: Decimal | None = None
        self.before: list | None = None
        self.move: Move | None = None
        self.waited = 0.0
        self.gave_up = False
        self.replay = False             # a movement has been seen: offer another run

    def open(self) -> None:
        self.feed.showing = True
        self.feed.want()
        if not self.arrived:        # an arrival has its own answer for this
            self.replay = False

    def close(self) -> None:
        self.feed.showing = False

    def arrive(self, player: str, pnl: Decimal) -> None:
        """Come in from the payout: hold the old picture and wait to be scored.

        `pnl` is what this run was worth, which is the one number the board
        cannot know until ENS is written — so it is shown ghosted beside the
        player's old row while the scorekeeper catches up.
        """
        self.arrived, self.pending_pnl = player, pnl
        self.before = list(self.feed.rows) if self.feed.rows is not None else None
        self.move, self.waited, self.gave_up = None, 0.0, False
        self.feed.hold = True
        self.feed.pending = None

    @property
    def waiting(self) -> bool:
        """Arrived from a payout, and the new score has not landed yet."""
        return bool(self.arrived) and self.move is None and not self.gave_up

    def settle(self) -> None:
        """Back to an ordinary board. Whatever is held is let through."""
        self.feed.take()
        self.arrived, self.pending_pnl, self.before, self.move = '', None, None, None
        self.waited, self.gave_up = 0.0, False

    def scored(self, rows: list) -> bool:
        """Has the scorekeeper written this run yet? A closed session shows up
        as one more play on the name, which is the only signal ENS gives us."""
        before = self.before or []
        was = rank_of(before, self.arrived)
        now = rank_of(rows, self.arrived)
        if now is None:
            return False
        return was is None or rows[now].sessions > before[was].sessions

    def update(self, dt: float) -> None:
        self.t += dt
        if self.move is not None:
            self.move.update(dt)
            if self.move.done:
                self.feed.take()
                self.move = None
                self.arrived, self.before, self.pending_pnl = '', None, None
                self.replay = True
            return
        if not self.waiting:
            return
        self.waited += dt
        if self.before is None and self.feed.rows is not None:
            # Arrived before the board had ever read. The first read that lands
            # is not held back, so adopt it as the picture to move from — every
            # read after it parks in `pending`, which is what we move to.
            self.before = list(self.feed.rows)
        pending = self.feed.pending
        if pending is not None and self.scored(pending):
            self.move = Move(self.before, pending, self.arrived)
        elif self.waited > self.SCORE_WAIT_S:
            # Say so and go back to being a board, rather than spin forever.
            self.gave_up = True
            self.replay = True
            self.feed.take()

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
            if self.again:
                return 'money'          # the loop closes: back to INSERT COIN
            self.feed.want()
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if pos[1] >= 274:
            return self.handle_action(InputAction.A if pos[0] >= 240 else InputAction.B)
        return None

    # ---- drawing -----------------------------------------------------------
    def rows_now(self) -> list | None:
        """The list the board is showing: what it has, or what it is moving through."""
        move = self.move
        if move is None:
            return self.feed.rows
        if move.holding:
            return move.before
        return move.at()[0] if move.swapping else move.after

    def draw(self, s: pygame.Surface) -> None:
        s.fill(NAVY)
        rows = self.rows_now()
        self.draw_head(s, rows)
        if rows is None:
            if self.feed.error:
                self.note(s, 'ENS UNREACHABLE', 'RETRYING' + '.' * (int(self.t * 2) % 4), RED)
            else:
                self.note(s, 'READING tick.eth ON ENS' + '.' * (int(self.t * 2) % 4),
                          'SEPOLIA / UNIVERSAL RESOLVER', CREAM)
        elif not rows and not self.me():
            self.note(s, 'NO PLAYERS YET', 'ADD USDC AND PLAY TO GET A tick.eth NAME', CREAM)
        elif self.move is not None:
            self.draw_move(s, self.move)
        else:
            self.draw_list(s, rows)
        self.draw_strip(s)
        footer(s, '< HOME', self.go_label())

    def go_label(self) -> str:
        """After a movement has landed, another run is the natural next thing."""
        return 'PLAY AGAIN >' if self.again else 'REFRESH >'

    @property
    def again(self) -> bool:
        return self.replay or (self.move is not None and self.move.landed >= 0)

    def scale(self, rows: list) -> Decimal:
        """The P&L the widest plate bar stands for: the board's own best."""
        top = max((abs(row.pnl) for row in rows), default=Decimal(0))
        return top if top > 0 else Decimal(1)

    # -- the list, standing still
    def draw_list(self, s: pygame.Surface, rows: list) -> None:
        me = self.me()
        placed = self.layout(rows, me)
        scale = self.scale(rows)
        if placed and placed[-1][0] == YOU_Y and len(rows) > TOP - 1:
            self.cut(s, YOU_Y - 4)      # the list is not continuous here
        # Standing still but waiting to be scored: the run's P&L is not on the
        # board yet, so it sits ghosted beside the row it is about to change.
        ghost = (f'{signed_usdc(self.pending_pnl)} >'
                 if self.waiting and self.pending_pnl is not None else None)
        for y, rank, row, mine in placed:
            if row is None:
                self.draw_unranked(s, y, me)
            else:
                self.draw_row(s, y, rank, row, scale, mine=mine,
                              ghost=ghost if mine else None)

    # -- the list, moving
    def draw_move(self, s: pygame.Surface, move: Move) -> None:
        """Two shapes. Inside the visible list a move is a swap, and the row it
        passes has to move too. Anywhere else there is nothing to trade places
        with, so the row simply flies from where it was to where it lands —
        which covers a player pinned below the list, one climbing into it or
        dropping out of it, and one arriving on the board for the first time."""
        if move.swapping:
            self.draw_swap(s, move)
        else:
            self.draw_fly(s, move)

    def ghost_mark(self, move: Move) -> tuple:
        """The two things that can sit in the narrow column beside your row:
        the score still landing, then how far it moved you."""
        if move.holding:
            return ((f'{signed_usdc(self.pending_pnl)} >'
                     if self.pending_pnl is not None else None), None)
        if move.new:
            return None, ((True, 'NEW ENTRY') if move.share >= 1 else None)
        moved = move.moved()
        return None, ((move.up, f'{"UP" if move.up else "DOWN"} {moved}') if moved else None)

    def draw_swap(self, s: pygame.Surface, move: Move) -> None:
        rows, at, p = move.at()
        scale = self.scale(rows)
        ghost, mark = self.ghost_mark(move)
        skip = {at, (at - 1 if move.up else at + 1)} if p else {at}
        for i, row in enumerate(rows[:TOP]):
            if i not in skip:
                self.draw_row(s, slot_y(i), i + 1, row, scale)
        if p:
            # The row being passed slides the other way, and its number rolls at
            # the same moment as the player's, so the two never read as one rank.
            other = at - 1 if move.up else at + 1
            y = slot_y(other) + (slot_y(at) - slot_y(other)) * ease(p)
            self.draw_row(s, y, other + 1 if p <= .25 else at + 1, rows[other], scale)
        to = at - 1 if move.up else at + 1
        y = slot_y(at) + ((slot_y(to) - slot_y(at)) * ease(p) if p else 0)
        self.draw_row(s, y, move.rank_now(), rows[at], scale, mine=True,
                      lift=int(8 * math.sin(math.pi * p)) if p else 0,
                      pnl=move.pnl_now(), ghost=ghost, mark=mark)

    def draw_fly(self, s: pygame.Surface, move: Move) -> None:
        rows = move.before if move.holding else move.after
        scale = self.scale(rows)
        mine = rank_of(rows, self.arrived)
        pinned = mine is None or mine >= TOP
        for i, row in enumerate(rows[:TOP - 1 if pinned else TOP]):
            if i != mine:
                self.draw_row(s, slot_y(i), i + 1, row, scale)
        if pinned:
            self.cut(s, YOU_Y - 4)          # the list is not continuous here

        start = place_y(move.start)
        y = start if move.holding else start + (place_y(move.end) - start) * ease(move.share)
        row = move.before[move.start] if move.holding and move.start is not None else None
        row = row or (move.after[move.end] if move.end is not None else None)
        ghost, mark = self.ghost_mark(move)
        if row is None:                     # never been scored: no row to fly yet
            self.draw_unranked(s, round(y), self.arrived)
            return
        self.draw_row(s, y, move.rank_now(), row, scale, mine=True,
                      pnl=move.pnl_now(), ghost=ghost, mark=mark)

    # -- one plate
    def draw_row(self, s: pygame.Surface, y: float, rank: int, row, scale: Decimal,
                 mine: bool = False, lift: int = 0, pnl: Decimal | None = None,
                 ghost: str | None = None, mark: tuple | None = None) -> None:
        """The P&L bar is the plate's own fill, so no column can collide with it."""
        value = row.pnl if pnl is None else pnl
        rect = pygame.Rect(12, round(y) - lift, 456, ROW_H)
        if lift:
            pygame.draw.rect(s, (6, 14, 20), rect.move(2, lift + 3), border_radius=4)
        pygame.draw.rect(s, PANEL, rect, border_radius=4)
        span = max(6, int(min(1.0, abs(value) / scale) * (rect.w - 6)))
        pygame.draw.rect(s, BAR_UP if value >= 0 else BAR_DOWN,
                         (rect.x + 3, rect.y + 3, span, rect.h - 6), border_radius=3)
        if mine:
            pulse = .5 + .5 * math.sin(self.t * 4)
            pygame.draw.rect(s, mix(YELLOW, CREAM, .25 * pulse), rect, 2, border_radius=4)

        handle = row.name.removesuffix('.tick.eth')
        if rank == 1:
            crown(s, 26, rect.y + 9)
        else:
            say_right(s, str(rank) if rank else '-', 36, rect.y + 5, 15,
                      MEDALS.get(rank, MUTED))
        say(s, handle, 46, rect.y + 5, 15, CREAM)
        if mine:
            self.you(s, handle, rect.y + 3)
        say_right(s, signed_usdc(value), PNL_R, rect.y + 5, 15,
                  MINT if value > 0 else RED if value < 0 else CREAM)
        say_right(s, signed_usdc(row.best), BEST_R, rect.y + 6, 13, MUTED)
        say_right(s, str(row.wins), WINS_R, rect.y + 5, 15, CREAM)
        say_right(s, str(row.sessions), PLAYS_R, rect.y + 5, 15, CREAM)
        if ghost:
            say(s, ghost, MOVE_X, rect.y + 6, 13, YELLOW)
        elif mark:
            up, text = mark
            color = MINT if up else MUTED
            chevron(s, MOVE_X + 6, rect.centery, up, color)
            say(s, text, MOVE_X + 18, rect.y + 7, 11, color)

    def draw_unranked(self, s: pygame.Surface, y: int, me: str) -> None:
        """The player on the device before the scorekeeper has scored a session."""
        rect = pygame.Rect(12, y, 456, ROW_H)
        pygame.draw.rect(s, PANEL, rect, border_radius=4)
        pygame.draw.rect(s, YELLOW, rect, 2, border_radius=4)
        name = getattr(self.funding, 'names', {}).get(me)
        handle = name.removesuffix('.tick.eth') if name else short_address(me)
        say_right(s, '-', 36, y + 5, 15, MUTED)
        say(s, handle, 46, y + 5, 15, CREAM)
        self.you(s, handle, y + 3)
        say_right(s, self.waiting_note(), PLAYS_R, y + 7, 11, MUTED)

    def you(self, s: pygame.Surface, handle: str, y: int) -> None:
        say(s, 'YOU', 46 + font(15).size(handle)[0] + 8, y + 4, 11, YELLOW)

    @staticmethod
    def cut(s: pygame.Surface, y: int) -> None:
        """A dashed rule where the list skips the players in between."""
        for x in range(20, 460, 12):
            pygame.draw.line(s, (46, 66, 78), (x, y), (x + 5, y), 2)

    # -- chrome
    def draw_head(self, s: pygame.Surface, rows: list | None) -> None:
        say(s, 'LEADERBOARD', 12, 6, 22, YELLOW)
        rank = self.my_rank(rows)
        if rank:
            say_right(s, f'#{rank}', 468, 8, 18, YELLOW)
            say_right(s, 'YOU', 468 - font(18).size(f'#{rank}')[0] - 10, 13, 12, MUTED)
        self.draw_source(s)
        if rows:
            y = 54
            say_right(s, '#', 36, y, 11, MUTED)
            say(s, 'PLAYER', 46, y, 11, MUTED)
            for title, right in (('P&L', PNL_R), ('BEST', BEST_R),
                                 ('WINS', WINS_R), ('PLAYS', PLAYS_R)):
                say_right(s, title, right, y, 11, MUTED)

    def my_rank(self, rows: list | None) -> int:
        if self.move is not None:
            return self.move.rank_now()
        place = rank_of(rows or [], self.me())
        return 0 if place is None else place + 1

    def draw_source(self, s: pygame.Surface) -> None:
        """Where the rows come from, and how fresh they are."""
        feed = self.feed
        source = 'LIVE FROM tick.eth ON ENS'
        say_right(s, source, 464, 34, 11, CREAM)
        if feed.rows is not None and not feed.error and int(self.t * 2) % 2 == 0:
            pygame.draw.circle(s, RED, (464 - font(11).size(source)[0] - 8, 40), 3)
        if feed.rows is None:
            return
        age = int(time.monotonic() - feed.updated)
        if feed.error:
            say(s, f'OFFLINE / LAST READ {age}s AGO', 12, 34, 11, RED)
        else:
            count = len(feed.rows)
            say(s, f'{count} PLAYER{"" if count == 1 else "S"} / {age}s AGO', 12, 34, 11, MUTED)

    def draw_strip(self, s: pygame.Surface) -> None:
        """The one line under the list: what the board is waiting for, or what
        just happened to you."""
        move = self.move
        if move is not None and move.landed >= 0:
            self.finish(s, move)
            return
        if self.waiting or (move is not None and move.holding):
            self.banner(s, 'SCORING YOUR RUN ON ENS ' + '>' * (1 + int(self.t * 4) % 3),
                        YELLOW, 1)
        elif self.gave_up:
            say(s, 'STILL SCORING ON ENS / LOOK AGAIN IN A MINUTE', 240, 253, 13, MUTED, True)

    def finish(self, s: pygame.Surface, move: Move) -> None:
        """What landing looks like: a party for a climb or a first entry, a quiet
        line for a slide, and nothing at all for a run that changed no place."""
        if not move.new and (not move.up or not move.moved()):
            say(s, 'THAT ONE COST YOU. GO AGAIN?' if move.moved() else 'SAME PLACE. GO AGAIN?',
                240, 253, 13, MUTED, True)
            return
        ct = move.landed
        self.confetti(s, ct, place_y(move.end))
        if ct > .2:
            if move.end is not None and move.end < 3:
                text = 'ON THE PODIUM!'
            elif move.new:
                text = 'ON THE BOARD!'
            else:
                text = f'UP {move.moved()} PLACES!'
            self.banner(s, text, YELLOW, 2, min(1.0, (ct - .2) / .22))

    @staticmethod
    def banner(s: pygame.Surface, text: str, color: tuple, edge: int,
               grow: float = 1.0) -> None:
        """The strip under the list. `grow` opens it out from the middle, so a
        celebration arrives rather than appearing."""
        rect = STRIP.copy()
        if grow < 1.0:
            rect.width = max(2, int(STRIP.width * grow))
            rect.centerx = STRIP.centerx
        pygame.draw.rect(s, NOTE_FILL, rect, border_radius=4)
        pygame.draw.rect(s, color, rect, edge, border_radius=4)
        if grow > .55:
            say(s, text, 240, rect.y + 3, 13, color, True)

    def confetti(self, s: pygame.Surface, ct: float, y: int) -> None:
        """Off the plate and over the list. Positions come from the clock, so
        there is no particle list to keep and nothing to update between frames."""
        rng = random.Random(11)
        for _ in range(70):
            vx, vy = rng.uniform(-190, 190), rng.uniform(-250, -110)
            px = rng.uniform(120, 360) + vx * ct
            py = y + ROW_H / 2 + vy * ct + 300 * ct * ct
            if py > 274 or not 8 < px < 472:
                continue
            size = rng.choice((2, 3, 4))
            pygame.draw.rect(s, rng.choice((YELLOW, MINT, CREAM)), (int(px), int(py), size, size))

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
