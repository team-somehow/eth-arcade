import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest

from games.box_model import BoxModel, normal_cdf
from markets.feed import PriceTick
from wallet import MICRO, DemoFunding, Wallet

START = 100 * MICRO
T0 = 1000.0


def model(balance=START):
    return BoxModel(Wallet(balance, DemoFunding()))


def feed(m, prices, start=T0, step=.2):
    """Stream ticks in, as the game loop would, and return the last timestamp."""
    now = start
    for i, price in enumerate(prices):
        now = start + i * step
        m.on_tick(PriceTick(price, len(m.history) + 1, now), now)
    return now


def warm(m, price=2500.0, count=40, start=T0, step=.2):
    """Enough flat-ish ticks to measure volatility from."""
    prices = [price * (1 + (.0002 if i % 2 else -.0002)) for i in range(count)]
    return feed(m, prices, start, step)


class WindowClockTests(unittest.TestCase):
    def test_first_price_starts_the_clock_and_centres_the_aim(self):
        m = model()
        self.assertFalse(m.started)
        feed(m, [2500.0])
        self.assertTrue(m.started)
        self.assertEqual(m.aim, 2500.0)
        self.assertAlmostEqual(m.window_end, T0 + m.WINDOW_S)
        self.assertGreater(m.half, 0)

    def test_clock_rolls_on_its_own_with_no_bet_placed(self):
        m = model()
        now = warm(m)
        m.update(now + 2 * m.WINDOW_S + 1)
        self.assertGreater(m.window_end, now + 2 * m.WINDOW_S)
        self.assertEqual((m.rounds, m.wallet.balance), (0, START))

    def test_window_length_is_exactly_twenty_seconds(self):
        m = model()
        feed(m, [2500.0])
        first = m.window_end
        m.update(first + .001)
        self.assertAlmostEqual(m.window_end - first, m.WINDOW_S)

    def test_rolling_is_time_driven_not_frame_driven(self):
        slow, fast = model(), model()
        warm(slow), warm(fast)
        slow.update(T0 + 61)
        for i in range(1, 61 * 30):
            fast.update(T0 + i / 30)
        self.assertAlmostEqual(slow.window_end, fast.window_end)


class BuyingTests(unittest.TestCase):
    def setUp(self):
        self.m = model()
        self.now = warm(self.m)

    def test_a_buys_the_next_window_at_the_cursor(self):
        m = self.m
        m.crank(4)
        level = m.aim
        self.assertTrue(m.buy(self.now))
        self.assertEqual(m.pending.level, level)
        self.assertEqual(m.pending.stake, m.STAKE)
        self.assertEqual(m.wallet.balance, START - m.STAKE)
        # The bought box is for the NEXT window; this one is still unbet.
        self.assertIsNone(m.live)

    def test_more_presses_add_stake_to_the_same_box(self):
        m = self.m
        m.buy(self.now)
        level = m.pending.level
        m.crank(6)                      # cursor moves, the bought box does not
        m.buy(self.now)
        m.buy(self.now)
        self.assertEqual(m.pending.level, level)
        self.assertEqual(m.pending.stake, 3 * m.STAKE)
        self.assertEqual(m.wallet.balance, START - 3 * m.STAKE)

    def test_topping_up_is_priced_at_the_odds_of_that_press(self):
        m = self.m
        m.crank(8)                      # a long way out: cheap odds, big multiple
        m.buy(self.now)
        first = m.pending.multiple
        # Walk the price up to the box, so the same box is now likely to land.
        now = feed(m, [2500 + i for i in range(1, 12)], self.now + .2)
        m.buy(now)
        self.assertLess(m.pending.multiple, first)
        self.assertGreater(m.pending.multiple, 1.0)

    def test_cranking_never_moves_a_bought_box(self):
        m = self.m
        m.buy(self.now)
        level, half = m.pending.level, m.pending.half
        for _ in range(30):
            m.crank(1)
        for _ in range(60):
            m.crank(-1)
        self.assertEqual((m.pending.level, m.pending.half), (level, half))

    def test_a_stale_price_cannot_place_a_bet(self):
        m = self.m
        self.assertFalse(m.buy(self.now + m.STALE_AFTER + 1))
        self.assertEqual((m.pending, m.wallet.balance), (None, START))

    def test_an_empty_balance_cannot_place_a_bet(self):
        m = model(balance=5 * MICRO)
        now = warm(m)
        self.assertFalse(m.buy(now))
        self.assertFalse(m.can_buy())
        self.assertEqual(m.wallet.balance, 5 * MICRO)

    def test_buying_early_prices_a_longer_horizon(self):
        m = self.m
        m.crank(6)                                           # a far box
        early = m.quote(m.aim, self.now)                     # ~20s to the bell
        at_the_bell = m.quote(m.aim, m.window_end - .01)     # a moment before
        # More drift makes a far box likelier to be reached, so buying early
        # pays less. Neither quote may be sitting on the cap for this to mean
        # anything.
        self.assertLess(max(early, at_the_bell), m.MAX_MULTIPLE)
        self.assertLess(early, at_the_bell)

    def test_the_quote_prices_the_horizon_it_claims_to(self):
        m = self.m
        m.crank(3)
        for now in (self.now, self.now + 5, m.window_end - .01):
            horizon = m.remaining(now) + m.WINDOW_S
            chance = m.probability(m.aim, m.half, horizon)
            self.assertAlmostEqual(m.quote(m.aim, now), 1 / chance, places=6)


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.m = model()
        self.now = warm(self.m)

    def roll(self, m, price):
        """Take the clock past the bell with a price stamped after it."""
        expiry = m.window_end
        m.on_tick(PriceTick(price, len(m.history) + 1, expiry + .1), expiry + .1)
        m.update(expiry + .1)
        return expiry + .1

    def buy_live_window(self, m, now):
        """Buy, then roll once so the bought box is the one settling next."""
        m.buy(now)
        pending = m.pending
        now = self.roll(m, m.price)
        self.assertIs(m.live, pending)
        return now

    def test_price_inside_the_box_pays_the_locked_multiple(self):
        m = self.m
        now = self.buy_live_window(m, self.now)
        order = m.live
        expected = int(order.payout)
        balance = m.wallet.balance
        self.roll(m, order.level)          # land dead centre
        self.assertTrue(m.last.hit)
        self.assertEqual(m.wallet.balance, balance + expected)
        self.assertEqual(m.last.payout, expected)

    def test_price_outside_the_box_pays_nothing(self):
        m = self.m
        now = self.buy_live_window(m, self.now)
        order = m.live
        balance = m.wallet.balance
        self.roll(m, order.high + 10 * m.half)
        self.assertFalse(m.last.hit)
        self.assertEqual((m.last.payout, m.wallet.balance), (0, balance))

    def test_the_boundary_counts_as_inside(self):
        m = self.m
        self.buy_live_window(m, self.now)
        order = m.live
        self.roll(m, order.high)
        self.assertTrue(m.last.hit)

    def test_only_the_price_at_the_bell_matters(self):
        m = self.m
        now = self.buy_live_window(m, self.now)
        order = m.live
        # Sail straight through the box mid-window, then leave before the bell.
        now = feed(m, [order.level, order.level, order.high + 8 * m.half], now + .2)
        self.roll(m, order.high + 8 * m.half)
        self.assertFalse(m.last.hit)
        self.assertEqual(m.hits, 0)

    def test_a_quote_from_before_the_bell_cannot_settle_it(self):
        m = self.m
        self.buy_live_window(m, self.now)
        expiry = m.window_end
        # Last price arrived before the bell: hold, do not settle on it.
        m.update(expiry + 1)
        self.assertTrue(m.settling)
        self.assertEqual(m.rounds, 0)
        m.on_tick(PriceTick(m.live.level, len(m.history) + 1, expiry + 1.5), expiry + 1.5)
        self.assertFalse(m.settling)
        self.assertEqual(m.rounds, 1)
        self.assertTrue(m.last.hit)

    def test_a_long_feed_gap_voids_the_window_and_refunds(self):
        m = self.m
        self.buy_live_window(m, self.now)
        staked, balance = m.live.stake, m.wallet.balance
        m.update(m.window_end + m.VOID_AFTER + .1)
        self.assertTrue(m.last.voided)
        self.assertEqual(m.wallet.balance, balance + staked)
        self.assertEqual(m.last.net, 0)
        self.assertEqual(m.hits, 0)

    def test_the_pending_box_becomes_live_at_the_bell(self):
        m = self.m
        m.buy(self.now)
        pending = m.pending
        self.roll(m, m.price)
        self.assertIs(m.live, pending)
        self.assertIsNone(m.pending)

    def test_payouts_are_whole_micro_usdc(self):
        m = self.m
        now = self.now
        for _ in range(6):
            m.crank(3)
            m.buy(now)
            now = self.roll(m, m.price)
            now = self.roll(m, m.price + m.half * .5)
        self.assertEqual(m.wallet.balance, int(m.wallet.balance))
        self.assertGreaterEqual(m.wallet.balance, 0)
        self.assertGreater(m.rounds, 0)


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.m = model()
        self.now = warm(self.m)

    def test_a_box_on_spot_pays_least_and_distance_pays_more(self):
        m = self.m
        on_spot = m.quote(m.price, self.now)
        quotes = []
        for steps in (2, 4, 8, 12):
            m.aim = m.price + steps * m.STEP_SIGMA * m.window_sigma()
            quotes.append(m.quote(m.aim, self.now))
        self.assertGreater(on_spot, 1.0)
        self.assertLess(on_spot, 2.5)
        self.assertEqual(quotes, sorted(quotes))
        self.assertGreater(quotes[-1], on_spot)

    def test_the_multiple_is_capped(self):
        m = self.m
        absurd = m.price + 50 * m.window_sigma()
        self.assertLessEqual(m.quote(absurd, self.now), m.MAX_MULTIPLE)

    def test_odds_are_fair_against_the_stated_probability(self):
        m = self.m
        m.aim = m.price + 3 * m.STEP_SIGMA * m.window_sigma()
        horizon = m.remaining(self.now) + m.WINDOW_S
        chance = m.probability(m.aim, m.half, horizon)
        self.assertAlmostEqual(m.quote(m.aim, self.now), 1 / chance, places=6)
        self.assertEqual(m.HOUSE_EDGE, 0.0)

    def test_box_height_tracks_measured_volatility(self):
        calm, wild = model(), model()
        feed(calm, [2500.0 + (.05 if i % 2 else -.05) for i in range(60)])
        feed(wild, [2500.0 + (6.0 if i % 2 else -6.0) for i in range(60)])
        self.assertGreater(wild.half, calm.half * 3)
        # Same shape in sigma terms, so the game plays the same in both.
        self.assertAlmostEqual(calm.half / calm.window_sigma(),
                               wild.half / wild.window_sigma(), places=6)

    def test_volatility_falls_back_before_enough_ticks_arrive(self):
        m = model()
        feed(m, [2500.0, 2500.5])
        self.assertGreater(m.window_sigma(), 0)
        self.assertGreater(m.quote(m.price, T0), 1.0)

    def test_a_flat_feed_cannot_collapse_the_box_or_the_odds(self):
        m = model()
        feed(m, [2500.0] * 60)
        self.assertGreater(m.half, 0)
        self.assertLessEqual(m.quote(m.price, T0), m.MAX_MULTIPLE)

    def test_normal_cdf_matches_known_values(self):
        self.assertAlmostEqual(normal_cdf(0), .5, places=9)
        self.assertAlmostEqual(normal_cdf(1.959964), .975, places=6)
        self.assertAlmostEqual(normal_cdf(-1.959964), .025, places=6)


class AimTests(unittest.TestCase):
    def test_the_cursor_steps_in_sigma_and_stays_in_reach(self):
        m = model()
        now = warm(m)
        sigma = m.window_sigma()
        before = m.aim
        m.crank(1)
        self.assertAlmostEqual(m.aim - before, m.STEP_SIGMA * sigma, places=9)
        for _ in range(400):
            m.crank(1)
        self.assertLessEqual(m.aim - m.price, m.AIM_RANGE_SIGMA * sigma + 1e-9)
        for _ in range(800):
            m.crank(-1)
        self.assertGreaterEqual(m.aim - m.price, -m.AIM_RANGE_SIGMA * sigma - 1e-9)

    def test_no_cranking_before_the_first_price(self):
        m = model()
        m.crank(5)
        self.assertEqual(m.aim, 0.0)


class GameTests(unittest.TestCase):
    """The loop as played: clock always running, dial always live."""

    def setUp(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((480, 320))
        self.surface = pygame.Surface((480, 320))
        self.time = T0
        from games.box import BoxGame
        self.game = BoxGame(seed=7, sound=False, source='sim',
                            wallet=Wallet(START, DemoFunding()),
                            clock=lambda: self.time)
        self.addCleanup(self.game.close)
        self.frames(60)

    def frames(self, count):
        from games.box import handle_box_events
        for _ in range(count):
            self.time += 1/30
            self.game.update(1/30)
            handle_box_events(self.game, [], [])
            self.game.draw(self.surface)

    def test_a_window_settles_and_the_next_one_starts_by_itself(self):
        m = self.game.model
        self.game.buy()
        self.assertEqual(m.pending.stake, m.STAKE)
        self.frames(int(30 * m.WINDOW_S) + 15)       # past one bell
        self.assertIsNotNone(m.live)
        self.assertIsNone(m.pending)
        self.frames(int(30 * m.WINDOW_S) + 15)       # past the next
        self.assertEqual(m.rounds, 1)
        self.assertIsNotNone(m.last)

    def test_the_dial_is_live_while_a_bought_box_waits(self):
        m = self.game.model
        self.game.buy()
        level = m.pending.level
        self.game.crank(5)
        self.assertNotEqual(m.aim, level)
        self.assertEqual(m.pending.level, level)

    def test_pressing_a_with_no_money_opens_the_loader(self):
        from games.box import BoxGame
        game = BoxGame(seed=7, sound=False, source='sim',
                       wallet=Wallet(0, DemoFunding()), clock=lambda: self.time)
        self.addCleanup(game.close)
        for _ in range(60):
            self.time += 1/30
            game.update(1/30)
        game.buy()
        self.assertTrue(game.wallet_open)
        game.load_selected()
        self.assertEqual(game.model.wallet.balance, 25 * MICRO)

    def test_every_screen_renders(self):
        from screens.home import HomeScreen
        m = self.game.model
        HomeScreen('box').draw(self.surface)
        self.game.draw(self.surface)                 # placed nothing yet
        self.game.crank(4)
        self.game.buy()
        self.game.buy()
        self.game.draw(self.surface)                 # pending box + ghost aim
        self.frames(int(30 * m.WINDOW_S) + 15)
        self.game.draw(self.surface)                 # live box counting down
        self.frames(int(30 * m.WINDOW_S) + 15)
        self.game.draw(self.surface)                 # result flash
        self.game.open_wallet()
        self.game.draw(self.surface)                 # loader
        self.game.wallet_open = False
        m.tick = None
        m.started = False
        self.game.draw(self.surface)                 # waiting for first price

    def test_escape_quits_from_the_game(self):
        import pygame
        from app import App
        from input import InputAction, actions_from_event
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        self.assertEqual(actions_from_event(escape), [InputAction.QUIT])
        app = App(game_id='box')
        try:
            app._dispatch([], [InputAction.A])
            self.assertEqual(app.current, 'game')
            app._dispatch([escape], actions_from_event(escape))
            self.assertFalse(app.running)
        finally:
            app.game.close()


if __name__ == '__main__':
    unittest.main()
