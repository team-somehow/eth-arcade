"""Capture the actual BOX RUN UI from the real game on a scripted clock.

No image generation. The clock is injected so the sequence is reproducible, and
the price is steered — the real sim feed plus a slowly ramped offset — so a hit,
a miss and a hat trick can each be photographed. Everything drawn is the real
renderer reading the real model.
"""
from dataclasses import replace
from pathlib import Path

import pygame

from games.box import BoxGame, BOX_W, STREET_BOTTOM
from screens.home import HomeScreen
from ui import CREAM, MINT, MUTED, YELLOW, RED, font
from wallet import MICRO, DemoFunding, Wallet

FRAME = 1/30
STATES = ['home', 'waiting', 'aiming', 'bought', 'live', 'hit', 'miss', 'hattrick', 'wallet']


class Clock:
    def __init__(self, start: float = 5000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t


class Steered:
    """The sim feed, plus an offset that ramps to wherever the shot needs it.

    The offset is kept once reached, so the price never snaps back: the trace
    looks like a market that happened to walk there.
    """

    def __init__(self, inner) -> None:
        self.inner, self.name = inner, inner.name
        self.offset = 0.0
        self.plan: tuple[float, float, float, float] | None = None  # from, to, start, ramp
        self.last = 0.0

    def aim_for(self, price: float, start: float, ramp: float = 2.0) -> None:
        self.plan = (self.offset, price, start, ramp)

    def poll(self, dt, now):
        out = []
        for tick in self.inner.poll(dt, now):
            if self.plan is not None:
                was, goal, start, ramp = self.plan
                if now >= start:
                    blend = min(1.0, (now - start) / ramp)
                    self.offset = was + (goal - tick.price - was) * blend
            out.append(replace(tick, price=tick.price + self.offset))
        return out

    def close(self) -> None:
        self.inner.close()


def new_game(clock: Clock, seed: int = 11) -> BoxGame:
    game = BoxGame(seed=seed, sound=False, source='sim',
                   wallet=Wallet(100 * MICRO, DemoFunding()), clock=clock)
    game.feed = Steered(game.feed)
    return game


def run(game: BoxGame, clock: Clock, seconds: float) -> None:
    for _ in range(int(seconds / FRAME)):
        clock.t += FRAME
        game.update(FRAME)


def ride_to_bell(game: BoxGame, clock: Clock, price: float, after: float) -> None:
    """Walk the price to `price` over the last seconds, then run past the bell."""
    m = game.model
    game.feed.aim_for(price, m.window_end - 3.2)
    run(game, clock, m.remaining(clock.t) + after)


def to_live(game: BoxGame, clock: Clock) -> None:
    """Buy the next window, then wait out the bell so the box is the live one."""
    game.buy()
    run(game, clock, game.model.remaining(clock.t) + .5)


def touch_sheet(frame: pygame.Surface, game: BoxGame) -> pygame.Surface:
    """The live frame at 2x, with every place you can tap drawn over it."""
    m = game.model
    scale = 2
    art = pygame.transform.scale(frame, (frame.get_width() * scale, frame.get_height() * scale))
    aim = game.box_rect(game.x_at(m.window_end + m.WINDOW_S),
                        game.aim_price - m.half, game.aim_price + m.half)
    play_top, play_bottom = 34, STREET_BOTTOM - 32

    def zone(rect, color, alpha=70):
        glass = pygame.Surface((rect[2] * scale, rect[3] * scale), pygame.SRCALPHA)
        glass.fill((*color, alpha))
        art.blit(glass, (rect[0] * scale, rect[1] * scale))
        pygame.draw.rect(art, color, [v * scale for v in rect], 3)

    zone((0, play_top, 480, aim.centery - play_top), MINT, 45)
    zone((0, aim.centery, 480, play_bottom - aim.centery), (110, 150, 255), 45)
    zone((0, STREET_BOTTOM, 240, 320 - STREET_BOTTOM), RED)
    zone((240, STREET_BOTTOM, 240, 320 - STREET_BOTTOM), YELLOW)
    pad = aim.inflate(28, 28)
    pygame.draw.rect(art, (255, 90, 220), [v * scale for v in pad], 4, border_radius=8)

    def tag(text, x, y, color):
        t = font(22).render(text, False, color)
        back = pygame.Surface((t.get_width() + 12, t.get_height() + 6), pygame.SRCALPHA)
        back.fill((0, 0, 0, 190))
        art.blit(back, (x - 6, y - 3))
        art.blit(t, (x, y))

    tag('TAP ABOVE THE BOX = MOVE IT UP', 20, (play_top + 22) * scale, MINT)
    tag('TAP BELOW THE BOX = MOVE IT DOWN', 20, (play_bottom - 22) * scale, (150, 180, 255))
    tag('OPTION: TAP ON THE BOX = BUY 10', 500, (pad.bottom + 4) * scale, (255, 90, 220))

    sheet = pygame.Surface((art.get_width() + 460, art.get_height()))
    sheet.fill((18, 22, 30))
    sheet.blit(art, (0, 0))
    notes = [
        ('WHERE YOU CAN TAP', YELLOW, 30),
        ('', CREAM, 20),
        ('GREEN   tap above the dashed box:', MINT, 20),
        ('        it moves up one step', CREAM, 20),
        ('BLUE    tap below it: moves down', (150, 180, 255), 20),
        ('RED     < HOME', RED, 20),
        ('YELLOW  BUY 10 (the A button)', YELLOW, 20),
        ('', CREAM, 20),
        ('THE QUESTION', (255, 90, 220), 26),
        ('Should tapping ON the box', CREAM, 20),
        ('(pink outline) also buy it?', CREAM, 20),
        ('', CREAM, 20),
        ('YES: aim + buy with one finger,', MUTED, 20),
        ('     fastest to play.', MUTED, 20),
        ('NO:  a finger that lands a bit', MUTED, 20),
        ('     off while nudging the box', MUTED, 20),
        ('     spends 10 USDC by accident.', MUTED, 20),
        ('', CREAM, 20),
        ('BUILT NOW: NO. Buying is only', CREAM, 20),
        ('the yellow BUY button / A.', CREAM, 20),
    ]
    y = 30
    for text, color, size in notes:
        sheet.blit(font(size).render(text, False, color), (art.get_width() + 24, y))
        y += size + 10
    return sheet


def main() -> None:
    pygame.init()
    pygame.display.set_mode((480, 320))
    output = Path(__file__).resolve().parents[1] / 'design' / 'box-run-live'
    output.mkdir(parents=True, exist_ok=True)
    surface = pygame.Surface((480, 320))
    board = pygame.Surface((1480, 1050))
    board.fill((225, 223, 215))

    clock = Clock()
    game = new_game(clock)
    for i, state in enumerate(STATES):
        if state == 'home':
            HomeScreen('box').draw(surface)
        else:
            if state == 'aiming':
                run(game, clock, 12)
                game.crank(5)
                run(game, clock, .5)
            elif state == 'bought':
                game.buy()
                game.buy()
                run(game, clock, .5)
            elif state == 'live':
                run(game, clock, game.model.remaining(clock.t) + 1.5)
                game.crank(-4)
                run(game, clock, .6)
            elif state in ('hit', 'miss'):
                game = new_game(clock, seed=3 if state == 'hit' else 5)
                run(game, clock, 12)
                if state == 'miss':
                    game.crank(2)
                to_live(game, clock)
                m = game.model
                target = m.live.level if state == 'hit' else m.live.high + 1.6 * m.half
                ride_to_bell(game, clock, target, .3)
                print(state, 'hit' if m.last.hit else 'miss')
            elif state == 'hattrick':
                game = new_game(clock, seed=9)
                run(game, clock, 12)
                to_live(game, clock)
                for _ in range(3):
                    game.buy()                       # the next one rides in behind
                    m = game.model
                    ride_to_bell(game, clock, m.live.level, .15)
                    print('hattrick leg', 'hit' if m.last.hit else 'miss', 'streak', game.streak)
                run(game, clock, .5)
            elif state == 'wallet':
                game.open_wallet()
            game.draw(surface)
        pygame.image.save(surface, output / f'{state}.png')
        if state == 'live':
            pygame.image.save(touch_sheet(surface, game), output / 'touch-zones.png')
        board.blit(surface, (10 + (i % 3) * 490, 20 + (i // 3) * 350))
    pygame.image.save(board, output / 'gameplay-sheet.png')
    game.close()
    pygame.quit()


if __name__ == '__main__':
    main()
