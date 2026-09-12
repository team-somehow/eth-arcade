"""The whole machine, headless: a real game class against a real market."""
import unittest

from tick import Game, InputAction
from tick.feeds.sim import FrozenFeed
from tick.money import MICRO
from tick.testing import Harness, ScriptedFeed


class Sitter(Game):
    """Bets a fixed band around spot whenever A is pressed. No drawing."""
    title = 'SITTER'
    window_s = 10.0
    band_bps = 4.0

    def setup(self, ctx):
        self.placed, self.settled, self.rounds_seen = [], [], 0

    def band(self, ctx):
        half = ctx.price * self.band_bps / 10_000
        return ctx.price - half, ctx.price + half

    def on_action(self, ctx, action):
        if action.name == 'A':
            low, high = self.band(ctx)
            bet = ctx.bet(low, high)
            if bet is not None:
                self.placed.append(bet)

    def on_settle(self, ctx, settlement):
        self.settled.append(settlement)

    def on_round_start(self, ctx, round_):
        self.rounds_seen += 1

    def draw(self, ctx, screen):
        pass


class TestLifecycle(unittest.TestCase):
    def test_the_clock_starts_on_the_first_price_and_keeps_rolling(self):
        with Harness(Sitter()) as h:
            h.advance(35)
            self.assertTrue(h.rounds.started)
            self.assertGreaterEqual(h.rounds.index, 3)
            self.assertGreaterEqual(h.game.rounds_seen, 3)

    def test_a_bet_is_debited_placed_and_settled_without_a_single_call_from_the_game(self):
        with Harness(Sitter(), balance=100 * MICRO, stake=10 * MICRO) as h:
            h.warm(20)
            h.press(InputAction.A)
            self.assertEqual(len(h.game.placed), 1)
            self.assertEqual(h.balance, 90 * MICRO)
            h.advance(25)
            self.assertEqual(len(h.game.settled), 1)
            settlement = h.game.settled[0]
            self.assertEqual(settlement.stake, 10 * MICRO)
            if settlement.hit:
                self.assertGreater(h.balance, 90 * MICRO)
            else:
                self.assertEqual(h.balance, 90 * MICRO)

    def test_a_bet_settles_at_the_bell_not_when_the_price_passes_through(self):
        # The price visits the band mid-round and leaves before the bell.
        rows = [(0.0, 2500.0)]
        rows += [(0.1 * i, 2500.0 + i * 0.02) for i in range(1, 400)]
        with Harness(Sitter(), feed=ScriptedFeed(rows), source='scripted', window_s=10.0) as h:
            h.warm(12)
            h.press(InputAction.A)
            self.assertTrue(h.game.placed, h.ctx.refused)
            band = h.game.placed[0]
            h.advance(32)
            done = [s for s in h.book.history if s.bet is band]
            self.assertTrue(done)
            self.assertEqual(done[0].hit, band.contains(done[0].price))


class TestRefusals(unittest.TestCase):
    def test_a_dead_flat_market_sells_nothing(self):
        with Harness(Sitter(), feed=FrozenFeed(2500.0), source='frozen') as h:
            h.advance(30)
            self.assertIsNone(h.ctx.bet(2499.0, 2501.0))
            self.assertIn('QUIET', h.ctx.refused)
            self.assertEqual(h.balance, 1000 * MICRO)

    def test_nothing_is_sold_before_the_feed_has_been_read(self):
        with Harness(Sitter()) as h:
            h.advance(0.2)
            self.assertIsNone(h.ctx.bet(2499.0, 2501.0))
            self.assertIn('READING', h.ctx.refused)

    def test_a_near_certain_bet_is_not_worth_selling(self):
        with Harness(Sitter()) as h:
            h.warm(25)
            # A band a mile wide is a certainty, and a certainty is not a bet.
            self.assertIsNone(h.ctx.bet(h.price * 0.5, h.price * 1.5))
            self.assertEqual(h.ctx.refused, 'TOO SURE TO SELL')

    def test_a_stale_feed_blocks_new_bets(self):
        rows = [(i * 0.05, 2500.0 + (i % 5) * 0.4) for i in range(400)]
        with Harness(Sitter(), feed=ScriptedFeed(rows), source='scripted') as h:
            h.warm(21)                 # the recording ran out at 20s
            h.advance(6)
            self.assertIsNone(h.ctx.bet(h.price - 1, h.price + 1))
            self.assertEqual(h.ctx.refused, 'FEED STALE')

    def test_a_win_past_what_the_escrow_can_pay_is_refused(self):
        from tick.money import DemoFunding

        class Capped(DemoFunding):
            cap = 120 * MICRO

        with Harness(Sitter(), balance=100 * MICRO, stake=10 * MICRO) as h:
            h.wallet.funding = Capped()
            h.warm(25)
            self.assertIsNone(h.ctx.bet(h.price - 0.01, h.price + 0.01))
            self.assertEqual(h.ctx.refused, 'MAX WIN REACHED / CASH OUT')

    def test_an_empty_wallet_refuses_before_anything_else_moves(self):
        with Harness(Sitter(), balance=5 * MICRO, stake=10 * MICRO) as h:
            h.warm(25)
            self.assertIsNone(h.ctx.bet(h.price - 1, h.price + 1))
            self.assertEqual(h.ctx.refused, 'NOT ENOUGH USDC')
            self.assertEqual(h.balance, 5 * MICRO)


class TestArming(unittest.TestCase):
    def test_presses_just_after_a_bell_are_swallowed(self):
        class Armed(Sitter):
            arm_s = 2.0

        with Harness(Armed()) as h:
            h.warm(25)
            index = h.rounds.index
            while h.rounds.index == index:      # roll to just after a bell
                h.frame()
            self.assertFalse(h.ctx.armed)
            self.assertIsNone(h.ctx.bet(h.price - 1, h.price + 1))
            self.assertEqual(h.ctx.refused, 'ARMING')
            h.advance(3)
            self.assertTrue(h.ctx.armed)


class TestOddsAreFair(unittest.TestCase):
    def test_over_many_rounds_a_fair_book_neither_prints_nor_burns_money(self):
        """The strongest claim this SDK makes, so it is the one that is tested.

        Stake a band on every round for a long simulated market and the balance
        should end near where it started -- not exactly, because variance is
        real, but the drift should be small against the money staked.
        """
        with Harness(Sitter(), balance=100_000 * MICRO, stake=10 * MICRO) as h:
            h.warm(25)
            for _ in range(300):
                h.press(InputAction.A)
                h.advance(10.5)
            settled = [s for s in h.book.history if not s.voided]
            self.assertGreater(len(settled), 200)
            staked = sum(s.stake for s in settled)
            paid = sum(s.payout for s in settled)
            drift = abs(paid - staked) / staked
            self.assertLess(drift, 0.35, f'staked {staked}, paid {paid}')

    def test_a_box_further_from_spot_always_pays_more(self):
        with Harness(Sitter()) as h:
            h.warm(25)
            half = h.price * 0.0002
            near = h.ctx.quote(h.price - half, h.price + half)
            far = h.ctx.quote(h.price + 4 * half, h.price + 6 * half)
            self.assertGreater(far, near)

    def test_buying_a_round_early_prices_more_drift(self):
        with Harness(Sitter()) as h:
            h.warm(25)
            half = h.price * 0.0002
            this_bell = h.ctx.quote(h.price - half, h.price + half, rounds_ahead=1)
            next_bell = h.ctx.quote(h.price - half, h.price + half, rounds_ahead=2)
            self.assertGreater(next_bell, this_bell)


class TestQuitting(unittest.TestCase):
    def test_quit_from_an_action_stops_the_loop(self):
        class Quitter(Sitter):
            def on_action(self, ctx, action):
                return 'quit'

        with Harness(Quitter()) as h:
            h.warm(2)
            h.press(InputAction.A)
            self.assertFalse(h.ctx.running)

    def test_the_quit_action_stops_the_loop_whatever_the_game_says(self):
        with Harness(Sitter()) as h:
            h.press(InputAction.QUIT)
            self.assertFalse(h.ctx.running)


if __name__ == '__main__':
    unittest.main()
