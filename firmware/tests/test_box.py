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


# Alternating this far each tick gives a 20-second sigma of about 0.04% —
# roughly live ETH, and the scale the fixed box size is chosen against.
WARM_SWING = .0000135


def warm(m, price=2500.0, count=40, start=T0, step=.2):
    """Enough ticks at ETH-like volatility to measure from."""
    prices = [price * (1 + (WARM_SWING if i % 2 else -WARM_SWING)) for i in range(count)]
    return feed(m, prices, start, step)


class WindowClockTests(unittest.TestCase):
    def test_first_price_starts_the_clock_and_centres_the_aim(self):
        m = model()
        self.assertFalse(m.started)
        feed(m, [2500.0])
        self.assertTrue(m.started)
        self.assertEqual((m.aim, m.window_open), (2500.0, 2500.0))
        self.assertAlmostEqual(m.window_end, T0 + m.WINDOW_S)
        self.assertGreater(m.half, 0)

    def test_clock_rolls_on_its_own_with_no_bet_placed(self):
        m = model()
        now = warm(m)
        m.update(now + 2 * m.WINDOW_S + 1)
        self.assertGreater(m.window_end, now + 2 * m.WINDOW_S)
        self.assertEqual((m.rounds, m.wallet.balance), (0, START))

    def test_windows_are_ten_seconds_long(self):
        m = model()
        feed(m, [2500.0])
        first = m.window_end
        m.update(first + .001)
        self.assertEqual(m.WINDOW_S, 10.0)
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
        # Walk the price gently up toward the box, so its odds have changed by
        # the time the second press lands.
        now = feed(m, [m.window_open + .2 * i for i in range(1, 11)], self.now + .2)
        second = m.quote(m.pending.level, now)
        m.buy(now)
        self.assertNotAlmostEqual(second, first, places=2)
        # The box carries a blend of what each press was actually worth, not
        # the first press's multiple applied to all the money.
        self.assertAlmostEqual(m.pending.multiple, (first + second) / 2, places=6)

    def test_the_dial_is_locked_out_once_the_box_is_bought(self):
        m = self.m
        m.buy(self.now)
        level, half, aim = m.pending.level, m.pending.half, m.aim
        self.assertTrue(m.locked)
        for _ in range(30):
            self.assertFalse(m.crank(1))
        for _ in range(60):
            self.assertFalse(m.crank(-1))
        # Nothing moves: not the bought box, and not a cursor either.
        self.assertEqual((m.pending.level, m.pending.half), (level, half))
        self.assertEqual(m.aim, aim)

    def test_money_can_still_be_added_while_the_dial_is_locked(self):
        m = self.m
        m.buy(self.now)
        m.crank(10)
        self.assertTrue(m.buy(self.now))
        self.assertEqual(m.pending.stake, 2 * m.STAKE)

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

    def test_payout_is_micro_usdc_like_the_stake(self):
        m = self.m
        m.buy(self.now)
        order = m.pending
        self.assertGreater(order.payout, order.stake)
        self.assertAlmostEqual(order.payout / MICRO,
                               (order.stake / MICRO) * order.multiple, places=6)

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
            m.aim = m.window_open + steps * m.step
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
        m.aim = m.window_open + 3 * m.step
        horizon = m.remaining(self.now) + m.WINDOW_S
        chance = m.probability(m.aim, m.half, horizon)
        self.assertAlmostEqual(m.quote(m.aim, self.now), 1 / chance, places=6)
        self.assertEqual(m.HOUSE_EDGE, 0.0)

    def test_box_size_is_constant_whatever_the_market_does(self):
        calm, wild = model(), model()
        feed(calm, [2500.0 + (.05 if i % 2 else -.05) for i in range(60)])
        feed(wild, [2500.0 + (6.0 if i % 2 else -6.0) for i in range(60)])
        self.assertGreater(wild.window_sigma(), calm.window_sigma() * 3)
        # Volatility moves the odds, never the geometry: the box is a fixed
        # slice of the price, so it is identical in both markets.
        for m in (calm, wild):
            self.assertAlmostEqual(2 * m.half / m.window_open,
                                   m.BOX_BPS / 10_000 * m.SCALE, places=12)
            self.assertAlmostEqual(m.view_half / m.window_open,
                                   m.VIEW_BPS / 10_000 * m.SCALE, places=12)
        self.assertAlmostEqual(2 * calm.half, 1.41, places=2)
        self.assertGreater(wild.quote(wild.price, T0), calm.quote(calm.price, T0))

    def test_a_placed_box_is_never_redrawn_at_another_size(self):
        m = model()
        now = warm(m)
        m.buy(now)
        order, placed = m.pending, m.pending.half
        # A violent burst must not resize a bet already down, and the bell
        # carrying it from pending to live must not either.
        feed(m, [2500.0 + (8.0 if i % 2 else -8.0) for i in range(40)], now + .2)
        self.assertIs(m.live, order)
        self.assertEqual(order.half, placed)

    def test_the_fixture_is_roughly_live_eth_volatility(self):
        m = model()
        warm(m)
        # About 0.03% over ten seconds, or 70c on $2,500.
        self.assertLess(.4, m.window_sigma())
        self.assertLess(m.window_sigma(), 1.4)

    def test_shrinking_the_window_keeps_the_same_ladder_of_odds(self):
        """A shorter window with a square-root-scaled box prices the same."""
        m = model()
        warm(m)
        on_spot = m.quote(m.window_open, m.window_end - m.WINDOW_S)
        far = m.quote(m.window_open + m.reach, m.window_end - m.WINDOW_S)
        # The ladder the 20-second build had: about 2x on spot, double digits
        # at full reach, and not pinned to the cap at either end.
        self.assertLess(1.5, on_spot)
        self.assertLess(on_spot, 2.6)
        self.assertGreater(far, 5.0)
        self.assertLess(far, m.MAX_MULTIPLE)

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
    def test_the_cursor_steps_a_constant_amount_and_stays_in_reach(self):
        m = model()
        warm(m)
        before = m.aim
        m.crank(1)
        self.assertAlmostEqual(m.aim - before, m.step, places=9)
        self.assertAlmostEqual(m.step, m.window_open * m.STEP_BPS / 10_000 * m.SCALE, places=9)
        # Reach is measured from the window's open, so the cursor can never be
        # cranked outside the drawn price band.
        for _ in range(400):
            m.crank(1)
        self.assertAlmostEqual(m.aim - m.window_open, m.reach, places=9)
        for _ in range(800):
            m.crank(-1)
        self.assertAlmostEqual(m.aim - m.window_open, -m.reach, places=9)

    def test_the_cursor_can_never_be_cranked_out_of_view(self):
        m = model()
        warm(m)
        for _ in range(400):
            m.crank(1)
        self.assertLessEqual(m.aim + m.half, m.window_open + m.view_half + 1e-9)

    def test_no_cranking_before_the_first_price(self):
        m = model()
        m.crank(5)
        self.assertEqual(m.aim, 0.0)


class MovementTests(unittest.TestCase):
    """Movement has to be readable, which means a reference that holds still."""

    def test_each_window_records_the_price_it_opened_at(self):
        m = model()
        warm(m)
        opened = m.window_open
        expiry = m.window_end
        feed(m, [2500.0 + i for i in range(1, 6)], expiry - 1, .1)
        self.assertEqual(m.window_open, opened)
        self.assertAlmostEqual(m.move, m.price - opened)
        # The bell starts a new reference at the price it opened on.
        m.on_tick(PriceTick(2530.0, len(m.history) + 1, expiry + .1), expiry + .1)
        self.assertEqual(m.window_open, 2530.0)
        self.assertEqual(m.move, 0.0)

    def test_the_move_readout_tracks_the_price(self):
        m = model()
        warm(m)
        base = m.window_open
        feed(m, [base + 3], T0 + 9, .1)
        self.assertAlmostEqual(m.move, 3.0, places=6)
        feed(m, [base - 2], T0 + 9.5, .1)
        self.assertAlmostEqual(m.move, -2.0, places=6)

    def test_no_move_before_the_first_price(self):
        self.assertEqual(model().move, 0.0)

class Ears:
    """Stand-in for Sounds that records what the game asked to play."""

    DETENTS = 8

    def __init__(self):
        self.played = []

    def detent(self, fraction):
        index = int(min(1.0, max(0.0, fraction)) * (self.DETENTS - 1) + .5)
        return f'detent{index}'

    def play(self, name):
        self.played.append(name)


class ScriptedFeed:
    """A feed whose prices the test chooses, polled exactly as the real one is."""

    name = 'SCRIPTED'

    def __init__(self, price, start_sequence=10_000):
        self.price = price
        self.queue = []
        self.sequence = start_sequence

    def poll(self, _dt, now):
        # Holds the last price and keeps ticking, like a live feed. A silent
        # feed would just go stale and block every bet.
        if self.queue:
            self.price = self.queue.pop(0)
        self.sequence += 1
        return [PriceTick(self.price, self.sequence, now)]

    def close(self):
        pass


class SoundTests(unittest.TestCase):
    """The sounds carry the tension, so the cues have to land on the right beat."""

    def setUp(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((480, 320))
        self.surface = pygame.Surface((480, 320))
        self.time = T0
        from games.box import BoxGame
        self.game = BoxGame(seed=3, sound=False, source='sim',
                            wallet=Wallet(START, DemoFunding()),
                            clock=lambda: self.time)
        self.addCleanup(self.game.close)
        self.ears = Ears()
        self.frames(45)                     # warm the real sim feed
        self.game.sounds = self.ears
        self.feed = ScriptedFeed(self.game.model.price)
        self.game.feed = self.feed          # from here the test sets the price

    def frames(self, count):
        for _ in range(count):
            self.time += 1/30
            self.game.update(1/30)

    def quote(self, price):
        """Put the price exactly where we want it, through the game's own loop."""
        self.feed.queue.append(price)
        self.time += 1/30
        self.game.update(1/30)

    def turn(self, count, steps=1):
        for _ in range(count):
            self.time += .06
            self.game.update(1/30)          # a frame passes, as in play
            self.game.crank(steps)

    def test_cranking_out_to_the_risky_end_rises_in_pitch(self):
        self.turn(2)
        near = [n for n in self.ears.played if n.startswith('detent')]
        self.turn(20)
        far = [n for n in self.ears.played if n.startswith('detent')]
        self.assertTrue(near)
        # Further from spot is a higher detent index.
        self.assertGreater(int(far[-1][-1]), int(near[-1][-1]))

    def test_stacked_presses_answer_a_note_higher(self):
        for _ in range(4):
            self.game.buy()
        buys = [n for n in self.ears.played if n.startswith('buy')]
        self.assertEqual(buys[:3], ['buy1', 'buy2', 'buy3'])
        # A fourth press stays at the top note rather than inventing 'buy4'.
        self.assertEqual(buys[3], 'buy3')

    def test_the_price_crossing_the_box_sounds_in_both_directions(self):
        m = self.game.model
        self.game.buy()
        self.frames(int(30 * m.WINDOW_S) + 6)      # the bet goes live
        self.assertIsNotNone(m.live)
        self.quote(m.live.high + m.half)            # start from a known side
        self.ears.played.clear()
        self.quote(m.live.level)                    # in
        self.quote(m.live.level + m.half * .5)      # still in: no repeat
        self.assertEqual(self.ears.played, ['hot'])
        self.quote(m.live.high + m.half)            # out
        self.assertEqual(self.ears.played, ['hot', 'cold'])
        self.quote(m.live.level)                    # back in
        self.assertEqual(self.ears.played, ['hot', 'cold', 'hot'])

    def test_the_final_ticks_say_whether_you_are_winning(self):
        m = self.game.model
        self.game.buy()
        self.frames(int(30 * m.WINDOW_S) + 6)
        # Park the price inside and run into the last seconds.
        self.quote(m.live.level)
        self.ears.played.clear()
        self.time = m.window_end - 2.5
        self.quote(m.live.level)
        self.assertIn('tick_in', self.ears.played)
        self.assertNotIn('tick_out', self.ears.played)
        # Same moment, price outside: a lower, unhappier tick.
        self.ears.played.clear()
        self.time = m.window_end - 1.5
        self.quote(m.live.high + m.half)
        self.assertIn('tick_out', self.ears.played)

    def test_the_ticks_double_in_rate_for_the_last_two_seconds(self):
        m = self.game.model
        self.game.buy()
        self.frames(int(30 * m.WINDOW_S) + 6)
        self.quote(m.live.level)
        self.ears.played.clear()
        # Walk the clock through the final three seconds a frame at a time.
        while m.remaining(self.time) > .05 and m.rounds == 0:
            self.quote(m.live.level)
        ticks = [n for n in self.ears.played if n.startswith('tick')]
        # One a second down to 2s, then one every half second: six in all.
        self.assertGreaterEqual(len(ticks), 5)
        self.assertLessEqual(len(ticks), 7)

    def test_a_bell_rings_on_an_empty_window_and_a_result_speaks_instead(self):
        m = self.game.model
        self.ears.played.clear()
        self.frames(int(30 * m.WINDOW_S) + 6)       # no money down
        self.assertIn('bell', self.ears.played)
        self.game.buy()
        self.frames(int(30 * m.WINDOW_S) + 6)       # bet goes live
        self.ears.played.clear()
        self.frames(int(30 * m.WINDOW_S) + 6)       # and settles
        self.assertEqual(m.rounds, 1)
        outcome = {'win_big', 'win_small', 'miss', 'void'} & set(self.ears.played)
        self.assertTrue(outcome, self.ears.played)
        self.assertNotIn('bell', self.ears.played)

    def test_a_big_multiple_wins_a_bigger_fanfare(self):
        m = self.game.model
        self.turn(10)                               # far out: a long-odds box
        self.game.buy()
        self.assertGreater(m.pending.multiple, 5)
        self.frames(int(30 * m.WINDOW_S) + 6)
        level = m.live.level
        self.ears.played.clear()
        self.time = m.window_end + .05
        self.quote(level)                           # land it
        self.assertTrue(m.last.hit)
        self.assertIn('win_big', self.ears.played)

    def test_no_audio_device_is_not_a_crash(self):
        from games.box import BoxGame
        game = BoxGame(seed=1, sound=False, source='sim',
                       wallet=Wallet(START, DemoFunding()), clock=lambda: self.time)
        self.addCleanup(game.close)
        self.assertIsNone(game.sounds)
        for _ in range(60):
            self.time += 1/30
            game.update(1/30)
        game.crank(3)                               # detent pitch needs sounds
        game.buy()
        game.draw(self.surface)

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

    def test_the_dial_does_nothing_while_a_bought_box_waits(self):
        m = self.game.model
        self.game.buy()
        aim, level = m.aim, m.pending.level
        self.game.crank(5)
        self.assertEqual(m.aim, aim)
        self.assertEqual(m.pending.level, level)
        self.assertIn('LOCKED', self.game.message)

    def test_a_live_bet_quotes_the_money_it_will_pay(self):
        m = self.game.model
        self.game.buy()
        self.frames(int(30 * m.WINDOW_S) + 15)
        text, _ = self.game.status()
        self.assertIn('10 IN / PAYS', text)
        # The payout is real money, not a unit slip that renders as zero.
        paid = float(text.split('PAYS')[1].strip().replace(',', ''))
        self.assertGreater(paid, 10)
        self.assertAlmostEqual(paid, m.live.payout / MICRO, places=2)

    def test_the_dial_frees_up_again_when_the_window_rolls(self):
        m = self.game.model
        self.game.buy()
        self.frames(int(30 * m.WINDOW_S) + 15)
        self.assertFalse(m.locked)
        self.assertTrue(m.crank(3))

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
