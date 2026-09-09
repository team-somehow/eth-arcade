"""Capture the actual BOX RUN UI from the real game on a scripted clock.

No image generation. The clock is injected so the sequence is reproducible, and
the two settlement shots are handed a chosen expiry price so both outcomes can
be photographed; everything drawn is the real renderer reading the real model.
"""
from pathlib import Path

import pygame

from games.box import BoxGame
from markets.feed import PriceTick
from screens.home import HomeScreen
from wallet import MICRO, DemoFunding, Wallet

FRAME = 1/30
STATES = ['home', 'waiting', 'aiming', 'bought', 'live', 'hit', 'miss', 'wallet']


class Clock:
    def __init__(self, start: float = 5000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t


def new_game(clock: Clock, seed: int = 11) -> BoxGame:
    return BoxGame(seed=seed, sound=False, source='sim',
                   wallet=Wallet(100 * MICRO, DemoFunding()), clock=clock)


def run(game: BoxGame, clock: Clock, seconds: float) -> None:
    for _ in range(int(seconds / FRAME)):
        clock.t += FRAME
        game.update(FRAME)


def to_live(game: BoxGame, clock: Clock) -> None:
    """Buy the next window, then wait out the bell so the box is the live one."""
    game.buy()
    run(game, clock, game.model.remaining(clock.t) + .5)


def settle(game: BoxGame, clock: Clock, inside: bool) -> None:
    """Hand the model a chosen expiry price so both outcomes can be captured."""
    m = game.model
    clock.t = m.window_end + .05
    price = m.live.level if inside else m.live.high + 1.5 * m.half
    m.on_tick(PriceTick(price, m.tick.sequence + 1, clock.t), clock.t)
    game.clock = clock.t
    game.flash_until = clock.t + 1.6


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
            elif state == 'bought':
                game.buy()
                game.buy()
                game.crank(3)          # the dial stays live behind the bet
            elif state == 'live':
                run(game, clock, game.model.remaining(clock.t) + .5)
                game.crank(-4)
            elif state in ('hit', 'miss'):
                game = new_game(clock, seed=3 if state == 'hit' else 5)
                run(game, clock, 12)
                if state == 'miss':
                    game.crank(2)
                to_live(game, clock)
                settle(game, clock, inside=state == 'hit')
            elif state == 'wallet':
                game.open_wallet()
            game.draw(surface)
        pygame.image.save(surface, output / f'{state}.png')
        board.blit(surface, (10 + (i % 3) * 490, 20 + (i // 3) * 350))
    pygame.image.save(board, output / 'gameplay-sheet.png')
    game.close()
    pygame.quit()


if __name__ == '__main__':
    main()
