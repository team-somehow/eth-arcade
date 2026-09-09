"""Capture the actual RUSH UI by cranking a deterministic sim; no image generation."""
from pathlib import Path

import pygame

from games.rush import RushGame
from screens.home import HomeScreen
from wallet import MICRO, DemoFunding, Wallet

FRAME = 1/30


def warm(game: RushGame, seconds: float) -> None:
    """Advance the sim feed so the chart and price are populated."""
    for _ in range(int(seconds / FRAME)):
        game.update(FRAME)


def new_game(seed: int) -> RushGame:
    return RushGame(seed=seed, sound=False, source='sim',
                    wallet=Wallet(100 * MICRO, DemoFunding()))


def main() -> None:
    pygame.init()
    pygame.display.set_mode((480, 320))
    output = Path(__file__).resolve().parents[1] / 'design' / 'rush-build'
    output.mkdir(parents=True, exist_ok=True)
    surface = pygame.Surface((480, 320))
    board = pygame.Surface((1480, 1050))
    board.fill((225, 223, 215))

    states = ['home', 'ready', 'arming', 'riding', 'redline', 'settled', 'wallet']
    game = new_game(4)
    warm(game, 3)
    for i, state in enumerate(states):
        if state == 'home':
            HomeScreen().draw(surface)
        else:
            if state == 'arming':
                game.crank(1)
            elif state == 'riding':
                game.crank(1)          # opens the ride
                for _ in range(20):
                    game.crank(1)
                    game.update(FRAME)
            elif state == 'redline':
                for _ in range(40):
                    game.crank(1)
                    game.update(FRAME)
            elif state == 'settled':
                game.model.bail(game.clock, 'Bailed out')
                warm(game, .5)
                assert game.model.phase == 'ready'
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
