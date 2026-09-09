import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest

from games.box_run_model import BoxRunModel


def started(seed=3):
    m = BoxRunModel(seed)
    for _ in range(3):
        m.confirm()
    return m


class RulesTests(unittest.TestCase):
    def test_three_confirmations_and_single_debit(self):
        m = BoxRunModel(4)
        m.confirm()
        m.confirm()
        self.assertEqual((m.phase, m.balance), ('review', 100))
        m.confirm()
        for _ in range(10):
            m.confirm()
        self.assertEqual((m.phase, m.balance), ('running', 90))

    def test_box_cannot_move_and_back_cannot_cancel(self):
        m = started()
        state = (m.center, m.half_width, m.locked_return)
        for _ in range(20):
            m.adjust(1)
            self.assertFalse(m.back())
        self.assertEqual(state, (m.center, m.half_width, m.locked_return))

    def test_same_outcome_across_frame_rates(self):
        slow, fast = started(11), started(11)
        slow.update(25)
        for _ in range(1200):
            fast.update(1/60)
        self.assertEqual(slow.path, fast.path)
        self.assertEqual(slow.balance, fast.balance)
        self.assertEqual(fast.phase, 'result')
        self.assertEqual(len(fast.path), 201)

    def test_settlement_once_at_expiry(self):
        m = started()
        m.update(19.9)
        self.assertEqual(m.phase, 'running')
        m.update(.1)
        balance = m.balance
        self.assertEqual(m.phase, 'result')
        for _ in range(100):
            m.update(20)
        self.assertEqual(m.balance, balance)
        self.assertEqual(m.rounds, 1)

    def test_bounds_and_quote_direction(self):
        m = BoxRunModel()
        broad = m.total_return
        m.phase = 'size'
        for _ in range(200):
            m.adjust(-1)
        self.assertEqual(m.half_width, 3)
        self.assertGreater(m.total_return, broad)
        m.phase = 'aim'
        for _ in range(200):
            m.adjust(1)
        self.assertEqual(m.center, 22)
        self.assertLessEqual(m.total_return, 100)

    def test_no_selected_outcomes_based_on_target(self):
        a, b = BoxRunModel(42), BoxRunModel(42)
        b.adjust(1)
        for _ in range(3):
            a.confirm()
            b.confirm()
        a.update(20)
        b.update(20)
        self.assertEqual(a.path, b.path)

    def test_hit_and_miss_accounting(self):
        for outcome in ('hit', 'miss'):
            m = started()
            class Source:
                def gauss(self, _mean, _sigma):
                    return 0 if outcome == 'hit' else 1
            m.rng = Source()
            quoted = m.locked_return
            m.update(20)
            self.assertEqual(m.hit, outcome == 'hit')
            self.assertEqual(m.balance, 90 + (quoted if m.hit else 0))
            self.assertEqual(m.net, (quoted if m.hit else 0)-10)

    def test_boundary_is_inside(self):
        m = started()
        m.path = [m.locked_width] * 201
        m.update(20)
        self.assertTrue(m.hit)

    def test_explicit_refill(self):
        m = BoxRunModel()
        m.balance = 0
        m.reset_prediction()
        self.assertEqual(m.phase, 'empty')
        m.update(100)
        self.assertEqual(m.balance, 0)
        m.confirm()
        self.assertEqual((m.balance, m.phase), (100, 'aim'))


class InputAndRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()
        pygame.display.set_mode((480, 320))

    def test_arrows_complete_round_and_return(self):
        import pygame
        from input import actions_from_event
        from games.box_run import BoxRunGame
        g = BoxRunGame(seed=4, sound=False)
        for key in [pygame.K_UP, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_RIGHT, pygame.K_RIGHT]:
            for action in actions_from_event(pygame.event.Event(pygame.KEYDOWN, key=key)):
                g.handle_action(action)
        self.assertEqual(g.model.phase, 'running')
        g.update(20)
        g.update(.6)
        from input import InputAction
        self.assertEqual(g.handle_action(InputAction.B), 'home')
        self.assertEqual(g.model.rounds, 1)

    def test_render_every_state(self):
        import pygame
        from games.box_run import BoxRunGame
        g = BoxRunGame(sound=False)
        screen = pygame.Surface((480,320))
        for state in ['aim','size','review','running','result','empty']:
            g.model.phase = state
            g.draw(screen)
            self.assertNotEqual(screen.get_at((0,0)), (0,0,0,255))

    def test_touch_duplicate_is_ignored(self):
        import pygame
        from input import event_position
        self.assertIsNone(event_position(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(300,300), button=1, touch=True)))

    def test_launcher_dispatch(self):
        from app import App
        from input import InputAction
        app = App(game_id='box_run')
        app._dispatch([], [InputAction.A])
        self.assertEqual(app.current, 'game')
        app._draw()
        app._dispatch([], [InputAction.B])
        self.assertEqual(app.current, 'home')
        app._draw()
        if app.encoder:
            app.encoder.close()


if __name__ == '__main__':
    unittest.main()
