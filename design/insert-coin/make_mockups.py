"""Render the proposed CASHIER and LEADERBOARD screens as 480x320 mockups.

Not running firmware: these are drawn here, by hand, to be looked at and argued
with. The palette, fonts and the night-city background come from the real game
(firmware/ui.py, firmware/games/box_scene.py), so what you see is what the panel
would show.

    cd design/insert-coin && ../../firmware/.venv/bin/python make_mockups.py

The leaderboard move is written out as frames and encoded to GIF with ffmpeg.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'firmware'))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame  # noqa: E402

from ui import NAVY, PANEL, GRID, CREAM, MUTED, YELLOW, MINT, RED, font, footer  # noqa: E402
from games.box_scene import Rider, Skyline  # noqa: E402

W, H = 480, 320
HORIZON, STREET_BOTTOM = 242, 274          # the game's own street, reused
HERE = Path(__file__).resolve().parent
LOGO_LOW = (196, 104, 28)
BRONZE = (214, 140, 76)
PAPER = (238, 231, 208)
INK = (26, 34, 40)
COIN_HI = (255, 224, 130)
COIN_LO = (196, 140, 28)
SHADOW = (6, 14, 20)
FPS = 20


# ---- small drawing helpers -------------------------------------------------

def say(s, words, x, y, size=16, color=CREAM, center=False, right=False):
    art = font(size).render(words, False, color)
    if center:
        s.blit(art, art.get_rect(midtop=(x, y)))
    elif right:
        s.blit(art, art.get_rect(topright=(x, y)))
    else:
        s.blit(art, (x, y))
    return art.get_width()


def marquee(s, words, y, size=40, color=YELLOW, bob=True):
    """The launcher's chunky arcade logo treatment, each letter a beat behind."""
    big = font(size)
    x0 = W // 2 - big.size(words)[0] // 2
    for i, ch in enumerate(words):
        if ch == ' ':
            continue
        x = x0 + big.size(words[:i])[0]
        dy = round(3 * math.sin(i * .55)) if bob else 0
        s.blit(big.render(ch, False, SHADOW), (x + 3, y + dy + 7))
        s.blit(big.render(ch, False, LOGO_LOW), (x, y + dy + 4))
        s.blit(big.render(ch, False, color), (x, y + dy))


def panel(s, rect, fill=PANEL, edge=GRID, width=1, radius=5):
    pygame.draw.rect(s, fill, rect, border_radius=radius)
    if edge:
        pygame.draw.rect(s, edge, rect, width, border_radius=radius)


def coin(s, x, y, r=9, face='$'):
    pygame.draw.circle(s, COIN_LO, (int(x), int(y)), r)
    pygame.draw.circle(s, YELLOW, (int(x), int(y)), r - 2)
    pygame.draw.circle(s, COIN_HI, (int(x - r // 3), int(y - r // 3)), max(1, r // 3))
    if r >= 8:
        art = font(r + 2).render(face, False, COIN_LO)
        s.blit(art, art.get_rect(center=(int(x), int(y))))


def bill(s, x, y, w=54, h=30, angle=0.0, tint=MINT):
    """A flying USDC note: drawn flat, then rotated."""
    note = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(note, PAPER, (0, 0, w, h), border_radius=3)
    pygame.draw.rect(note, tint, (0, 0, w, h), 2, border_radius=3)
    pygame.draw.circle(note, tint, (w // 2, h // 2), h // 4, 2)
    for i in (6, h - 8):
        pygame.draw.line(note, (176, 170, 150), (5, i), (w - 6, i), 1)
    art = font(9).render('USDC', False, INK)
    note.blit(art, art.get_rect(center=(w // 2, h // 2)))
    turned = pygame.transform.rotate(note, angle)
    s.blit(turned, turned.get_rect(center=(x, y)))


def qr_image(text, size):
    import qrcode
    code = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(text)
    code.make(fit=True)
    matrix = code.get_matrix()
    cell = max(1, size // len(matrix))
    image = pygame.Surface((len(matrix) * cell, len(matrix) * cell))
    image.fill((255, 255, 255))
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                image.fill((0, 0, 0), (x * cell, y * cell, cell, cell))
    return image


ADDRESS = '0x3E0A1f4c9b228d7eA4c6135f0b71D9e2C88F562E'
QR_TEXT = f'ethereum:{ADDRESS}@5042002'


def slot(s, rect, lit=YELLOW):
    """An arcade coin slot: a dark capsule in a lit plate."""
    panel(s, rect, fill=(18, 32, 42), edge=lit, width=2, radius=4)
    inner = pygame.Rect(rect.x + 10, rect.centery - 4, rect.w - 20, 8)
    pygame.draw.rect(s, SHADOW, inner, border_radius=4)
    pygame.draw.rect(s, lit, inner, 1, border_radius=4)


def chevron(s, x, y, up=True, color=MINT, size=7):
    if up:
        pygame.draw.polygon(s, color, [(x, y - size), (x + size, y + size // 2),
                                       (x - size, y + size // 2)])
    else:
        pygame.draw.polygon(s, color, [(x, y + size), (x + size, y - size // 2),
                                       (x - size, y - size // 2)])


def new_screen():
    s = pygame.Surface((W, H))
    s.fill(NAVY)
    return s


def head(s, left='CASHIER', right='ARC TESTNET', right_color=MUTED):
    say(s, left, 12, 6, 18, YELLOW)
    say(s, right, 468, 9, 13, right_color, right=True)
    pygame.draw.line(s, GRID, (0, 30), (W, 30))


# ---- 01 INSERT COIN ---------------------------------------------------------

_skyline = None


def city(s, top=10, low=68):
    """The game's own night city behind the cashier.

    The veil is a gradient: light at the top so the moon and stars keep their
    look, heavier down at the window band where the text has to stay readable.
    """
    global _skyline
    if _skyline is None:
        _skyline = Skyline(W, HORIZON, STREET_BOTTOM, seed=3)
    _skyline.draw(s, 0, 3.0)                 # a clock the lit windows have caught up with
    shade = pygame.Surface((W, STREET_BOTTOM), pygame.SRCALPHA)
    for y in range(STREET_BOTTOM):
        share = min(1.0, y / HORIZON)
        shade.fill((*NAVY, int(top + (low - top) * share)), (0, y, W, 1))
    s.blit(shade, (0, 0))


def waiting_rider(s, x=330, ground=268):
    """The kid from the game, parked on the street with nothing to do yet."""
    rider = Rider()
    for _ in range(26):                      # let the idle sway settle somewhere natural
        rider.update(1 / 30, 0.0, False)
    rider.draw(s, x, ground, 0.0)
    bubble = pygame.Rect(x + 22, ground - 58, 46, 30)
    panel(s, bubble, fill=(18, 32, 42), edge=MUTED, width=1, radius=6)
    pygame.draw.polygon(s, (18, 32, 42), [(bubble.x + 2, bubble.bottom - 8),
                                          (bubble.x + 1, bubble.bottom + 2),
                                          (bubble.x + 12, bubble.bottom - 1)])
    coin(s, bubble.centerx, bubble.centery, 9)


def insert_coin():
    """Waiting for money. The QR is the coin slot, and it is the only job here.

    Everything is packed into the top two thirds so the game's own street stays
    open along the bottom, with the rider waiting on it for someone to pay.
    """
    s = new_screen()
    city(s)
    head(s)
    marquee(s, 'INSERT COIN', 26, 32)

    bezel = pygame.Rect(16, 72, 136, 136)
    panel(s, bezel, fill=(14, 28, 38), edge=YELLOW, width=2, radius=6)
    slot(s, pygame.Rect(bezel.x + 15, bezel.y + 7, bezel.w - 30, 15))
    qr = qr_image(QR_TEXT, 100)
    s.blit(qr, qr.get_rect(center=(bezel.centerx, bezel.centery + 13)))
    say(s, 'SCAN TO INSERT', bezel.centerx, bezel.bottom + 5, 13, YELLOW, center=True)

    x = 166
    say(s, 'SEND USDC ON ARC', x, 80, 20, CREAM)
    box = pygame.Rect(x - 6, 112, 292, 44)
    panel(s, box, fill=(16, 30, 40))
    say(s, ADDRESS[:21], x + 2, 117, 13, MUTED)
    say(s, ADDRESS[21:], x + 2, 135, 13, MUTED)
    pygame.draw.circle(s, RED, (x + 7, 182), 5)
    say(s, 'WAITING FOR COINS...', x + 20, 174, 15, CREAM)

    waiting_rider(s)
    footer(s, '< BACK', '')
    return s


# ---- 02 COIN DROP -----------------------------------------------------------

def coin_drop():
    """The deposit landing. 2.5 seconds, and the one moment worth a takeover."""
    s = new_screen()
    rng = random.Random(7)
    spots = []
    while len(spots) < 20:
        cx, cy = rng.randrange(16, 464), rng.randrange(22, 250)
        if 64 < cy < 252 and 84 < cx < 396:     # keep the middle clear for the numbers
            continue
        spots.append((cx, cy, rng.choice((6, 7, 9, 11))))
    for cx, cy, r in spots:
        pygame.draw.line(s, (40, 62, 76), (cx, cy - r - 14), (cx, cy - r - 4), 2)
        coin(s, cx, cy, r)

    plate = pygame.Rect(96, 66, 288, 68)
    panel(s, plate, fill=(16, 44, 40), edge=MINT, width=2, radius=6)
    marquee(s, '+25.00', plate.y + 8, 42, MINT, bob=False)
    say(s, 'FROM amber-otter.tick.eth', 240, 142, 15, CREAM, center=True)

    say(s, 'CREDIT', 240, 172, 13, MUTED, center=True)
    marquee(s, '25.00 USDC', 190, 30, CREAM, bob=False)
    say(s, 'COINS ARE IN. GO.', 240, 246, 15, YELLOW, center=True)
    footer(s, 'HOME', 'PLAY NOW >')
    return s


# ---- 04 PAYING OUT ----------------------------------------------------------

def paying():
    """Bills flying out of the slot while Arc confirms. The wait becomes the show."""
    s = new_screen()
    marquee(s, 'CASHING OUT', 10, 32)

    steps = ((True, 'FINISHING THE LIVE BOX'), (True, 'CLOSING SESSION ON ARC'),
             (False, 'SENDING 137.40 USDC'))
    for i, (done, text) in enumerate(steps):
        y = 86 + i * 34
        color = MINT if done else YELLOW
        if done:
            pygame.draw.lines(s, MINT, False, [(20, y + 10), (26, y + 16), (38, y + 2)], 3)
        else:
            pygame.draw.arc(s, YELLOW, (18, y - 1, 20, 20), 0.6, 4.4, 3)
        say(s, text, 48, y, 15, color)
    say(s, 'TO amber-otter.tick.eth', 48, 190, 13, MUTED)

    front = pygame.Rect(286, 208, 186, 54)
    panel(s, front, fill=(18, 32, 42), edge=MINT, width=2, radius=5)
    mouth = pygame.Rect(front.x + 16, front.y + 10, front.w - 32, 12)
    pygame.draw.rect(s, SHADOW, mouth, border_radius=4)
    pygame.draw.rect(s, MINT, mouth, 1, border_radius=4)
    say(s, 'CASH TRAY', front.centerx, front.bottom - 20, 11, MUTED, center=True)
    for x, y, a in ((362, 170, 16), (398, 128, -14), (330, 120, 8), (434, 168, 30)):
        bill(s, x, y, angle=a)

    footer(s, '', '')
    return s


# ---- 05 RECEIPT -------------------------------------------------------------

def receipt():
    """A printed ticket, the way the machine hands you one."""
    s = new_screen()
    say(s, 'TICK ARCADE', 240, 8, 15, MUTED, center=True)

    card = pygame.Rect(56, 30, 368, 214)
    pygame.draw.rect(s, PAPER, card, border_radius=3)
    for x in range(card.x, card.right - 6, 12):     # torn bottom edge
        pygame.draw.polygon(s, NAVY, [(x, card.bottom - 8), (x + 6, card.bottom + 1),
                                      (x + 12, card.bottom - 8), (x + 12, card.bottom + 2),
                                      (x, card.bottom + 2)])

    def ink(words, y, size=15, color=INK):
        art = font(size).render(words, False, color)
        s.blit(art, art.get_rect(midtop=(card.centerx, y)))

    ink('PAID OUT', 42, 17, (92, 104, 110))
    ink('+137.40 USDC', 60, 36, (22, 112, 84))
    ink('to amber-otter.tick.eth', 104, 15)
    pygame.draw.line(s, (176, 170, 150), (card.x + 18, 130), (card.right - 18, 130))
    for i, (title, value) in enumerate((('IN', '100.00'), ('OUT', '137.40'), ('P&L', '+155.80'))):
        cx = card.x + 62 + i * 122
        art = font(11).render(title, False, (122, 130, 134))
        s.blit(art, art.get_rect(midtop=(cx, 140)))
        art = font(19).render(value, False, (22, 112, 84) if i == 2 else INK)
        s.blit(art, art.get_rect(midtop=(cx, 156)))
    ink('12 BOXES  /  7 HITS  /  BEST WIN +48.00', 186, 13, (92, 104, 110))
    ink('TX 0x91ab...77c2', 206, 11, (122, 130, 134))

    say(s, 'YOUR RANK IS UPDATING >>>', 240, 252, 13, YELLOW, center=True)
    footer(s, 'HOME', 'SEE YOUR RANK >')
    return s


# ---- the leaderboard --------------------------------------------------------

ME = 'amber-otter'
# The run takes amber-otter from last of six to the podium: -18.40 -> +137.40.
CLIMB_BEFORE = [('turbo-lynx', 812.00, 90, 9, 14), ('misty-crab', 402.50, 55, 6, 11),
                ('neon-yak', 101.00, 30, 4, 9), ('sly-moose', 52.00, 22, 3, 8),
                ('quiet-vole', 12.00, 14, 2, 7), (ME, -18.40, 28, 6, 11)]
CLIMB_AFTER = 137.40
# The mirror: a bad run drops the same player from the podium to last.
SLIDE_BEFORE = [('turbo-lynx', 812.00, 90, 9, 14), ('misty-crab', 402.50, 55, 6, 11),
                (ME, 137.40, 48, 7, 12), ('neon-yak', 101.00, 30, 4, 9),
                ('sly-moose', 52.00, 22, 3, 8), ('quiet-vole', 12.00, 14, 2, 7)]
SLIDE_AFTER = -26.40

MEDALS = {1: YELLOW, 2: CREAM, 3: BRONZE}
ROW_Y, PITCH, ROW_H = 70, 30, 26
MOVE_X = 190                                    # the small up/down column
PNL_R, BEST_R, WINS_R, PLAYS_R = 326, 386, 420, 462
TOP_PNL = 812.0


def slot_y(index):
    return ROW_Y + index * PITCH


def board_head(s, you, sub='LIVE FROM tick.eth ON ENS'):
    say(s, 'LEADERBOARD', 12, 6, 22, YELLOW)
    width = say(s, you, 468, 8, 18, YELLOW, right=True)
    say(s, 'YOU', 468 - width - 10, 13, 12, MUTED, right=True)
    say(s, sub, 468, 34, 11, MUTED, right=True)
    y = 54
    say(s, '#', 36, y, 11, MUTED, right=True)
    say(s, 'PLAYER', 46, y, 11, MUTED)
    for title, right in (('P&L', PNL_R), ('BEST', BEST_R), ('WINS', WINS_R), ('PLAYS', PLAYS_R)):
        say(s, title, right, y, 11, MUTED, right=True)


def crown(s, x, y, color=YELLOW):
    pygame.draw.polygon(s, color, [(x - 7, y + 5), (x - 7, y - 4), (x - 3, y), (x, y - 6),
                                   (x + 3, y), (x + 7, y - 4), (x + 7, y + 5)])


def board_row(s, y, rank, row, mine=False, lift=0, ghost=None, mark=None, pnl=None):
    """One plate. The P&L bar is the plate's own fill, so no column can collide with it."""
    name, row_pnl, best, wins, plays = row
    value = row_pnl if pnl is None else pnl
    rect = pygame.Rect(12, int(y) - lift, 456, ROW_H)
    if lift:
        pygame.draw.rect(s, SHADOW, rect.move(2, lift + 3), border_radius=4)
    pygame.draw.rect(s, PANEL, rect, border_radius=4)
    span = max(6, int(min(1.0, abs(value) / TOP_PNL) * (rect.w - 6)))
    tint = (24, 58, 48) if value >= 0 else (58, 30, 32)
    pygame.draw.rect(s, tint, (rect.x + 3, rect.y + 3, span, rect.h - 6), border_radius=3)
    if mine:
        pygame.draw.rect(s, YELLOW, rect, 2, border_radius=4)

    if rank == 1:
        crown(s, 26, rect.y + 9)
    else:
        say(s, str(rank), 36, rect.y + 5, 15, MEDALS.get(rank, MUTED), right=True)
    say(s, name, 46, rect.y + 5, 15, CREAM)
    if mine:
        say(s, 'YOU', 46 + font(15).size(name)[0] + 8, rect.y + 8, 11, YELLOW)
    say(s, f'{value:+,.2f}', PNL_R, rect.y + 5, 15,
        MINT if value > 0 else RED if value < 0 else CREAM, right=True)
    say(s, f'+{best:.0f}', BEST_R, rect.y + 6, 13, MUTED, right=True)
    say(s, str(wins), WINS_R, rect.y + 5, 15, CREAM, right=True)
    say(s, str(plays), PLAYS_R, rect.y + 5, 15, CREAM, right=True)
    if ghost:
        say(s, ghost, MOVE_X, rect.y + 6, 13, YELLOW)
    if mark:
        up, text = mark
        color = MINT if up else MUTED
        chevron(s, MOVE_X + 6, rect.centery, up, color, 6)
        say(s, text, MOVE_X + 18, rect.y + 7, 11, color)


def board_before():
    """Arriving from the cash out: your OLD rank, and the score still landing."""
    s = new_screen()
    board_head(s, '#6')
    for i, row in enumerate(CLIMB_BEFORE):
        board_row(s, slot_y(i), i + 1, row, mine=row[0] == ME,
                  ghost='+155.80 >' if row[0] == ME else None)
    note = pygame.Rect(12, 250, 456, 22)
    panel(s, note, fill=(50, 44, 18), edge=YELLOW, width=1, radius=4)
    say(s, 'SCORING YOUR RUN ON ENS >>>', 240, 253, 13, YELLOW, center=True)
    footer(s, '< HOME', 'REFRESH >')
    return s


# ---- the move, one place at a time ------------------------------------------

HOLD_S = 0.7            # the old picture, before anything moves
STEP_S = 0.52           # one place
SETTLE_S = 1.7          # celebration (up) or a quiet beat (down)


def ease(p):
    return 1 - (1 - p) ** 3


class Move:
    """The climb (or slide) as a timeline: one adjacent swap per step."""

    def __init__(self, before, final_pnl):
        self.before = list(before)
        self.start = next(i for i, row in enumerate(self.before) if row[0] == ME)
        self.old_pnl = self.before[self.start][1]
        self.new_pnl = final_pnl
        after = [row for row in self.before if row[0] != ME]
        mine = self.before[self.start]
        target = len([row for row in after if row[1] > final_pnl])
        after.insert(target, (mine[0], final_pnl, mine[2], mine[3] + 1, mine[4] + 1))
        self.after = after
        self.end = target
        self.up = target < self.start
        self.steps = abs(target - self.start)
        self.length = HOLD_S + self.steps * STEP_S + SETTLE_S

    def order_after(self, done):
        """The list once `done` swaps have happened."""
        rows = list(self.before)
        at = self.start
        for _ in range(done):
            to = at - 1 if self.up else at + 1
            rows[at], rows[to] = rows[to], rows[at]
            at = to
        return rows, at

    def frame(self, t):
        s = new_screen()
        moving = max(0.0, t - HOLD_S)
        done = min(self.steps, int(moving // STEP_S))
        p = 0.0 if done >= self.steps else (moving - done * STEP_S) / STEP_S
        rows, at = self.order_after(done)
        climbed = done + (p if done < self.steps else 0)
        progress = climbed / self.steps if self.steps else 1.0
        pnl = self.old_pnl + (self.new_pnl - self.old_pnl) * progress
        rolled = p > .25                    # ease() puts the visual crossing at p~.21
        rank_now = at + 1 - (1 if self.up and rolled else 0) + (1 if not self.up and rolled else 0)

        board_head(s, f'#{rank_now}')
        # everyone standing still
        for i, row in enumerate(rows):
            if i == at or (p and i == (at - 1 if self.up else at + 1)):
                continue
            board_row(s, slot_y(i), i + 1, row)
        if p:                                   # the row being passed, sliding the other way
            other = at - 1 if self.up else at + 1
            y = slot_y(other) + (slot_y(at) - slot_y(other)) * ease(p)
            # Its number rolls at the same moment the player's does, so the two
            # rows never read as the same rank.
            board_row(s, y, (other + 1) if p <= .25 else (at + 1), rows[other])
        # the player, lifted over the list
        to = at - 1 if self.up else at + 1
        y = slot_y(at) + ((slot_y(to) - slot_y(at)) * ease(p) if p else 0)
        lift = int(8 * math.sin(math.pi * p)) if p else 0
        moved = done + (1 if rolled else 0)
        mark = (self.up, f'{"UP" if self.up else "DOWN"} {moved}') if moved else None
        board_row(s, y, rank_now, rows[at], mine=True, lift=lift, pnl=pnl,
                  ghost=f'{self.new_pnl - self.old_pnl:+,.2f} >' if t < HOLD_S else None,
                  mark=None if t < HOLD_S else mark)

        if t < HOLD_S:
            note = pygame.Rect(12, 250, 456, 22)
            panel(s, note, fill=(50, 44, 18), edge=YELLOW, width=1, radius=4)
            say(s, 'SCORING YOUR RUN ON ENS >>>', 240, 253, 13, YELLOW, center=True)
            footer(s, '< HOME', 'REFRESH >')
            return s

        landed = t - (HOLD_S + self.steps * STEP_S)
        if landed >= 0:
            self.finish(s, landed, slot_y(self.end))
        footer(s, '< HOME', 'PLAY AGAIN >' if landed >= 0 else 'REFRESH >')
        return s

    def finish(self, s, ct, y):
        """What landing looks like: a party for a climb, a quiet line for a slide."""
        if not self.up:
            say(s, 'THAT ONE COST YOU. GO AGAIN?', 240, 252, 13, MUTED, center=True)
            return
        rng = random.Random(11)
        for _ in range(70):
            vx = rng.uniform(-190, 190)
            vy = rng.uniform(-250, -110)
            px = rng.uniform(120, 360) + vx * ct
            py = y + ROW_H / 2 + vy * ct + 300 * ct * ct
            if py > STREET_BOTTOM or not 8 < px < 472:
                continue
            size = rng.choice((2, 3, 4))
            pygame.draw.rect(s, rng.choice((YELLOW, MINT, CREAM)), (int(px), int(py), size, size))
        if ct > .2:
            grow = min(1.0, (ct - .2) / .22)
            width = int(216 * grow)
            banner = pygame.Rect(240 - width // 2, 250, width, 22)
            panel(s, banner, fill=(50, 44, 18), edge=YELLOW, width=2, radius=5)
            if grow > .55:
                say(s, 'ON THE PODIUM!', 240, 253, 15, YELLOW, center=True)


# ---- output -----------------------------------------------------------------

def encode_gif(move: Move, name: str) -> list:
    """Frames to a GIF through ffmpeg, doubled with nearest-neighbour so it stays pixel art."""
    frames = [move.frame(i / FPS) for i in range(int(move.length * FPS))]
    temp = Path(tempfile.mkdtemp(prefix='tick-move-'))
    try:
        for i, image in enumerate(frames):
            pygame.image.save(image, str(temp / f'f{i:03d}.png'))
        out = HERE / f'{name}.gif'
        filters = ('scale=960:640:flags=neighbor,split[a][b];'
                   '[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=none')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS),
                        '-i', str(temp / 'f%03d.png'), '-vf', filters, '-loop', '0', str(out)],
                       check=True)
        print(f'{name}.gif  ({len(frames)} frames, {move.length:.1f}s)')
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return frames


def strip(frames, picks, captions, name, cols=3):
    """A contact strip of the key frames, for reviewing the move as stills."""
    pad, cap = 14, 20
    rows = (len(picks) + cols - 1) // cols
    board = pygame.Surface((cols * W + pad * (cols + 1), rows * (H + cap) + pad * (rows + 1) + 34))
    board.fill((22, 30, 38))
    art = font(18).render(name.replace('-', ' ').upper(), False, CREAM)
    board.blit(art, (pad, 10))
    for i, (index, caption) in enumerate(zip(picks, captions)):
        x = pad + (i % cols) * (W + pad)
        y = 34 + pad + (i // cols) * (H + cap + pad)
        board.blit(frames[min(index, len(frames) - 1)], (x, y))
        pygame.draw.rect(board, GRID, (x, y, W, H), 1)
        art = font(12).render(caption, False, MUTED)
        board.blit(art, (x, y + H + 4))
    pygame.image.save(board, str(HERE / f'{name}-frames.png'))
    print(f'{name}-frames.png')


SHOTS = [('01-insert-coin', insert_coin, 'CASHIER / waiting for money'),
         ('02-coin-drop', coin_drop, 'CASHIER / the deposit lands'),
         ('04-paying-out', paying, 'CASHIER / the payout, on Arc'),
         ('05-receipt', receipt, 'CASHIER / the ticket, then the board'),
         ('06-board-before', board_before, 'BOARD / your old rank, still scoring')]


def sheet(images):
    cols, pad, cap = 3, 18, 22
    rows = (len(images) + cols - 1) // cols
    board = pygame.Surface((cols * W + pad * (cols + 1), rows * (H + cap) + pad * (rows + 1) + 40))
    board.fill((22, 30, 38))
    art = font(20).render('TICK / CASHIER AND LEADERBOARD / PROPOSED', False, CREAM)
    board.blit(art, (pad, 14))
    for i, (image, caption) in enumerate(images):
        x = pad + (i % cols) * (W + pad)
        y = 46 + pad + (i // cols) * (H + cap + pad)
        board.blit(image, (x, y))
        pygame.draw.rect(board, GRID, (x, y, W, H), 1)
        art = font(13).render(caption, False, MUTED)
        board.blit(art, (x, y + H + 5))
    return board


def main() -> None:
    pygame.init()
    pygame.display.set_mode((W, H))
    made = []
    for name, draw, caption in SHOTS:
        image = draw()
        pygame.image.save(image, str(HERE / f'{name}.png'))
        made.append((image, caption))
        print(f'{name}.png')

    up = Move(CLIMB_BEFORE, CLIMB_AFTER)
    frames = encode_gif(up, '07-move-up')
    marks = [int(HOLD_S * FPS) - 1] + [int((HOLD_S + (i + .62) * STEP_S) * FPS) for i in range(3)]
    marks += [int((HOLD_S + 3 * STEP_S + .42) * FPS), len(frames) - 1]
    strip(frames, marks, ['#6, still scoring', 'passing #5', 'passing #4', 'passing #3',
                          'landed, confetti', 'on the podium'], '07-move-up')
    made.append((frames[marks[2]], 'BOARD / the climb, one place at a time'))
    made.append((frames[-1], 'BOARD / landed on the podium'))

    down = Move(SLIDE_BEFORE, SLIDE_AFTER)
    down_frames = encode_gif(down, '07-move-down')
    dmarks = [int(HOLD_S * FPS) - 1, int((HOLD_S + 1.62 * STEP_S) * FPS), len(down_frames) - 1]
    strip(down_frames, dmarks, ['#3, still scoring', 'slipping past #4', 'settled at #6'],
          '07-move-down', cols=3)
    made.append((down_frames[-1], 'BOARD / a bad run, no fanfare'))

    pygame.image.save(sheet(made), str(HERE / 'contact-sheet.png'))
    print('contact-sheet.png')
    pygame.quit()


if __name__ == '__main__':
    main()
