import os
import sys
import unittest
from decimal import Decimal
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pygame

from input import InputAction
from names import Standing
from screens.board import TOP, YOU_Y, BoardFeed, BoardScreen, rank_of, signed_usdc

ME = '0x0Dd7D7Ad21d15A999dcc7218E7Df3F25700e696f'


def standing(i: int, player: str | None = None) -> Standing:
    return Standing(f'player-{i}.tick.eth', player or f'0x{i:040x}', 3, 1,
                    Decimal(10 - i), Decimal('0.5'))


class StubFeed:
    def __init__(self, rows=None, error=''):
        self.rows, self.error, self.updated, self.showing = rows, error, 0.0, False
        self.pending, self.hold = None, False
        self.wanted = 0

    def want(self):
        self.wanted += 1

    def take(self):
        self.hold = False
        if self.pending is not None:
            self.rows, self.pending = self.pending, None
        return self.rows


def screen(rows=None, me='', error='', names=None, in_session=False) -> BoardScreen:
    funding = SimpleNamespace(player=me, last_cashout=None, names=names or {},
                              in_session=in_session)
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

    def test_an_unranked_player_is_told_why(self):
        board = screen([], ME, in_session=True)
        self.assertEqual(board.waiting_note(), 'RANKED AFTER CASH OUT')
        board.funding.in_session = False        # cashed out: the scorekeeper has the rest
        self.assertTrue(board.waiting_note().startswith('SCORING ON ENS'))

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


def named(name: str, pnl, player: str | None = None, plays: int = 3) -> Standing:
    return Standing(f'{name}.tick.eth', player or f'0x{abs(hash(name)):040x}'[:42],
                    plays, 1, Decimal(str(pnl)), Decimal('0.5'))


# The run that takes our player from last of six to the podium.
CLIMB = [named('turbo-lynx', 812), named('misty-crab', 402.5), named('neon-yak', 101),
         named('sly-moose', 52), named('quiet-vole', 12), named('amber-otter', -18.4, ME)]


def scored(before: list, pnl) -> list:
    """The same board after the scorekeeper writes our player's closed session."""
    rows = [row for row in before if row.player != ME]
    mine = next(row for row in before if row.player == ME)
    rows.append(Standing(mine.name, ME, mine.sessions + 1, mine.wins,
                         Decimal(str(pnl)), mine.best))
    rows.sort(key=lambda row: (-row.pnl, -row.wins, row.name))
    return rows


class ArrivalTests(unittest.TestCase):
    """Coming in from a payout: the old picture, the wait, then the movement."""

    def setUp(self):
        pygame.init()
        self.canvas = pygame.Surface((480, 320))

    def board(self, before=None, me=ME):
        board = screen(list(before if before is not None else CLIMB), me)
        board.feed.rows = list(before if before is not None else CLIMB)
        return board

    def arrive(self, board, pnl, before=None):
        old = next((r.pnl for r in (before or CLIMB) if r.player == ME), Decimal(0))
        board.arrive(ME, Decimal(str(pnl)) - old)
        return scored(before or CLIMB, pnl)

    def run_move(self, board, after, seconds=6.0):
        board.feed.pending = after
        for _ in range(int(seconds * 30)):
            board.update(1 / 30)
            board.draw(self.canvas)
            if board.move is None and not board.waiting:
                break
        return board

    def test_it_holds_the_old_picture_and_says_what_it_is_waiting_for(self):
        board = self.board()
        self.arrive(board, 137.40)
        self.assertTrue(board.waiting)
        self.assertTrue(board.feed.hold)
        self.assertEqual(rank_of(board.feed.rows, ME), 5)       # still last
        board.draw(self.canvas)                                 # ghosted +155.80

    def test_a_read_is_parked_until_the_movement_has_run(self):
        after = scored(CLIMB, 137.40)
        answers = [list(CLIMB), after]
        board = screen(None, ME)
        board.feed = BoardFeed(lambda: answers.pop(0))
        board.feed.refresh()                                    # the board as it stands
        self.arrive(board, 137.40)
        board.feed.refresh()                                    # the scorekeeper writes
        self.assertEqual(board.feed.pending, after)
        self.assertEqual(rank_of(board.feed.rows, ME), 5)       # the board has not moved
        board.update(1 / 30)
        self.assertIsNotNone(board.move)

    def test_an_unscored_read_does_not_start_the_movement(self):
        board = self.board()
        self.arrive(board, 137.40)
        board.feed.pending = list(CLIMB)                        # same rows, same plays
        board.update(1 / 30)
        self.assertIsNone(board.move)
        self.assertTrue(board.waiting)

    def test_the_climb_moves_one_place_at_a_time_and_lands_on_the_podium(self):
        board = self.board()
        after = self.arrive(board, 137.40)
        board.feed.pending = after
        board.update(1 / 30)
        move = board.move
        self.assertEqual((move.start, move.end, move.steps, move.up), (5, 2, 3, True))
        seen = []
        for _ in range(int(move.length * 30) + 4):
            if board.move is not None:
                seen.append(board.move.rank_now())
            board.update(1 / 30)
            board.draw(self.canvas)
        self.assertEqual(sorted(set(seen), reverse=True), [6, 5, 4, 3])  # every place shown
        self.assertIsNone(board.move)
        self.assertEqual(rank_of(board.feed.rows, ME), 2)       # the held read is through
        self.assertTrue(board.again)
        self.assertEqual(board.handle_action(InputAction.A), 'money')

    def test_the_pnl_counts_up_and_settles_on_what_ens_holds(self):
        board = self.board()
        after = self.arrive(board, 137.40)
        board.feed.pending = after
        board.update(1 / 30)
        move = board.move
        self.assertEqual(move.pnl_now(), Decimal('-18.4'))      # holding: the old number
        move.update(move.HOLD_S + move.span / 2)
        self.assertTrue(Decimal('-18.4') < move.pnl_now() < Decimal('137.40'))
        move.update(move.length)
        self.assertEqual(move.pnl_now(), Decimal('137.40'))     # exact, not rounded

    def test_a_bad_run_slides_and_nothing_celebrates(self):
        before = [named('turbo-lynx', 812), named('misty-crab', 402.5),
                  named('amber-otter', 137.40, ME), named('neon-yak', 101),
                  named('sly-moose', 52), named('quiet-vole', 12)]
        board = self.board(before)
        after = self.arrive(board, -26.40, before)
        self.run_move(board, after)
        self.assertEqual(rank_of(board.feed.rows, ME), 5)
        self.assertTrue(board.again)

    def test_a_player_below_the_visible_list_counts_their_number_instead(self):
        before = [named(f'p{i}', 500 - i) for i in range(11)] + [named('amber-otter', -5, ME)]
        board = self.board(before)
        after = self.arrive(board, 300, before)
        board.feed.pending = after
        board.update(1 / 30)
        move = board.move
        self.assertFalse(move.swapping)         # nothing on screen to trade places with
        self.assertEqual(move.steps, 0)
        self.assertEqual(move.rank_now(), 12)   # still showing the old number
        move.update(move.length)
        self.assertEqual(move.rank_now(), move.end + 1)
        self.run_move(board, after)

    def test_a_pinned_row_stays_on_screen_for_the_whole_movement(self):
        """Its rank is off the bottom of the list, so it is drawn on the pinned
        row instead — not at a slot the screen does not reach."""
        before = [named(f'p{i}', 500 - i) for i in range(11)] + [named('amber-otter', -5, ME)]
        board = self.board(before)
        after = self.arrive(board, 300, before)
        board.feed.pending = after
        board.update(1 / 30)
        drawn = []
        board.draw_row = lambda s, y, rank, row, scale, **kw: (
            drawn.append((round(y), kw.get('mine', False))))
        for _ in range(int(board.move.length * 30)):
            board.draw(self.canvas)
            board.update(1 / 30)
        mine = {y for y, is_mine in drawn if is_mine}
        self.assertTrue(mine, 'the player was never drawn')
        self.assertTrue(all(y <= YOU_Y for y in mine), f'drawn off the screen at {sorted(mine)}')

    def test_a_climb_out_of_the_tail_flies_into_the_list(self):
        before = [named(f'p{i}', 500 - i) for i in range(11)] + [named('amber-otter', -5, ME)]
        board = self.board(before)
        after = self.arrive(board, 495.5, before)
        board.feed.pending = after
        board.update(1 / 30)
        move = board.move
        self.assertEqual((move.start, move.end, move.swapping), (11, 5, False))
        self.run_move(board, after)
        self.assertEqual(rank_of(board.feed.rows, ME), 5)

    def test_a_first_ever_run_flies_up_from_the_unranked_row(self):
        before = [named('turbo-lynx', 812), named('misty-crab', 402.5)]
        board = self.board(before, ME)
        board.arrive(ME, Decimal('60'))
        after = list(before) + [named('amber-otter', 60, ME, plays=1)]
        after.sort(key=lambda row: (-row.pnl, -row.wins, row.name))
        board.feed.pending = after
        board.update(1 / 30)
        move = board.move
        self.assertTrue(move.new)
        self.assertIsNone(move.start)
        self.assertFalse(move.swapping)         # no old place to trade away
        self.assertEqual(move.rank_now(), 0)    # holding: no rank to show yet
        move.update(move.HOLD_S + .01)
        self.assertEqual(move.rank_now(), 3)    # then the place it earned
        self.run_move(board, after)
        self.assertEqual(rank_of(board.feed.rows, ME), 2)

    def test_arriving_before_the_board_has_ever_read_still_moves(self):
        """The first read is never held back, so it becomes the picture to move
        from rather than the picture we wake up already showing."""
        board = screen(None, ME)
        board.feed.rows = None
        board.arrive(ME, Decimal('155.80'))
        self.assertIsNone(board.before)
        board.feed.rows = list(CLIMB)               # the first read lands
        board.update(1 / 30)
        self.assertEqual(rank_of(board.before, ME), 5)
        board.feed.pending = scored(CLIMB, 137.40)  # the next one is held
        board.update(1 / 30)
        self.assertIsNotNone(board.move)
        self.assertEqual((board.move.start, board.move.end), (5, 2))

    def test_it_gives_up_rather_than_wait_for_ens_forever(self):
        board = self.board()
        self.arrive(board, 137.40)
        board.update(BoardScreen.SCORE_WAIT_S + 1)
        self.assertFalse(board.waiting)
        self.assertTrue(board.gave_up)
        self.assertFalse(board.feed.hold)
        board.draw(self.canvas)                 # says so, rather than spinning

    def test_the_board_forgets_the_run_when_it_is_opened_again(self):
        board = self.board()
        after = self.arrive(board, 137.40)
        self.run_move(board, after)
        board.open()
        self.assertFalse(board.again)
        self.assertIsNone(board.handle_action(InputAction.A))   # A refreshes again


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

    def test_holding_parks_a_read_and_take_lets_it_through(self):
        rows = [[standing(1)], [standing(1), standing(2)]]
        feed = BoardFeed(lambda: rows[min(len(rows) - 1, feed_calls[0])])
        feed_calls = [0]
        feed.refresh()
        self.assertEqual(len(feed.rows), 1)
        feed.hold, feed_calls[0] = True, 1
        feed.refresh()
        self.assertEqual(len(feed.rows), 1)             # the board still shows the old one
        self.assertEqual(len(feed.pending), 2)
        self.assertEqual(len(feed.take()), 2)
        self.assertFalse(feed.hold)
        self.assertIsNone(feed.pending)

    def test_the_first_read_is_never_held_back(self):
        feed = BoardFeed(lambda: [standing(1)])
        feed.hold = True
        feed.refresh()
        self.assertEqual(len(feed.rows), 1)             # nothing to hold it against
        self.assertIsNone(feed.pending)


if __name__ == '__main__':
    unittest.main()
