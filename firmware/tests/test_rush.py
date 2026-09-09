import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import math
import unittest

from games.rush_model import RushModel
from markets.feed import PriceTick, SimulatedFeed, parse_coinbase
from wallet import MICRO, DemoFunding, UsdcFunding, Wallet, format_usdc, to_micro

START = 100 * MICRO


def model(balance=START, price=2000.0, at=100.0):
    m = RushModel(Wallet(balance, DemoFunding()))
    if price:
        quote(m, price, at)
    return m


def quote(m, price, now, sequence=None):
    """Deliver one feed tick, as the game loop would."""
    m.on_tick(PriceTick(price, sequence if sequence is not None else len(m.history)+1, now), now)


def ride(m, now=100.0):
    """Open a position the only way the game can: by cranking."""
    for _ in range(RushModel.ARM_STEPS):
        m.crank(1, now)
    return m


class ArmingTests(unittest.TestCase):
    def test_one_detent_does_not_stake(self):
        m = model()
        self.assertFalse(m.crank(1, 100.0))
        self.assertEqual((m.phase, m.wallet.balance), ('ready', START))
        self.assertTrue(m.crank(1, 100.05))
        self.assertEqual((m.phase, m.wallet.balance), ('riding', START - m.STAKE))

    def test_no_button_press_is_needed_or_available(self):
        m = ride(model())
        self.assertEqual(m.phase, 'riding')
        # The model exposes no confirm/next step at all.
        for name in ('confirm', 'next', 'start'):
            self.assertFalse(hasattr(m, name))

    def test_reversal_picks_the_other_side_without_staking(self):
        m = model()
        m.crank(1, 100.0)
        m.crank(-1, 100.1)
        self.assertEqual((m.phase, m.side, m.arm), ('ready', -1, 1))
        m.crank(-1, 100.2)
        self.assertEqual((m.phase, m.side), ('riding', -1))
        self.assertLess(m.units, 0)

    def test_charge_expires_so_a_slow_nudge_never_rides(self):
        m = model()
        for i in range(6):
            self.assertFalse(m.crank(1, 100.0 + i * (m.ARM_WINDOW + .1)))
        self.assertEqual(m.wallet.balance, START)

    def test_empty_balance_cannot_open(self):
        m = ride(model(balance=5 * MICRO))
        self.assertEqual((m.phase, m.wallet.balance), ('ready', 5 * MICRO))
        self.assertFalse(m.can_ride())

    def test_stale_price_cannot_open_but_keeps_the_charge(self):
        m = model(price=2000.0, at=100.0)
        late = 100.0 + m.STALE_AFTER + 1
        ride(m, now=late)
        self.assertEqual((m.phase, m.wallet.balance), ('ready', START))
        self.assertEqual(m.arm, m.ARM_STEPS)
        # A hand that is still turning opens on the first fresh quote.
        quote(m, 2000.0, late + .1)
        self.assertTrue(m.crank(1, late + .2))


class LeverageTests(unittest.TestCase):
    def test_ride_opens_at_1x_and_cranking_raises_leverage(self):
        m = ride(model())
        self.assertEqual(m.leverage, 1.0)
        for i in range(12):
            m.crank(1, 100.0 + i * .01)
        quote(m, 2000.0, 100.2)
        self.assertGreater(m.leverage, 2.0)
        self.assertLessEqual(m.leverage, m.MAX_LEVERAGE)

    def test_leverage_is_capped(self):
        m = ride(model())
        for i in range(300):
            m.crank(1, 100.0 + i * .01)
        quote(m, 2000.0, 104.0)
        self.assertEqual(m.throttle, 1.0)
        self.assertAlmostEqual(m.leverage, m.MAX_LEVERAGE)

    def test_cranking_never_multiplies_a_gain_already_made(self):
        m = ride(model())
        quote(m, 2020.0, 100.2)          # +1% at 1x
        earned = m.pnl
        self.assertAlmostEqual(earned, 10 * .01, places=6)
        for i in range(20):              # redline the flywheel
            m.crank(1, 100.3 + i * .01)
        quote(m, 2020.0, 100.6)          # price unchanged
        self.assertAlmostEqual(m.pnl, earned, places=9)
        self.assertGreater(m.leverage, 2.0)

    def test_short_side_profits_when_price_falls(self):
        m = model()
        m.crank(-1, 100.0)
        m.crank(-1, 100.1)
        quote(m, 1900.0, 100.2)
        self.assertGreater(m.pnl, 0)

    def test_liquidation_stops_at_the_stake(self):
        m = ride(model())
        for i in range(20):
            m.crank(1, 100.0 + i * .01)
        quote(m, 2000.0, 100.3)
        quote(m, 400.0, 100.4)
        self.assertEqual((m.phase, m.last_reason), ('ready', 'Liquidated'))
        self.assertAlmostEqual(m.last_pnl, -10.0)
        self.assertEqual(m.wallet.balance, START - m.STAKE)


class SettlementTests(unittest.TestCase):
    def test_flat_market_returns_the_exact_stake(self):
        m = ride(model())
        for i in range(30):
            m.crank(1, 100.0 + i * .01)
            quote(m, 2000.0, 100.0 + i * .01)
        m.bail(101.0)
        self.assertEqual((m.phase, m.wallet.balance), ('ready', START))

    def test_stopping_the_crank_closes_the_ride(self):
        m = ride(model())
        quote(m, 2000.0, 100.1)
        m.update(1/30, 100.2)
        self.assertEqual(m.phase, 'riding')
        m.update(1/30, 100.1 + m.COAST_S)
        self.assertEqual((m.phase, m.last_reason), ('ready', 'Crank stopped'))

    def test_cranking_through_a_result_opens_the_next_ride(self):
        m = ride(model())
        m.bail(100.5)
        self.assertEqual(m.phase, 'ready')
        self.assertEqual(m.rides, 1)
        ride(m, now=100.6)
        self.assertEqual((m.phase, m.rides), ('riding', 1))

    def test_stale_exit_waits_for_a_real_price(self):
        m = ride(model())
        late = 100.0 + m.STALE_AFTER + 1
        m.bail(late)
        self.assertEqual(m.phase, 'exit_pending')
        self.assertEqual(m.wallet.balance, START - m.STAKE)
        quote(m, 2200.0, late)
        # Settled on the fresh quote, not on the stale one it was holding.
        self.assertEqual(m.phase, 'ready')
        self.assertAlmostEqual(m.last_pnl, 10 * (2200/2000 - 1), places=6)

    def test_feed_interruption_closes_the_ride(self):
        m = ride(model())
        m.update(1/30, 100.0 + m.STALE_AFTER + 1)
        self.assertEqual((m.phase, m.last_reason), ('exit_pending', 'Feed interrupted'))

    def test_settlement_never_invents_money(self):
        m = model()
        walk = [2000.0 * math.exp(math.sin(i) * .004) for i in range(200)]
        for i, price in enumerate(walk):
            now = 100.0 + i * .05
            m.crank(1, now)
            quote(m, price, now)
            m.update(.05, now)
        if m.active:
            m.bail(100.0 + len(walk) * .05)
        # Winning rides pay from price moves only; the balance stays a whole
        # number of micro-USDC and cannot exceed stake plus realised PnL.
        self.assertEqual(m.wallet.balance, int(m.wallet.balance))
        self.assertGreater(m.rides, 0)
        self.assertLessEqual(m.wallet.balance, START + to_micro(max(0.0, m.last_pnl or 0) * m.rides))

    def test_frame_rate_does_not_change_the_flywheel(self):
        slow, fast = ride(model()), ride(model())
        slow.update(1.0, 101.0)
        for i in range(60):
            fast.update(1/60, 100.0 + (i+1)/60)
        self.assertAlmostEqual(slow.throttle, fast.throttle, places=6)


class WalletTests(unittest.TestCase):
    def test_loads_credit_only_confirmed_deposits(self):
        wallet = Wallet(0, DemoFunding())
        deposit = wallet.load(25)
        self.assertEqual((deposit.status, wallet.balance), ('confirmed', 25 * MICRO))
        live = Wallet(0, UsdcFunding())
        pending = live.load(10)
        self.assertEqual((pending.status, live.balance), ('failed', 0))
        self.assertEqual(len(live.deposits), 1)

    def test_unsupported_amounts_are_rejected(self):
        wallet = Wallet(0, DemoFunding())
        with self.assertRaises(ValueError):
            wallet.load(7)
        self.assertEqual(wallet.balance, 0)

    def test_debit_cannot_overdraw_and_money_is_integral(self):
        wallet = Wallet(10 * MICRO, DemoFunding())
        self.assertFalse(wallet.debit(10 * MICRO + 1))
        self.assertFalse(wallet.debit(0))
        self.assertTrue(wallet.debit(10 * MICRO))
        self.assertEqual((wallet.balance, format_usdc(0)), (0, '0.00'))
        self.assertEqual(to_micro(1.999999), 1999999)


class FeedTests(unittest.TestCase):
    def test_simulated_feed_is_deterministic_and_rate_independent(self):
        slow = [t.price for t in SimulatedFeed(9).poll(1.0, 100.0)]
        fast = []
        feed = SimulatedFeed(9)
        for i in range(20):
            fast.extend(t.price for t in feed.poll(.05, 100.0 + i * .05))
        self.assertEqual(slow, fast)

    def test_out_of_order_and_bad_ticks_are_ignored(self):
        m = model(price=2000.0, at=100.0)
        ride(m)
        for bad in (PriceTick(0, 99, 100.0), PriceTick(float('nan'), 99, 100.0),
                    PriceTick(2500.0, 1, 100.0), PriceTick(2500.0, 99, 100.0, -1)):
            m.on_tick(bad, 100.0)
        self.assertEqual((m.tick.price, m.pnl), (2000.0, 0.0))

    def test_live_payload_parsing_rejects_junk(self):
        good = {'price': '2500.10', 'trade_id': 7, 'time': '2026-01-01T00:00:00Z'}
        tick = parse_coinbase(good, 100.0, 1767225600.0)
        self.assertEqual((tick.price, tick.sequence), (2500.10, 7))
        for payload in ({**good, 'price': '-1'},
                        {**good, 'time': '2026-01-01T00:00:00'},
                        {**good, 'time': '2099-01-01T00:00:00Z'}):
            with self.assertRaises(ValueError):
                parse_coinbase(payload, 100.0, 1767225600.0)


class FakeEncoder:
    def __init__(self):
        self.steps = 0


class FakeButton:
    is_pressed = False


class EncoderTests(unittest.TestCase):
    def test_continuous_mode_reports_only_current_motion(self):
        from encoder import EncoderInput
        from input import InputAction
        encoder, button = FakeEncoder(), FakeButton()
        reader = EncoderInput(encoder, button)
        encoder.steps = 5
        actions = reader.poll(continuous=True)
        self.assertEqual(actions, [InputAction.UP] * 5)
        # Hand stopped: nothing queued from the spin that just happened.
        self.assertEqual(reader.poll(continuous=True), [])
        encoder.steps = 2
        self.assertEqual(reader.poll(continuous=True), [InputAction.DOWN] * 3)

    def test_menu_mode_rate_limits_a_whip_spin(self):
        from encoder import EncoderInput
        encoder, button = FakeEncoder(), FakeButton()
        reader = EncoderInput(encoder, button)
        encoder.steps = 40
        self.assertEqual(len(reader.poll()), 1)


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()
        pygame.display.set_mode((480, 320))
        cls.surface = pygame.Surface((480, 320))

    def game(self):
        from games.rush import RushGame
        return RushGame(seed=5, sound=False, source='sim',
                        wallet=Wallet(START, DemoFunding()))

    def test_every_state_renders(self):
        from screens.home import HomeScreen
        game = self.game()
        try:
            HomeScreen().draw(self.surface)
            game.draw(self.surface)                      # connecting
            for _ in range(60):
                game.update(1/30)
            game.draw(self.surface)                      # ready
            game.crank(1)
            game.draw(self.surface)                      # arming
            game.crank(1)
            for _ in range(30):
                game.crank(1)
                game.update(1/30)
            game.draw(self.surface)                      # riding
            game.model.tick = game.model.tick.__class__(
                game.model.tick.price, game.model.tick.sequence, game.clock - 60)
            game.draw(self.surface)                      # stale overlay
            game.open_wallet()
            game.draw(self.surface)                      # wallet closed to a ride
            game.model.bail(game.clock, 'Bailed out')
            game.open_wallet()
            game.draw(self.surface)                      # wallet
        finally:
            game.close()

    def test_launcher_routes_to_the_game_and_the_loader(self):
        from app import App
        from input import InputAction
        app = App()
        try:
            app._dispatch([], [InputAction.A])
            self.assertEqual(app.current, 'game')
            app._draw()
            app._dispatch([], [InputAction.B])
            self.assertEqual(app.current, 'home')
            app._dispatch([], [InputAction.DOWN])
            app._dispatch([], [InputAction.A])
            self.assertTrue(app.game.wallet_open)
        finally:
            app.game.close()

    def test_touch_on_the_plot_cranks(self):
        game = self.game()
        try:
            for _ in range(60):
                game.update(1/30)
            game.handle_touch((240, 150))
            game.handle_touch((240, 150))
            self.assertEqual(game.model.phase, 'riding')
            self.assertEqual(game.model.side, 1)
        finally:
            game.close()


class GameLoopTests(unittest.TestCase):
    """The whole point of RUSH: one uninterrupted crank, no confirmations."""

    def setUp(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((480, 320))
        self.surface = pygame.Surface((480, 320))
        self.time = 1000.0
        from games.rush import RushGame
        self.game = RushGame(seed=3, sound=False, source='sim',
                             wallet=Wallet(START, DemoFunding()),
                             clock=lambda: self.time)
        self.addCleanup(self.game.close)
        self.frames(30)

    def frames(self, count):
        from games.rush import handle_rush_events
        for _ in range(count):
            self.time += 1/30
            self.game.update(1/30)
            handle_rush_events(self.game, [], [])
            self.game.draw(self.surface)

    def key(self, kind, code):
        import pygame
        from games.rush import handle_rush_events
        handle_rush_events(self.game, [pygame.event.Event(kind, key=code)], [])

    def test_one_uninterrupted_crank_runs_a_whole_ride(self):
        import pygame
        m = self.game.model
        self.key(pygame.KEYDOWN, pygame.K_UP)
        self.frames(45)
        self.assertEqual(m.phase, 'riding')
        self.assertGreater(m.leverage, 5.0)
        self.assertEqual(m.wallet.balance, START - m.STAKE)

        self.key(pygame.KEYUP, pygame.K_UP)
        self.frames(int(30 * (m.COAST_S + .5)))
        self.assertEqual((m.phase, m.last_reason, m.rides), ('ready', 'Crank stopped', 1))
        self.assertGreater(m.wallet.balance, 0)

        # Straight back in on the other side without touching a button.
        self.key(pygame.KEYDOWN, pygame.K_DOWN)
        self.frames(10)
        self.assertEqual((m.phase, m.side, m.rides), ('riding', -1, 1))


if __name__ == '__main__':
    unittest.main()
