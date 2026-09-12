"""Placing, topping up, settling, refunding -- every path money takes."""
import unittest

from tick.bets import BetBook
from tick.money import MICRO, DemoFunding, Wallet
from tick.rounds import Round


def closed_round(index=1, price=2500.0, voided=False):
    r = Round(index, 2500.0, 0.0, 10.0)
    r.close_price, r.closed_at, r.voided = price, 10.0, voided
    return r


class TestBook(unittest.TestCase):
    def setUp(self):
        self.wallet = Wallet(100 * MICRO, DemoFunding())
        self.book = BetBook(self.wallet)

    def test_placing_debits_at_once(self):
        self.book.place(1, 2499, 2501, 10 * MICRO, 2.0)
        self.assertEqual(self.wallet.balance, 90 * MICRO)

    def test_a_bet_the_wallet_cannot_cover_is_refused_and_costs_nothing(self):
        self.assertIsNone(self.book.place(1, 2499, 2501, 200 * MICRO, 2.0))
        self.assertEqual(self.wallet.balance, 100 * MICRO)
        self.assertEqual(self.book.open, [])

    def test_topping_up_blends_the_multiple_at_each_press_own_odds(self):
        self.book.place(1, 2499, 2501, 10 * MICRO, 2.0)
        bet = self.book.place(1, 2499, 2501, 10 * MICRO, 4.0)
        self.assertEqual(bet.presses, 2)
        self.assertEqual(bet.stake, 20 * MICRO)
        self.assertAlmostEqual(bet.multiple, 3.0)      # not 2.0, and not 4.0

    def test_a_hit_pays_the_blended_payout(self):
        self.book.place(1, 2499, 2501, 10 * MICRO, 2.5)
        settled = self.book.settle(closed_round(price=2500.0))
        self.assertTrue(settled[0].hit)
        self.assertEqual(settled[0].payout, 25 * MICRO)
        self.assertEqual(self.wallet.balance, 115 * MICRO)

    def test_the_boundary_counts_as_inside(self):
        self.book.place(1, 2499, 2501, 10 * MICRO, 2.0)
        self.assertTrue(self.book.settle(closed_round(price=2501.0))[0].hit)

    def test_a_miss_pays_nothing(self):
        self.book.place(1, 2499, 2501, 10 * MICRO, 2.0)
        settled = self.book.settle(closed_round(price=2501.01))
        self.assertFalse(settled[0].hit)
        self.assertEqual(settled[0].payout, 0)
        self.assertEqual(self.wallet.balance, 90 * MICRO)

    def test_a_payout_is_truncated_never_rounded_up(self):
        self.book.place(1, 2499, 2501, 3, 1.5)     # 3 micro at 1.5x = 4.5
        settled = self.book.settle(closed_round(price=2500.0))
        self.assertEqual(settled[0].payout, 4)

    def test_a_void_refunds_and_counts_as_neither_win_nor_loss(self):
        self.book.place(1, 2499, 2501, 10 * MICRO, 2.0)
        settled = self.book.settle(closed_round(price=2500.0, voided=True))
        self.assertTrue(settled[0].voided)
        self.assertEqual(self.wallet.balance, 100 * MICRO)
        self.assertEqual(self.book.hits, 0)

    def test_settling_one_round_leaves_another_alone(self):
        self.book.place(1, 2499, 2501, 10 * MICRO, 2.0)
        self.book.place(2, 2499, 2501, 10 * MICRO, 2.0)
        self.book.settle(closed_round(index=1, price=2500.0))
        self.assertEqual(len(self.book.open), 1)
        self.assertEqual(self.book.open[0].round_index, 2)

    def test_refund_returns_a_future_round_stake(self):
        self.book.place(2, 2499, 2501, 10 * MICRO, 2.0)
        self.assertEqual(self.book.refund(2), 10 * MICRO)
        self.assertEqual(self.wallet.balance, 100 * MICRO)

    def test_best_case_is_what_the_book_owes_if_everything_lands(self):
        self.book.place(1, 2499, 2501, 10 * MICRO, 2.0)
        self.book.place(2, 2499, 2501, 10 * MICRO, 3.0)
        self.assertAlmostEqual(self.book.best_case(), 50 * MICRO)

    def test_streak_counts_consecutive_hits_and_ignores_voids(self):
        for _ in range(3):
            self.book.place(1, 2499, 2501, MICRO, 2.0)
            self.book.settle(closed_round(price=2500.0))
        self.assertEqual(self.book.streak, 3)
        self.book.place(1, 2499, 2501, MICRO, 2.0)
        self.book.settle(closed_round(price=2600.0))
        self.assertEqual(self.book.streak, 0)


if __name__ == '__main__':
    unittest.main()
