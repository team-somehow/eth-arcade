"""The money screens: INSERT COIN, the coin drop, the payout and the ticket.

Arcade rules. You put a coin in, the machine gives you credit, you play, and
when you walk away the machine pays you and hands you a ticket. Each of those
is its own face here, and only one of them is ever on screen — the old wallet
page did all three jobs at once and shouted SEND USDC at a player who was
trying to leave.

Which face is up comes from funding state that already exists on `ArcFunding`,
plus two timers: the coin drop falls back to the launcher if nobody presses
anything, and the ticket hands itself to the leaderboard. Nothing here touches
the escrow. Real funds only — demo money keeps its own +10/+25/+100 chooser
inside `BoxGame`, which is the whole of what paper money needs.

Drawn from the mockups in `design/insert-coin`.
"""
from __future__ import annotations

import math
import random

import pygame

from games.box import say, say_right, short_address
from games.box_scene import Rider, Skyline
from input import InputAction, event_position
from ui import NAVY, PANEL, GRID, CREAM, MUTED, YELLOW, MINT, RED, font, footer
from wallet import format_usdc

W, H = 480, 320
HORIZON, STREET_BOTTOM = 242, 274       # the game's own street, reused
LOGO_LOW = (196, 104, 28)               # the launcher logo's underside
PAPER = (238, 231, 208)
INK = (26, 34, 40)
PAPER_RULE = (176, 170, 150)
PAPER_FAINT = (122, 130, 134)
PAPER_QUIET = (92, 104, 110)
PAPER_GOOD = (22, 112, 84)
COIN_HI = (255, 224, 130)
COIN_LO = (196, 140, 28)
SHADOW = (6, 14, 20)
PLATE = (14, 28, 38)
BUBBLE = (18, 32, 42)

# How long each face holds before it moves on by itself.
ARRIVAL_S = 2.5         # the coin rain, and the best moment the machine owns
ARRIVAL_HOLD_S = 3.0    # then nothing pressed: the launcher, with PLAY up
CONFIRM_ARM_S = 0.5     # the beat before a second A actually sends the money
RECEIPT_S = 2.5         # then the leaderboard, by itself
# A payout takes about four seconds. Past this it is late — Arc unreachable, a
# retry in progress — and the player should not be held on a screen with no way
# off: the worker finishes the payout whatever is on the panel, and the launcher
# says so when it lands.
PAYING_HOLD_S = 8.0

_qr: dict[tuple[str, int], pygame.Surface] = {}


def qr_surface(text: str, size: int) -> pygame.Surface:
    """A QR of `text`, dark on white with its quiet zone. Built once per size."""
    key = (text, size)
    if key not in _qr:
        import qrcode            # real funds only; demo play does not need it
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
        _qr[key] = image
    return _qr[key]


def panel(s: pygame.Surface, rect: pygame.Rect, fill: tuple = PANEL,
          edge: tuple | None = GRID, width: int = 1, radius: int = 5) -> None:
    pygame.draw.rect(s, fill, rect, border_radius=radius)
    if edge:
        pygame.draw.rect(s, edge, rect, width, border_radius=radius)


def marquee(s: pygame.Surface, words: str, y: int, size: int = 40,
            color: tuple = YELLOW, bob: bool = True) -> None:
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


def coin(s: pygame.Surface, x: float, y: float, r: int = 9, face: str = '$') -> None:
    pygame.draw.circle(s, COIN_LO, (int(x), int(y)), r)
    pygame.draw.circle(s, YELLOW, (int(x), int(y)), r - 2)
    pygame.draw.circle(s, COIN_HI, (int(x - r // 3), int(y - r // 3)), max(1, r // 3))
    if r >= 8:
        art = font(r + 2).render(face, False, COIN_LO)
        s.blit(art, art.get_rect(center=(int(x), int(y))))


def bill(s: pygame.Surface, x: float, y: float, w: int = 54, h: int = 30,
         angle: float = 0.0, tint: tuple = MINT) -> None:
    """A flying USDC note: drawn flat, then turned."""
    note = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(note, PAPER, (0, 0, w, h), border_radius=3)
    pygame.draw.rect(note, tint, (0, 0, w, h), 2, border_radius=3)
    pygame.draw.circle(note, tint, (w // 2, h // 2), h // 4, 2)
    for i in (6, h - 8):
        pygame.draw.line(note, PAPER_RULE, (5, i), (w - 6, i), 1)
    art = font(9).render('USDC', False, INK)
    note.blit(art, art.get_rect(center=(w // 2, h // 2)))
    turned = pygame.transform.rotate(note, angle)
    s.blit(turned, turned.get_rect(center=(round(x), round(y))))


def pulse(s: pygame.Surface, x: int, y: int, clock: float, size: int = 7, count: int = 3,
          gap: int = 13, lit: tuple = RED, dim: tuple = (96, 44, 44)) -> None:
    """A row of square dots with one alight, walking: the machine is still waiting."""
    on = int(clock * 3) % count
    for i in range(count):
        pygame.draw.rect(s, lit if i == on else dim, (x + i * gap, y - size // 2, size, size))


class Rain:
    """Coins falling into the machine. Their own thing, because `Sparks` draws
    flat pips and the whole point of this beat is that they read as money."""

    def __init__(self, seed: int = 7) -> None:
        self.rng = random.Random(seed)
        self.items: list[list] = []

    def pour(self, count: int = 22) -> None:
        for _ in range(count):
            self.items.append([self.rng.randrange(14, W - 14), self.rng.uniform(-260, -10),
                               self.rng.uniform(150, 260), self.rng.choice((6, 7, 9, 11))])

    def update(self, dt: float) -> None:
        for c in self.items:
            c[1] += c[2] * dt
            c[2] += 260 * dt
        self.items = [c for c in self.items if c[1] < H + 20]

    def draw(self, s: pygame.Surface) -> None:
        for x, y, _, r in self.items:
            pygame.draw.line(s, (40, 62, 76), (x, y - r - 14), (x, y - r - 4), 2)
            coin(s, x, y, r)


class MoneyScreen:
    """One screen, four faces, driven by what the money is actually doing."""

    def __init__(self, game=None, skyline: Skyline | None = None) -> None:
        # The launcher already built this exact city (same size, seed and
        # street), and it is the biggest thing either screen owns — half a
        # megabyte of pre-rendered buildings — so the two share one.
        self.game = game
        self.face = 'waiting'
        self.t = 0.0                # seconds in the current face
        self.leave: str | None = None    # a face that timed out and wants to move on
        self.deposit: tuple[int, str] | None = None   # (amount, sender) on the coin drop
        self.credit = 0.0           # the balance the coin drop counts up to
        self.pour_at = 0.0          # seconds until the next handful of coins falls
        self.owed = 0               # what the payout is sending, kept once the balance is zeroed
        self.payee = ''             # who the payout is going to, kept once sessions close
        self.skyline = skyline or Skyline(W, HORIZON, STREET_BOTTOM, seed=3)
        self.rider = Rider()
        self.rain = Rain()
        self.veil = self._veil()

    @staticmethod
    def _veil() -> pygame.Surface:
        """Night over the city: light at the top so the moon keeps its look,
        heavier down the window band where the text has to stay readable."""
        veil = pygame.Surface((W, STREET_BOTTOM), pygame.SRCALPHA)
        for y in range(STREET_BOTTOM):
            share = min(1.0, y / HORIZON)
            veil.fill((*NAVY, int(10 + 58 * share)), (0, y, W, 1))
        return veil

    # ---- what the money is doing -------------------------------------------
    @property
    def funding(self):
        return getattr(getattr(getattr(self.game, 'model', None), 'wallet', None),
                       'funding', None)

    @property
    def balance(self) -> int:
        wallet = getattr(getattr(self.game, 'model', None), 'wallet', None)
        return getattr(wallet, 'balance', 0)

    def who(self, address: str) -> str:
        teller = getattr(self.game, 'who', None)
        return teller(address) if teller else short_address(address)

    def show(self, face: str) -> None:
        self.face, self.t, self.leave = face, 0.0, None

    def open(self) -> None:
        """Pick the face from the state of the money, and start there."""
        # Both seams are cleared first. A deposit that landed while the player
        # was somewhere else was announced on the launcher and is old news, and
        # a ticket from a run already paid out must not stand in for this one.
        if self.game is not None:
            self.game.coin_in = None
            self.game.ticket = None
        funding = self.funding
        # `is not None`, not truthiness: a payout part-way through the sessions
        # it is closing holds a pending balance of zero for a moment, and that
        # is still a payout in flight, not an empty machine.
        pending = getattr(funding, 'pending_cashout', None)
        if funding is None:
            self.show('waiting')
        elif getattr(self.game, 'cashing', False) or pending is not None:
            self.owed = pending or self.owed or self.balance
            self.payee = self.payee or getattr(funding, 'player', '')
            self.show('paying')
        elif getattr(funding, 'in_session', False):
            self.owed, self.payee = 0, ''       # nothing is being sent
            self.show('confirm')
        else:
            self.owed, self.payee = 0, ''
            self.show('waiting')

    def close(self) -> None:
        self.rain.items.clear()

    # ---- the beats ---------------------------------------------------------
    def update(self, dt: float) -> None:
        self.t += dt
        self.rider.update(dt, 0.0, False)
        self.rain.update(dt)
        getattr(self, f'_{self.face}')(dt)

    def _waiting(self, dt: float) -> None:
        coin_in = getattr(self.game, 'coin_in', None)
        if coin_in is None:
            return
        self.game.coin_in = None
        self.deposit, self.credit, self.pour_at = coin_in, 0.0, 0.0
        self.show('arrival')
        self.rain.pour()

    def _arrival(self, dt: float) -> None:
        # The credit meter runs up over the rain, then the screen waits to be told.
        self.credit += (self.balance - self.credit) * (1 - math.exp(-dt * 5))
        if self.t < ARRIVAL_S:
            self.pour_at -= dt
            if self.pour_at <= 0:
                self.pour_at = .3
                self.rain.pour(6)
        elif self.t > ARRIVAL_S + ARRIVAL_HOLD_S:
            self.leave = 'funded'

    def _confirm(self, dt: float) -> None:
        if not self._in_session:
            self.show('waiting')

    def _paying(self, dt: float) -> None:
        if getattr(self.game, 'ticket', None) is not None:
            self.show('receipt')

    def _receipt(self, dt: float) -> None:
        if self.t > RECEIPT_S:
            self.leave = 'board'

    @property
    def _in_session(self) -> bool:
        return bool(getattr(self.funding, 'in_session', False))

    @property
    def stuck(self) -> bool:
        """The payout is taking longer than a payout should, so offer the way out."""
        return self.face == 'paying' and self.t > PAYING_HOLD_S

    @property
    def armed(self) -> bool:
        """The confirm card ignores A for a beat, so the press that opened it
        cannot also send the money."""
        return self.t >= CONFIRM_ARM_S

    def start_cash_out(self) -> None:
        if not self._in_session:
            return
        self.owed = self.balance
        # Both of these are about to be gone: the balance is zeroed the moment
        # the cash-out is queued, and `player` empties as the sessions close.
        self.payee = getattr(self.funding, 'player', '')
        self.game.ticket = None     # this run's ticket is what the payout prints
        self.game.request_cash_out()
        self.show('paying')

    def steps(self) -> list[tuple[str, str]]:
        """(state, text) for the payout, where state is done / doing / waiting."""
        game, funding = self.game, self.funding
        live = not getattr(game, 'cashing', False)
        closed = not getattr(funding, 'sessions', ())
        sent = getattr(game, 'ticket', None) is not None
        return [('done' if live else 'doing', 'FINISHING THE LIVE BOX'),
                ('done' if closed else ('doing' if live else 'waiting'),
                 'CLOSING SESSION ON ARC'),
                ('done' if sent else ('doing' if closed else 'waiting'),
                 f'SENDING {format_usdc(self.owed)} USDC')]

    # ---- input -------------------------------------------------------------
    def handle_action(self, action: InputAction) -> str | None:
        if action == InputAction.QUIT:
            return 'quit'
        if self.face == 'paying':
            # Nothing to press while it sends — pressing cannot make Arc faster.
            # If it is running late, leaving is allowed: the worker carries on.
            return 'home' if self.stuck and action == InputAction.B else None
        if action == InputAction.B:
            return 'home'
        if action != InputAction.A:
            return None
        if self.face == 'arrival':
            return 'game'                   # PLAY NOW: no detour through home
        if self.face == 'receipt':
            return 'board'
        if self.face == 'confirm' and self.armed:
            self.start_cash_out()
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if pos[1] >= STREET_BOTTOM:
            return self.handle_action(InputAction.A if pos[0] >= 240 else InputAction.B)
        return None

    # ---- drawing -----------------------------------------------------------
    def draw(self, s: pygame.Surface) -> None:
        s.fill(NAVY)
        getattr(self, f'draw_{self.face}')(s)

    def city(self, s: pygame.Surface) -> None:
        self.skyline.draw(s, 0, 3.0)     # a clock the lit windows have caught up with
        s.blit(self.veil, (0, 0))

    def head(self, s: pygame.Surface, right: str = '', color: tuple = MUTED) -> None:
        """The launcher's own mark, so this reads as the same machine rather
        than a department you have walked into."""
        say(s, 'ETH', 10, 5, 20, CREAM)
        say(s, 'ARCADE', 54, 11, 12, MUTED)
        if right:
            say_right(s, right, 470, 9, 13, color)
        pygame.draw.line(s, GRID, (0, 30), (W, 30))

    # -- INSERT COIN
    def draw_waiting(self, s: pygame.Surface) -> None:
        funding = self.funding
        net = getattr(getattr(funding, 'net', None), 'name', 'ARC')
        chain = net.split()[0]          # the header carries the full name already
        error = getattr(funding, 'error', '')
        self.city(s)
        self.head(s, f'{chain} UNREACHABLE' if error else net, RED if error else MUTED)
        marquee(s, 'INSERT COIN', 26, 32)

        plate = pygame.Rect(16, 72, 136, 136)
        panel(s, plate, fill=PLATE, edge=None, radius=6)     # a plate, not a frame
        text = getattr(funding, 'qr_text', '')
        if text:
            code = qr_surface(text, 116)
            s.blit(code, code.get_rect(center=plate.center))
        say(s, 'SCAN TO INSERT', plate.centerx, plate.bottom + 5, 13, YELLOW, True)

        x = 166
        say(s, f'SEND USDC ON {chain}', x, 80, 20, CREAM)
        address = getattr(funding, 'address', '')
        box = pygame.Rect(x - 6, 112, 292, 44)
        panel(s, box, fill=(16, 30, 40))
        say(s, address[:21], x + 2, 117, 13, MUTED)
        say(s, address[21:], x + 2, 135, 13, MUTED)
        pulse(s, x + 6, 182, self.t, 4, 3, 13)
        say(s, 'RETRYING...' if error else 'WAITING FOR COINS', x + 42, 174, 15,
            RED if error else CREAM)

        self.draw_rider(s)
        footer(s, '< BACK', '')

    def draw_rider(self, s: pygame.Surface, x: int = 300, ground: int = 272,
                   scale: float = 1.4) -> None:
        """The kid from the game is the waiting sign: parked on the street,
        holding his balance, thinking about a coin nobody has sent yet."""
        pad = pygame.Surface((120, 120), pygame.SRCALPHA)
        self.rider.draw(pad, 60, 110, 0.0)
        big = pygame.transform.scale(pad, (int(120 * scale), int(120 * scale)))
        s.blit(big, (x - 60 * scale, ground - 110 * scale))

        bubble = pygame.Rect(x + 22, ground - 64, 74, 30)
        pygame.draw.polygon(s, BUBBLE, [(bubble.x, bubble.bottom - 12),
                                        (bubble.x - 10, bubble.bottom + 2),
                                        (bubble.x + 6, bubble.bottom - 1)])
        panel(s, bubble, fill=BUBBLE, edge=MUTED, width=1, radius=6)
        coin(s, bubble.x + 18, bubble.centery, 9)
        pulse(s, bubble.x + 33, bubble.centery, self.t, 5, 3, 10, YELLOW, (74, 70, 44))

    # -- the coin drop
    def draw_arrival(self, s: pygame.Surface) -> None:
        amount, sender = self.deposit or (0, '')
        self.rain.draw(s)
        plate = pygame.Rect(96, 66, 288, 68)
        panel(s, plate, fill=(16, 44, 40), edge=MINT, width=2, radius=6)
        marquee(s, f'+{format_usdc(amount)}', plate.y + 8, 42, MINT, bob=False)
        say(s, f'FROM {self.who(sender)}'[:32], 240, 142, 15, CREAM, True)
        say(s, 'CREDIT', 240, 172, 13, MUTED, True)
        marquee(s, f'{format_usdc(round(self.credit))} USDC', 190, 30, CREAM, bob=False)
        say(s, 'COINS ARE IN. GO.', 240, 246, 15, YELLOW, True)
        footer(s, 'HOME', 'PLAY NOW >')

    # -- the beat before the money leaves
    def draw_confirm(self, s: pygame.Surface) -> None:
        self.city(s)
        self.head(s, self.who(getattr(self.funding, 'player', '')))
        marquee(s, 'CASH OUT', 34, 34)

        card = pygame.Rect(84, 96, 312, 108)
        panel(s, card, fill=(16, 44, 40), edge=MINT, width=2, radius=6)
        say(s, 'SENDING YOU', card.centerx, card.y + 10, 13, MUTED, True)
        marquee(s, f'{format_usdc(self.balance)} USDC', card.y + 30, 34, MINT, bob=False)
        say(s, 'THIS ENDS THE SESSION ON ARC', card.centerx, card.bottom - 22, 13, CREAM, True)
        ready = self.armed
        say(s, 'PRESS AGAIN TO SEND' if ready else 'HOLD ON...', 240, 218, 15,
            YELLOW if ready else MUTED, True)
        footer(s, '< NOT YET', 'YES, CASH OUT >' if ready else '')

    # -- the payout
    def draw_paying(self, s: pygame.Surface) -> None:
        error = getattr(self.funding, 'error', '')
        marquee(s, 'CASHING OUT', 10, 32)
        for i, (state, text) in enumerate(self.steps()):
            y = 86 + i * 34
            doing = state == 'doing'
            color = MINT if state == 'done' else (
                (RED if error else YELLOW) if doing else MUTED)
            if state == 'done':
                pygame.draw.lines(s, MINT, False, [(20, y + 10), (26, y + 16), (38, y + 2)], 3)
            elif doing:
                sweep = self.t * 5
                pygame.draw.arc(s, color, (18, y - 1, 20, 20), sweep, sweep + 3.8, 3)
            else:
                pygame.draw.circle(s, MUTED, (28, y + 9), 4, 1)
            say(s, text, 48, y, 15, color)
            if doing and error:     # right-aligned, or it reads as part of the step
                say_right(s, 'RETRYING...', 470, y, 15, RED)
        if self.stuck:      # two short lines: the cash tray owns the right half
            say(s, 'TAKING LONGER THAN USUAL.', 48, 212, 11, MUTED)
            say(s, 'IT KEEPS SENDING IF YOU LEAVE.', 48, 228, 11, MUTED)
        say(s, f'TO {self.who(self.payee)}'[:34], 48, 190, 13, MUTED)

        tray = pygame.Rect(286, 208, 186, 54)
        panel(s, tray, fill=BUBBLE, edge=MINT, width=2, radius=5)
        mouth = pygame.Rect(tray.x + 16, tray.y + 10, tray.w - 32, 12)
        pygame.draw.rect(s, SHADOW, mouth, border_radius=4)
        pygame.draw.rect(s, MINT, mouth, 1, border_radius=4)
        say(s, 'CASH TRAY', tray.centerx, tray.bottom - 20, 11, MUTED, True)
        # Notes fly out of the tray and off the top while Arc confirms; they
        # stall when it cannot be reached, because the payout has stalled too.
        for i, (x, span, angle) in enumerate(((362, 88, 16), (398, 130, -14),
                                              (330, 134, 8), (434, 90, 30))):
            drift = 0.0 if error else (self.t * 46 + i * 31) % span
            bill(s, x, mouth.centery - drift, angle=angle)
        footer(s, '< LEAVE IT RUNNING' if self.stuck else '', '')

    # -- the ticket
    def draw_receipt(self, s: pygame.Surface) -> None:
        ticket = getattr(self.game, 'ticket', None)
        say(s, 'ETH ARCADE', 240, 8, 15, MUTED, True)
        card = pygame.Rect(56, 30, 368, 214)
        pygame.draw.rect(s, PAPER, card, border_radius=3)
        for x in range(card.x, card.right - 6, 12):          # torn bottom edge
            pygame.draw.polygon(s, NAVY, [(x, card.bottom - 8), (x + 6, card.bottom + 1),
                                          (x + 12, card.bottom - 8), (x + 12, card.bottom + 2),
                                          (x, card.bottom + 2)])

        def ink(words: str, y: int, size: int = 15, color: tuple = INK) -> None:
            art = font(size).render(words, False, color)
            s.blit(art, art.get_rect(midtop=(card.centerx, y)))

        paid = ticket.paid if ticket else 0
        ink('PAID OUT', 42, 17, PAPER_QUIET)
        ink(f'+{format_usdc(paid)} USDC', 60, 36, PAPER_GOOD)
        ink(f'to {self.who(ticket.player if ticket else "")}'[:34], 104, 15)
        pygame.draw.line(s, PAPER_RULE, (card.x + 18, 130), (card.right - 18, 130))
        pnl = paid - (ticket.paid_in if ticket else 0)
        cells = (('IN', format_usdc(ticket.paid_in if ticket else 0)),
                 ('OUT', format_usdc(paid)),
                 ('P&L', f'{"+" if pnl >= 0 else "-"}{format_usdc(abs(pnl))}'))
        for i, (title, value) in enumerate(cells):
            cx = card.x + 62 + i * 122
            art = font(11).render(title, False, PAPER_FAINT)
            s.blit(art, art.get_rect(midtop=(cx, 140)))
            good = i == 2 and pnl >= 0
            art = font(19).render(value, False, PAPER_GOOD if good else INK)
            s.blit(art, art.get_rect(midtop=(cx, 156)))
        if ticket:
            ink(f'{ticket.boxes} BOXES  /  {ticket.hits} HITS  /  '
                f'BEST WIN +{format_usdc(ticket.best)}', 186, 13, PAPER_QUIET)
            tx = ticket.tx
            ink(f'TX {tx[:6]}...{tx[-4:]}' if tx else 'NO TX', 206, 11, PAPER_FAINT)
        march = '>' * (1 + int(self.t * 4) % 3)
        say(s, f'YOUR RANK IS UPDATING {march}', 240, 252, 13, YELLOW, True)
        footer(s, 'HOME', 'SEE YOUR RANK >')


def handle_money_events(money: MoneyScreen, events: list,
                        actions: list[InputAction]) -> str | None:
    if money.leave:
        # A face that ran out of patience outranks the frame's presses; the
        # press that was aimed at it has nowhere to land any more.
        target, money.leave = money.leave, None
        return target
    for event in events:
        pos = event_position(event)
        if pos is not None:
            target = money.handle_touch(pos)
            if target:
                return target
    for action in actions:
        target = money.handle_action(action)
        if target:
            return target
    return None
