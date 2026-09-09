"""Capture the actual UI using deterministic practice rounds; no image generation."""
from pathlib import Path
import pygame
from games.box_run import BoxRunGame
from screens.home import HomeScreen


def main():
    pygame.init()
    pygame.display.set_mode((480, 320))
    output = Path(__file__).resolve().parents[1] / 'design' / 'box-run-build'
    output.mkdir(parents=True, exist_ok=True)
    surface = pygame.Surface((480, 320))
    board = pygame.Surface((1480, 1050))
    board.fill((225, 223, 215))
    game = BoxRunGame(seed=4, sound=False)
    for i, state in enumerate(['home', 'aim', 'size', 'review', 'running', 'miss', 'hit', 'empty']):
        if state == 'home':
            HomeScreen('box_run').draw(surface, {})
        else:
            if state in ('size', 'review'):
                game.model.confirm()
            elif state == 'running':
                game.model.confirm()
                game.update(17)
            elif state == 'miss':
                game.update(3)
            elif state == 'hit':
                # Pick a reproducible seed; do not alter the live game's rules.
                game = BoxRunGame(seed=7, sound=False)
                for _ in range(3):
                    game.model.confirm()
                game.update(20)
                assert game.model.hit
            elif state == 'empty':
                game.model.balance = 0
                game.model.reset_prediction()
            game.draw(surface)
        pygame.image.save(surface, output / f'{state}.png')
        board.blit(surface, (10 + (i % 3) * 490, 20 + (i // 3) * 350))
    pygame.image.save(board, output / 'gameplay-sheet.png')
    pygame.quit()


if __name__ == '__main__':
    main()
