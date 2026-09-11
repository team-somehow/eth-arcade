"""BOX RUN: crank the box, buy the next window. Renderer, sound and input."""
from __future__ import annotations
from collections import deque
import math
import os
import time
from typing import Callable

import pygame

from games.box_model import BoxModel, Result
from games.box_scene import Floaters, Rider, Skyline, Sparks, mix
from input import InputAction, event_position
from markets.feed import open_feed
from ui import NAVY, GRID, CREAM, MUTED, YELLOW, MINT, RED, Sounds, font, label, footer
from wallet import LOAD_CHOICES, MICRO, DemoFunding, Wallet, format_usdc, places_for

# The world. Time is one horizontal scale across the whole screen: the rider
# sits at RIDER_X at "now", history is to the left, and every bell is a post
# ahead that slides toward him at PX_PER_S. There are no columns — a box is
# drawn at the moment it settles, so it arrives under the wheel on its bell.
PLAY = pygame.Rect(0, 34, 480, 208)
STREET_BOTTOM = 274
MID_Y = PLAY.centery
HALF_PX = 92
# Boxes are drawn inside this band, which has to cover the whole price range a
# box can legally reach — squeeze it and a box at full crank gets clipped and
# flagged off-scale when it is really on screen.
BAND_TOP = PLAY.top + 4
BAND_BOTTOM = PLAY.bottom - 4
RIDER_X = 120
# Slow enough that the next window's bell, twenty seconds out, is on screen.
PX_PER_S = 16.0
BOX_W = 44
OPEN_LINE = (74, 96, 103)
POST = (40, 58, 76)
POST_NOW = (88, 110, 128)
SHADE = (80, 170, 210, 30)   # under the price line
GLOW = (44, 80, 98)


FUNDING = ('demo', 'arc-testnet')


def build_wallet() -> Wallet:
    """TICK_FUNDING picks the money: demo (paper) or arc-testnet (real testnet USDC)."""
    kind = os.environ.get('TICK_FUNDING', 'demo')
    if kind not in FUNDING:
        raise ValueError(f"TICK_FUNDING must be one of {', '.join(FUNDING)}")
    if kind == 'arc-testnet':
        from arc import ArcFunding     # needs eth-account; demo play does not
        funding = ArcFunding(kind)
        return Wallet(funding.balance, funding)
    return Wallet(100 * MICRO, DemoFunding())


def short_address(address: str) -> str:
    return f'{address[:6]}..{address[-4:]}' if address else ''


def dashed_rect(s: pygame.Surface, rect: pygame.Rect, color: tuple, dash: int = 6) -> None:
    for x in range(rect.left, rect.right, dash * 2):
        end = min(x + dash, rect.right)
        pygame.draw.line(s, color, (x, rect.top), (end, rect.top), 2)
        pygame.draw.line(s, color, (x, rect.bottom - 1), (end, rect.bottom - 1), 2)
    for y in range(rect.top, rect.bottom, dash * 2):
        end = min(y + dash, rect.bottom)
        pygame.draw.line(s, color, (rect.left, y), (rect.left, end), 2)
        pygame.draw.line(s, color, (rect.right - 1, y), (rect.right - 1, end), 2)


def say(s: pygame.Surface, words: str, x: float, y: float, size: int = 16,
        color: tuple = CREAM, center: bool = False) -> None:
    """A label with a drop shadow, so it reads over the city."""
    label(s, words, round(x) + 1, round(y) + 1, size, (0, 0, 0), center)
    label(s, words, round(x), round(y), size, color, center)


def say_right(s: pygame.Surface, words: str, right: int, y: int, size: int, color: tuple) -> None:
    say(s, words, right - font(size).size(words)[0], y, size, color)


def ease_out(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


class BoxGame:
    def __init__(self, seed: int | None = None, sound: bool = True,
                 source: str | None = None, wallet: Wallet | None = None,
                 clock: Callable[[], float] | None = None) -> None:
        self.feed = open_feed(source or os.environ.get('TICK_MARKET_SOURCE', 'sim'), seed)
        self.model = BoxModel(wallet or build_wallet())
        self.sounds = Sounds() if sound else None
        # Wall-clock monotonic in play: live ticks are stamped on the same
        # clock, so the window bell and staleness stay honest. Tests inject.
        self._now = clock or time.monotonic
        self.clock = self._now()
        self.held: dict[int, float] = {}
        self.wallet_open = False
        self.amount_index = 1
        self.message = ''
        self.message_until = 0.0
        self.last_sound_at = 0.0
        self.flash_until = 0.0
        self.last_bell: tuple | None = None
        self.was_inside: bool | None = None
        self.was_fresh = True
        # The scene. Everything on screen eases toward where the model says it
        # is, in price terms, so a tick or a detent is a glide and not a jump.
        self.skyline = Skyline(PLAY.width, PLAY.bottom, STREET_BOTTOM)
        self.rider = Rider()
        self.sparks = Sparks()
        self.floaters = Floaters()
        self.shade = pygame.Surface(PLAY.size, pygame.SRCALPHA)
        self.anchor = 0.0          # eased window open: the camera
        self.ride_price = 0.0      # eased spot: the wheel
        self.aim_price = 0.0       # eased cursor: the dashed box
        self.trail: deque[tuple[float, float]] = deque()
        self.settled: deque[tuple[Result, float]] = deque(maxlen=4)
        self.ghost: tuple[float, float, float, float] | None = None
        self.aim_in_at = -99.0
        self.pop_at = -99.0
        self.shake_at = -99.0
        self.streak = 0            # hits in a row; three sets the rider on fire
        # Real funds only.
        self.cashing = False       # cash-out asked for; waiting for the live box to land
        self.money_note: tuple[str, float] | None = None   # shown on the launcher too
        self.qr: tuple[str, pygame.Surface] | None = None

    def enter(self) -> None:
        self.held.clear()
        self.wallet_open = False

    def close(self) -> None:
        self.music('off')
        self.feed.close()
        stop = getattr(self.model.wallet.funding, 'stop', None)
        if stop is not None:
            stop()

    def play(self, name: str) -> None:
        if self.sounds:
            self.sounds.play(name)

    def music(self, mode: str) -> None:
        if self.sounds:
            self.sounds.music(mode)

    def ambient(self) -> None:
        """Bed for the launcher, so the machine hums before you play."""
        self.music('idle')

    def bed_for_now(self) -> str:
        """Calm with nothing down, driving with money live, tense at the bell."""
        m = self.model
        if m.live is not None and m.live.stake:
            return 'final' if m.remaining(self.clock) <= 3 else 'live'
        return 'live' if m.pending is not None else 'idle'

    def note(self, text: str, seconds: float = 2.0) -> None:
        self.message, self.message_until = text, self.clock + seconds

    def stake_text(self, micro: int | None = None) -> str:
        """A stake (one press by default) with exactly the decimals the stake has."""
        stake = self.model.STAKE
        return format_usdc(stake if micro is None else micro, places_for(stake))

    # ---- real funds --------------------------------------------------------
    @property
    def onchain(self) -> bool:
        return bool(getattr(self.model.wallet.funding, 'onchain', False))

    def announce(self, text: str, seconds: float) -> None:
        """A money message: on the status line here, and on the launcher."""
        self.note(text, seconds)
        self.money_note = (text, self.clock + seconds)

    def banner(self) -> tuple[str, tuple] | None:
        if self.money_note is not None and self.clock < self.money_note[1]:
            return self.money_note[0], MINT
        return None

    def request_cash_out(self) -> None:
        """A on the wallet screen: refund the box bought for next, let the live
        one land, then pay the whole balance back to the player."""
        m = self.model
        funding = m.wallet.funding
        if self.cashing or not getattr(funding, 'in_session', False):
            return
        m.cancel_pending()
        self.play('nav')
        if m.live is not None and m.live.stake:
            self.cashing = True
            self.note('FINISHING THE LIVE BOX...', 10)
        else:
            funding.cash_out(m.wallet)

    def sync_funding(self) -> None:
        """Take the chain worker's news, and pay out once no box is in play."""
        m = self.model
        funding = m.wallet.funding
        if not hasattr(funding, 'sync'):
            return
        for event in funding.sync(m.wallet):
            kind = event[0]
            if kind == 'opened':
                self.announce(f'+{format_usdc(event[1])} USDC FROM {short_address(event[2])}', 6)
                self.play('coin')
            elif kind == 'cashed_out' and event[1]:
                paid = sum(payout for payout, _, _ in event[1])
                self.announce(f'SENT {format_usdc(paid)} TO {short_address(event[1][-1][1])}', 8)
                self.play('coin')
            elif kind == 'refunded':
                self.announce(f'SENT BACK {format_usdc(event[1])} / {event[3]}', 6)
            elif kind == 'ended':
                self.announce('SESSION ENDED ON CHAIN', 4)
        if self.cashing and (m.live is None or not m.live.stake):
            self.cashing = False
            funding.cash_out(m.wallet)

    def open_wallet(self) -> None:
        self.wallet_open = True
        self.held.clear()

    def load_selected(self) -> None:
        amount = LOAD_CHOICES[self.amount_index]
        deposit = self.model.wallet.load(amount)
        self.wallet_open = False
        if deposit.status == 'confirmed':
            self.note(f'+{amount} {self.model.wallet.funding.name} USDC IN')
            self.play('coin')
        else:
            self.note(f'DEPOSIT {deposit.status.upper()} / NOT CREDITED', 3)

    # ---- input -----------------------------------------------------------
    def crank(self, steps: int) -> None:
        m = self.model
        if m.locked:
            # The bet is placed: the dial does nothing until the bell.
            if self.clock - self.last_sound_at > .25:
                self.play('warn')
                self.last_sound_at = self.clock
            self.shake_at = self.clock
            self.note(f'BOX LOCKED / A ADDS {self.stake_text()}', 1.5)
            return
        above = m.aim - m.price
        moved = m.crank(steps)
        if moved and above * (m.aim - m.price) < 0:
            self.play('crossline')       # the box just passed over spot
        if moved and self.clock - self.last_sound_at > .04:
            # Pitch rises as the box moves out to the risky end of its reach.
            if self.sounds is not None and m.reach:
                self.play(self.sounds.detent(abs(m.aim - m.window_open) / m.reach))
            self.last_sound_at = self.clock

    def buy(self) -> None:
        m = self.model
        if self.cashing:
            self.note('CASHING OUT / NO NEW BOXES')
            return
        if not m.can_buy():
            self.open_wallet()
            return
        if m.buy(self.clock):
            # Each stacked press on the same box answers a note higher.
            presses = min(3, max(1, round(m.pending.stake / m.STAKE)))
            self.play(f'buy{presses}')
            self.message = ''
            # The dashed box turns solid where it stands, with a pop.
            self.aim_price = m.pending.level
            self.pop_at = self.clock
            x = self.x_at(m.window_end + m.WINDOW_S)
            self.sparks.burst(x, self.y_of(m.pending.level), 10, (CREAM, YELLOW),
                              110, .45, 3, gravity=0, drift=-PX_PER_S)
        elif m.refused == 'cap':
            self.note('MAX WIN REACHED / CASH OUT', 3)
        elif not m.fresh(self.clock):
            self.note('NO LIVE PRICE / NOT PLACED')
        elif m.settling:
            self.note('SETTLING LAST WINDOW')
        elif m.quiet(self.clock):
            self.note('MARKET QUIET / NO BETS')
        elif not m.measured:
            self.note('READING THE MARKET...')
        elif m.quote(m.aim if m.pending is None else m.pending.level,
                     self.clock) < m.MIN_MULTIPLE:
            self.note(f'UNDER {m.MIN_MULTIPLE:.2f}x / NOT SOLD')

    def handle_action(self, action: InputAction) -> str | None:
        if action == InputAction.QUIT:
            return 'quit'
        if self.wallet_open:
            if action in (InputAction.UP, InputAction.DOWN) and not self.onchain:
                step = 1 if action == InputAction.UP else -1
                self.amount_index = (self.amount_index + step) % len(LOAD_CHOICES)
                self.play('nav')
            elif action == InputAction.A:
                if self.onchain:
                    self.request_cash_out()
                else:
                    self.load_selected()
            elif action == InputAction.B:
                self.wallet_open = False
            return None
        if action in (InputAction.UP, InputAction.DOWN):
            self.crank(1 if action == InputAction.UP else -1)
        elif action == InputAction.A:
            self.buy()
        elif action == InputAction.B:
            self.held.clear()
            return 'home'
        return None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        x, y = pos
        if y >= STREET_BOTTOM:
            return self.handle_action(InputAction.B if x < 240 else InputAction.A)
        if self.wallet_open:
            return self.handle_action(InputAction.UP if x >= 240 else InputAction.DOWN)
        if PLAY.top <= y < PLAY.bottom:
            # Tap above the aim box to raise it, below to lower it.
            aim_y = self.y_of(self.aim_price) if self.model.started else MID_Y
            return self.handle_action(InputAction.UP if y < aim_y else InputAction.DOWN)
        return None

    def update(self, dt: float) -> None:
        self.clock = self._now()
        m = self.model
        rounds_before = m.rounds
        for key in list(self.held):
            self.held[key] -= dt
            if self.held[key] <= 0:
                self.crank(1 if key in (pygame.K_UP, pygame.K_w) else -1)
                if key in self.held:
                    self.held[key] = .05
        windows_before = m.windows
        for tick in self.feed.poll(dt, self.clock):
            m.on_tick(tick, self.clock)
        m.update(self.clock)
        self.sync_funding()
        if m.rounds != rounds_before and m.last is not None:
            if m.last.voided:
                self.play('void')
            elif m.last.hit:
                self.play('jackpot' if m.last.multiple >= 15
                          else ('win_big' if m.last.multiple >= 5 else 'win_small'))
            else:
                self.play('miss')
            self.flash_until = self.clock + 1.6
            self.on_result(m.last, m.window_end - m.WINDOW_S)
        elif m.windows != windows_before:
            # The empty-window heartbeat; a result speaks for the bell instead.
            self.play('bell')
        if m.windows != windows_before:
            if m.live is None:
                # Nobody bought the box on its way in: it fades out on its post
                # while a fresh one slides in from the right for the next bell.
                self.ghost = (self.aim_price, m.half, m.window_end, self.clock)
            self.aim_in_at = self.clock

        # Crossing into or out of a live box is the whole tension of a window,
        # so it gets a sound of its own in each direction.
        inside = m.inside
        if inside is not None and self.was_inside is not None and inside != self.was_inside:
            self.play('hot' if inside else 'cold')
        self.was_inside = inside

        # Last seconds: ticks pitched by whether the money is currently winning,
        # and doubling in rate inside the final two so the bell rushes at you.
        left = m.remaining(self.clock)
        slot = ('s', int(left)) if left > 2 else ('h', int(left * 2))
        if inside is not None and 0 < left <= 3 and slot != self.last_bell:
            self.play('tick_in' if inside else 'tick_out')
        self.last_bell = slot

        fresh = m.fresh(self.clock)
        if self.was_fresh and not fresh:
            self.play('stale')
        self.was_fresh = fresh
        self.music('idle' if self.wallet_open else self.bed_for_now())
        self.animate(dt)

    def watch(self, dt: float) -> None:
        """Keep reading prices while the launcher is up, silently.

        The feed opens at boot, so by the time you press play the market has
        already been read and the window clock is already running — rather
        than starting both from nothing the moment you walk in.
        """
        self.clock = self._now()
        for tick in self.feed.poll(dt, self.clock):
            self.model.on_tick(tick, self.clock)
        self.model.update(self.clock)
        self.sync_funding()

    def on_result(self, result: Result, bell: float) -> None:
        """A box just reached the wheel: make it land."""
        self.settled.append((result, bell))
        y = self.y_of((result.low + result.high) / 2)
        if result.voided:
            self.floaters.add('VOID', RIDER_X + 64, y - 30, MUTED)
            return
        if result.hit:
            self.streak += 1
            self.sparks.burst(RIDER_X, y, 20, (YELLOW, YELLOW, CREAM), 180, 1.1, 5,
                              square=True, drift=-PX_PER_S)
            self.floaters.add(f'+{format_usdc(result.payout)}', RIDER_X + 64, y - 36, MINT, 20)
            if self.streak >= 3:
                # Low over the city, clear of the rider, the boxes and their tags.
                self.floaters.add('HAT TRICK!' if self.streak == 3 else f'{self.streak} IN A ROW!',
                                  300, BAND_BOTTOM - 30, YELLOW, 28, life=2.2, rise=10)
                bx, by = self.rider.back(RIDER_X, self.rider_y())
                self.sparks.burst(bx, by, 26, (YELLOW, (255, 138, 40), RED), 150, .6, 5,
                                  gravity=-60)
                self.play('hattrick')
            self.rider.react('flip' if result.multiple >= 5
                             else ('cheer' if self.streak == 3 else 'hop'))
            return
        if self.streak >= 3:
            bx, by = self.rider.back(RIDER_X, self.rider_y())
            self.sparks.burst(bx, by, 16, ((96, 104, 112), (70, 76, 84)), 60, 1.0, 6,
                              gravity=-50)
            self.play('fizzle')
        self.streak = 0
        self.sparks.burst(RIDER_X, y, 14, (RED, (140, 60, 56)), 150, .8, 4, square=True,
                          drift=-PX_PER_S)
        self.floaters.add('MISS', RIDER_X + 64, y - 34, RED, 20)
        self.rider.react('wobble')

    def animate(self, dt: float) -> None:
        """Ease the camera, the wheel and the cursor; run the rider and sparks."""
        m = self.model

        def ease(rate: float) -> float:
            return 1 - math.exp(-rate * dt)

        if m.started:
            if not self.anchor:
                self.anchor, self.ride_price, self.aim_price = m.window_open, m.price, m.aim
            # The camera still anchors on the window's open, as it always has —
            # it just glides there at the bell instead of snapping.
            self.anchor += (m.window_open - self.anchor) * ease(5)
            self.ride_price += (m.price - self.ride_price) * ease(12)
            self.aim_price += (m.aim - self.aim_price) * ease(24)
            self.trail.append((self.clock, self.ride_price))
            while len(self.trail) > 2 and self.clock - self.trail[0][0] > .6:
                self.trail.popleft()
        slope = 0.0
        if len(self.trail) > 1 and m.view_half > 0:
            t0, p0 = self.trail[0]
            rise = (self.ride_price - p0) / m.view_half * HALF_PX
            slope = math.degrees(math.atan2(rise, max(4.0, (self.clock - t0) * PX_PER_S)))
        self.rider.update(dt, slope, self.streak >= 3)
        if self.streak >= 3:
            self.sparks.flame(*self.rider.back(RIDER_X, self.rider_y()), -PX_PER_S)
        self.sparks.update(dt)
        self.floaters.update(dt)

    # ---- drawing ---------------------------------------------------------
    def y_of(self, price: float) -> float:
        """Price to screen, anchored on the window's opening price.

        Anchoring on spot instead would re-centre the chart on every tick and
        pin the latest point to the middle, which makes movement invisible.
        """
        m = self.model
        if m.view_half <= 0:
            return MID_Y
        return MID_Y - (price - (self.anchor or m.window_open)) / m.view_half * HALF_PX

    def x_at(self, t: float) -> float:
        """Time to screen: the rider is now, a bell is a post ahead of him."""
        return RIDER_X + (t - self.clock) * PX_PER_S

    def rider_y(self) -> float:
        if not self.model.started:
            return PLAY.bottom - 1          # parked on the street until a price arrives
        return max(BAND_TOP + 2, min(BAND_BOTTOM, self.y_of(self.ride_price)))

    def draw(self, s: pygame.Surface) -> None:
        m = self.model
        if self.wallet_open:
            s.fill(NAVY)
            label(s, 'BOX RUN', 14, 5, 20, CREAM)
            label(s, f'{format_usdc(m.wallet.balance)} {m.wallet.funding.name}', 336, 9, 16, MINT)
            pygame.draw.line(s, GRID, (14, 32), (466, 32))
            self.draw_wallet(s)
            return
        self.skyline.draw(s, self.clock * PX_PER_S, self.clock)
        if not m.started:
            self.rider.draw(s, RIDER_X, self.rider_y(), self.spin())
            say(s, 'WAITING FOR THE', 280, 96, 22, YELLOW, True)
            say(s, 'FIRST PRICE...', 280, 128, 22, YELLOW, True)
            footer(s, '< HOME', f'BUY {self.stake_text()} >')
            return
        self.draw_world(s)
        self.draw_hud(s)
        self.draw_status(s)
        footer(s, '< HOME', f'BUY {self.stake_text()} >' if m.can_buy()
               else ('ADD USDC >' if self.onchain else 'LOAD >'))

    def spin(self) -> float:
        return self.clock * PX_PER_S / Rider.WHEEL

    def draw_hud(self, s: pygame.Surface) -> None:
        m = self.model
        asset = self.feed.asset
        price = f'${asset.format(m.price)}'
        say(s, price, 10, 6, 20, CREAM)
        say(s, asset.format(m.move, sign=True), 22 + font(20).size(price)[0], 10, 16, MINT if m.move >= 0 else RED)
        say_right(s, f'{format_usdc(m.wallet.balance)} {m.wallet.funding.name}', 470, 10, 15, MINT)

    def draw_world(self, s: pygame.Surface) -> None:
        m = self.model
        open_y = round(self.y_of(m.window_open))
        for x in range(0, PLAY.right, 10):
            pygame.draw.line(s, OPEN_LINE, (x, open_y), (x + 5, open_y), 1)
        say(s, 'OPEN', 4, open_y + 3, 12, MUTED)

        # Bell posts, one per window, riding in toward the wheel.
        for k in (-1, 0, 1):
            bx = round(self.x_at(m.window_end + k * m.WINDOW_S))
            if -2 <= bx <= PLAY.right + 2:
                for y in range(PLAY.top + 26, PLAY.bottom, 8):
                    pygame.draw.line(s, POST_NOW if k == 0 else POST, (bx, y), (bx, y + 3))
        bell_x = self.x_at(m.window_end)
        if m.settling:
            say(s, 'SETTLING', max(40, bell_x), PLAY.top + 5, 14, RED, True)
        else:
            left = m.remaining(self.clock)
            say(s, f'{int(left):02d}s', bell_x, PLAY.top + 2, 20,
                RED if left <= 3 else YELLOW, True)

        self.draw_settled(s)
        self.draw_bets(s)
        self.draw_trace(s)
        self.sparks.draw(s)
        ride_y = self.rider_y()
        if ride_y != self.y_of(self.ride_price):
            say(s, 'OFF SCALE', RIDER_X + 18, ride_y - 16, 12, YELLOW)
        self.rider.draw(s, RIDER_X, ride_y, self.spin())
        self.floaters.draw(s)

    def draw_trace(self, s: pygame.Surface) -> None:
        m = self.model
        ride_y = self.rider_y()
        # History holds a minute of ticks for the volatility estimate; only the
        # few seconds behind the rider are drawn, so walk back and stop there.
        points = []
        for t, p in reversed(m.history):
            x = self.x_at(t)
            # The wheel is eased; the last raw tick would put a jag under it.
            if x < RIDER_X - 3:
                points.append((x, self.y_of(p)))
            if x < -4:
                break
        points.reverse()
        points.append((RIDER_X, ride_y))
        clip = s.get_clip()
        s.set_clip(PLAY)
        if len(points) > 1:
            self.shade.fill((0, 0, 0, 0))
            hill = [(x, y - PLAY.top) for x, y in points]
            hill += [(RIDER_X, PLAY.height), (points[0][0], PLAY.height)]
            pygame.draw.polygon(self.shade, SHADE, hill)
            s.blit(self.shade, PLAY.topleft)
            pygame.draw.lines(s, GLOW, False, points, 6)
            pygame.draw.lines(s, CREAM, False, points, 2)
        # Where the price is now, carried forward to read against the boxes.
        for x in range(RIDER_X + 16, PLAY.right, 8):
            pygame.draw.line(s, (150, 146, 128), (x, round(ride_y)), (x + 3, round(ride_y)))
        s.set_clip(clip)

    def box_rect(self, x: float, low: float, high: float) -> pygame.Rect:
        top = max(BAND_TOP, min(BAND_BOTTOM - 8, round(self.y_of(high))))
        bottom = max(top + 8, min(BAND_BOTTOM, round(self.y_of(low))))
        return pygame.Rect(round(x - BOX_W / 2), top, BOX_W, bottom - top)

    def draw_box(self, s: pygame.Surface, x: float, low: float, high: float, color: tuple,
                 alpha: int = 48, dashed: bool = False, grow: int = 0,
                 width: int = 3) -> pygame.Rect:
        rect = self.box_rect(x, low, high).inflate(grow, grow)
        if alpha:
            glass = pygame.Surface(rect.size, pygame.SRCALPHA)
            glass.fill((*color, alpha))
            s.blit(glass, rect)
        if dashed:
            dashed_rect(s, rect, color)
        else:
            pygame.draw.rect(s, color, rect, width, border_radius=3)
        # Past the edge of the visible band: say so rather than lie about it.
        cx = rect.centerx
        if self.y_of(high) < BAND_TOP:
            pygame.draw.polygon(s, color, [(cx, rect.top + 4), (cx - 6, rect.top + 12),
                                           (cx + 6, rect.top + 12)])
        if self.y_of(low) > BAND_BOTTOM:
            pygame.draw.polygon(s, color, [(cx, rect.bottom - 4), (cx - 6, rect.bottom - 12),
                                           (cx + 6, rect.bottom - 12)])
        return rect

    def box_tag(self, s: pygame.Surface, rect: pygame.Rect, text: str, color: tuple) -> None:
        y = rect.top - 17 if rect.top - 17 >= PLAY.top + 22 else rect.bottom + 3
        say(s, text, rect.centerx, y, 14, color, True)

    def draw_bets(self, s: pygame.Surface) -> None:
        m = self.model
        now = self.clock
        if m.live is not None and m.live.stake:
            left = m.remaining(now)
            urgent = left <= 3 and int(now * 6) % 2 == 0
            rect = self.draw_box(s, self.x_at(m.window_end), m.live.low, m.live.high, YELLOW,
                                 alpha=96 if m.inside else 40, width=4 if urgent else 3)
            self.box_tag(s, rect, f'{self.stake_text(m.live.stake)} @ {m.live.multiple:.1f}x', YELLOW)

        if self.ghost is not None:
            level, half, bell, since = self.ghost
            fade = (now - since) / .45
            if fade < 1:
                self.draw_box(s, self.x_at(bell), level - half, level + half,
                              mix(YELLOW, POST, fade), alpha=0, dashed=True)

        next_x = self.x_at(m.window_end + m.WINDOW_S)
        if m.locked:
            p = (now - self.pop_at) / .25
            grow = round(10 * (1 - p)) if p < 1 else 0
            t = now - self.shake_at
            if t < .3:
                next_x += 4 * math.sin(t * 60) * (1 - t / .3)
            rect = self.draw_box(s, next_x, m.pending.low, m.pending.high, CREAM, grow=grow)
            self.box_tag(s, rect, f'{self.stake_text(m.pending.stake)} @ {m.pending.multiple:.1f}x',
                         CREAM)
        else:
            # A fresh cursor slides in from the right edge after each bell.
            next_x += 60 * (1 - ease_out((now - self.aim_in_at) / .45))
            half = m.half
            rect = self.draw_box(s, next_x, self.aim_price - half, self.aim_price + half, YELLOW,
                                 alpha=18, dashed=True)
            if m.quiet(now) or not m.measured:
                # No quote on offer: a flat line is not a 2x bet.
                self.box_tag(s, rect, 'QUIET' if m.quiet(now) else '...', MUTED)
            else:
                quote = m.quote(m.aim, now)
                self.box_tag(s, rect, f'{quote:.1f}x',
                             YELLOW if quote >= m.MIN_MULTIPLE else MUTED)

    def draw_settled(self, s: pygame.Surface) -> None:
        """Boxes that already rang stay in the world and scroll away behind him."""
        for result, bell in self.settled:
            x = self.x_at(bell)
            if x < -BOX_W:
                continue
            color = MUTED if result.voided else (MINT if result.hit else RED)
            fade = min(1.0, max(0.0, (self.clock - bell) / 7))
            self.draw_box(s, x, result.low, result.high, mix(color, POST, fade),
                          alpha=round(70 * (1 - fade)))
            # Where the price actually landed, so a miss shows by how much.
            pygame.draw.circle(s, mix(color, POST, fade), (round(x), round(self.y_of(result.price))), 3)

    def status(self) -> tuple[str, tuple]:
        """The one line of words at the bottom, as text and colour.

        Separate from drawing so the money it quotes can be asserted; the
        payout is micro-USDC like every other balance in the game.
        """
        m = self.model
        result = m.last
        if self.clock < self.message_until:
            return self.message, MINT
        if result is not None and self.clock < self.flash_until + 3:
            if result.voided:
                return f'VOID / {self.stake_text(result.stake)} BACK', MUTED
            if result.hit:
                return f'HIT / PAID {format_usdc(result.payout)}', MINT
            return f'MISS / -{self.stake_text(result.stake)}', RED
        if m.live is not None and m.live.stake:
            return (f'{self.stake_text(m.live.stake)} IN / PAYS '
                    f'{format_usdc(int(m.live.payout))}'), YELLOW
        if m.pending is not None:
            return f'PLACED / A ADDS {self.stake_text()} MORE', CREAM
        if m.quiet(self.clock):
            return 'MARKET QUIET / NO BETS', MUTED
        if not m.measured:
            return 'READING THE MARKET...', MUTED
        return f'CRANK / A BUYS NEXT {self.model.WINDOW_S:.0f}s', MUTED

    def draw_status(self, s: pygame.Surface) -> None:
        m = self.model
        text, color = self.status()
        say(s, text[:27], 10, PLAY.bottom + 6, 16, color)
        if self.streak >= 2:
            say_right(s, f'STREAK {self.streak}', 470, PLAY.bottom + 7, 15,
                      (255, 138, 40) if self.streak >= 3 else YELLOW)
        elif m.rounds:
            say_right(s, f'HITS {m.hits}/{m.rounds}', 470, PLAY.bottom + 7, 15, MUTED)

    def draw_wallet(self, s: pygame.Surface) -> None:
        wallet = self.model.wallet
        if self.onchain:
            self.draw_arc_wallet(s)
            return
        label(s, f'LOAD {wallet.funding.name} USDC', 240, 50, 26, YELLOW, True)
        label(s, 'LOCAL TEST BALANCE / NO REAL MONEY', 240, 88, 15, MUTED, True)
        for i, amount in enumerate(LOAD_CHOICES):
            rect = pygame.Rect(16 + i * 155, 122, 140, 66)
            pygame.draw.rect(s, YELLOW if i == self.amount_index else GRID, rect, border_radius=4)
            label(s, f'+{amount}', rect.centerx, 138, 28,
                  NAVY if i == self.amount_index else CREAM, True)
        label(s, 'UP / DOWN TO CHOOSE', 240, 204, 17, MUTED, True)
        label(s, f'{len(wallet.deposits)} LOADS THIS SESSION', 240, 236, 15, CREAM, True)
        footer(s, '< BACK', 'LOAD >')

    def draw_arc_wallet(self, s: pygame.Surface) -> None:
        """Real funds: the device's address as a QR code, and what the money is doing."""
        m = self.model
        funding = m.wallet.funding
        self.draw_qr(s, funding.qr_text, pygame.Rect(14, 38, 164, 164))
        x = 190
        label(s, 'SEND USDC ON', x, 40, 18, YELLOW)
        label(s, funding.net.name, x, 60, 18, YELLOW)
        label(s, funding.address[:22], x, 88, 13, CREAM)
        label(s, funding.address[22:], x, 104, 13, CREAM)
        text, color = self.arc_status()
        label(s, text[:26], x, 132, 15, color)
        label(s, f'KEEPS {format_usdc(funding.gas_fee)} OF EACH FOR GAS', x, 156, 11, MUTED)
        if funding.error:
            label(s, funding.error[:36], x, 176, 11, RED)
        if funding.in_session:
            label(s, f'BALANCE {format_usdc(m.wallet.balance)} USDC', 14, 212, 17, MINT)
            label(s, f'A: CASH OUT TO {short_address(funding.player)}', 14, 238, 15, CREAM)
        elif funding.last_cashout is not None:
            paid, player, tx = funding.last_cashout
            label(s, f'SENT {format_usdc(paid)} TO {short_address(player)}', 14, 212, 17, MINT)
            label(s, f'TX {tx[:12]}..{tx[-6:]}', 14, 238, 13, MUTED)
        else:
            label(s, 'SCAN IN METAMASK AND SEND ANY AMOUNT', 14, 212, 15, CREAM)
            label(s, f'MAX WIN IS 5x THE DEPOSIT', 14, 238, 13, MUTED)
        footer(s, '< BACK', 'CASH OUT >' if funding.in_session and not self.cashing else '')

    def arc_status(self) -> tuple[str, tuple]:
        funding = self.model.wallet.funding
        if self.cashing:
            return 'FINISHING LIVE BOX...', YELLOW
        if funding.pending_cashout is not None:
            return 'SENDING USDC...', YELLOW
        if funding.busy:
            return f'{funding.status}...', YELLOW
        if funding.error:
            return 'ARC UNREACHABLE', RED
        if funding.in_session and funding.last_deposit is not None:
            amount, sender = funding.last_deposit
            return f'+{format_usdc(amount)} FROM {short_address(sender)}', MINT
        if funding.in_session:
            return 'IN PLAY', MINT
        return 'WAITING FOR USDC' + '.' * (int(self.clock * 2) % 4), CREAM

    def draw_qr(self, s: pygame.Surface, text: str, rect: pygame.Rect) -> None:
        """A QR code of `text`, dark on white with its quiet zone, built once."""
        if self.qr is None or self.qr[0] != text:
            import qrcode              # real funds only; demo play does not need it
            code = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            code.add_data(text)
            code.make(fit=True)
            matrix = code.get_matrix()
            cell = max(1, min(rect.w, rect.h) // len(matrix))
            image = pygame.Surface((len(matrix) * cell, len(matrix) * cell))
            image.fill((255, 255, 255))
            for y, row in enumerate(matrix):
                for x, dark in enumerate(row):
                    if dark:
                        image.fill((0, 0, 0), (x * cell, y * cell, cell, cell))
            self.qr = (text, image)
        image = self.qr[1]
        s.blit(image, image.get_rect(center=rect.center))


def handle_box_events(game: BoxGame, events: list, actions: list[InputAction]) -> str | None:
    for event in events:
        if event.type == pygame.WINDOWFOCUSLOST:
            game.held.clear()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                game.open_wallet()
            elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s) and not game.wallet_open:
                # Held keys emulate a spun dial for desktop testing.
                game.held[event.key] = .12
        elif event.type == pygame.KEYUP:
            game.held.pop(event.key, None)
        pos = event_position(event)
        if pos is not None:
            target = game.handle_touch(pos)
            if target:
                return target
    for action in actions:
        target = game.handle_action(action)
        if target:
            return target
    return None
