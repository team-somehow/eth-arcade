import os
import sys
import unittest
from decimal import Decimal
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pygame

from input import InputAction
from names import Standing
from screens.board import TOP, YOU_Y, BoardFeed, BoardScreen, signed_usdc

ME = '0x0Dd7D7Ad21d15A999dcc7218E7Df3F25700e696f'


def standing(i: int, player: str | None = None) -> Standing:
    return Standing(f'player-{i}.tick.eth', player or f'0x{i:040x}', 3, 1,
                    Decimal(10 - i), Decimal('0.5'))


class StubFeed:
    def __init__(self, rows=None, error=''):
        self.rows, self.error, self.updated, self.showing = rows, error, 0.0, False
        self.wanted = 0

    def want(self):
        self.wanted += 1


def screen(rows=None, me='', error='', names=None) -> BoardScreen:
    funding = SimpleNamespace(player=me, last_cashout=None, names=names or {})
    game = SimpleNamespace(model=SimpleNamespace(wallet=SimpleNamespace(funding=funding)))
    return BoardScreen(game, StubFeed(rows, error))


class BoardTests(unittest.TestCase):
    """The leaderboard: the top players, and the one on this device picked out."""

    def setUp(self):
        pygame.init()

    def test_money_reads_with_its_sign(self):
        self.assertEqual(signed_usdc(Decimal('0.005')), '+0.005')
        self.assertEqual(signed_usdc(Decimal('-1.5')), '-1.50')
        self.assertEqual(signed_usdc(Decimal('0')), '0.00')

    def test_nobody_playing_shows_the_top(self):
        rows = [standing(i) for i in range(10)]
        placed = screen(rows).layout(rows, '')
        self.assertEqual([rank for _, rank, _, _ in placed], list(range(1, TOP + 1)))
        self.assertFalse(any(mine for *_, mine in placed))

    def test_a_player_in_the_top_is_lit_in_place(self):
        rows = [standing(i, ME if i == 2 else None) for i in range(10)]
        placed = screen(rows, ME).layout(rows, ME.lower())
        self.assertEqual(len(placed), TOP)
        self.assertEqual([rank for _, rank, _, mine in placed if mine], [3])

    def test_a_player_further_down_gets_their_own_row(self):
        rows = [standing(i, ME if i == 11 else None) for i in range(15)]
        placed = screen(rows, ME).layout(rows, ME)
        self.assertEqual(len(placed), TOP)
        y, rank, row, mine = placed[-1]
        self.assertEqual((y, rank, row.player, mine), (YOU_Y, 12, ME, True))

    def test_a_player_not_scored_yet_is_shown_unranked(self):
        rows = [standing(i) for i in range(3)]
        y, rank, row, mine = screen(rows, ME).layout(rows, ME)[-1]
        self.assertEqual((y, rank, row, mine), (YOU_Y, 0, None, True))

    def test_the_last_player_paid_counts_as_ours(self):
        board = screen([])
        board.funding.last_cashout = (1, ME, '0xtx')
        self.assertEqual(board.me(), ME)

    def test_b_goes_home_and_a_reads_again(self):
        board = screen([])
        self.assertEqual(board.handle_action(InputAction.B), 'home')
        self.assertIsNone(board.handle_action(InputAction.A))
        self.assertEqual(board.feed.wanted, 1)
        self.assertEqual(board.handle_touch((100, 300)), 'home')

    def test_every_state_draws(self):
        rows = [standing(i, ME if i == 9 else None) for i in range(12)]
        surface = pygame.Surface((480, 320))
        for board in (screen(), screen(error='timed out'), screen([]), screen(rows),
                      screen(rows, ME), screen(rows[:3], ME, names={ME: 'fancy-panda.tick.eth'}),
                      screen(rows, ME, error='timed out')):
            board.draw(surface)


class FeedTests(unittest.TestCase):
    def test_a_failed_read_keeps_the_last_rows(self):
        answers = [[standing(1)], OSError('no route')]

        def read():
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        feed = BoardFeed(read)
        self.assertTrue(feed.refresh())
        self.assertFalse(feed.refresh())
        self.assertEqual(len(feed.rows), 1)
        self.assertEqual(feed.error, 'no route')


if __name__ == '__main__':
    unittest.main()
