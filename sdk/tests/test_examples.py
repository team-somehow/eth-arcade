"""Every shipped example runs headless and draws a frame without raising.

Run with a dummy display, as CI and the Makefile do:

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -t .
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

from tick import Game
from tick.money import MICRO
from tick.testing import Harness

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return [v for v in vars(module).values()
            if isinstance(v, type) and issubclass(v, Game) and v is not Game][-1]


class TestExamples(unittest.TestCase):
    paths = [ROOT / 'examples' / 'coinflip.py',
             ROOT / 'examples' / 'ladder.py',
             ROOT / 'tick' / 'templates' / 'game.py']

    def test_each_example_plays_and_draws(self):
        from tick import InputAction
        for path in self.paths:
            with self.subTest(example=path.name):
                game = load(path)()
                with Harness(game, balance=1000 * MICRO, stake=10 * MICRO) as h:
                    h.warm(25)
                    h.draw_once()                       # a cold screen
                    h.press(InputAction.UP)
                    h.press(InputAction.UP)
                    h.press(InputAction.A)
                    h.draw_once()                       # with a bet on it
                    h.advance(25)
                    h.draw_once()                       # after a settlement
                    self.assertGreater(h.rounds.index, 2)

    def test_an_example_never_spends_money_it_does_not_have(self):
        from tick import InputAction
        for path in self.paths:
            with self.subTest(example=path.name):
                with Harness(load(path)(), balance=25 * MICRO, stake=10 * MICRO) as h:
                    h.warm(25)
                    for _ in range(40):
                        h.press(InputAction.A)
                        h.advance(1.0)
                    self.assertGreaterEqual(h.balance, 0)


if __name__ == '__main__':
    unittest.main()
