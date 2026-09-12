"""The clock: it rolls on its own, and it will not settle on the wrong price."""
import unittest

from tick.rounds import RoundClock


class TestClock(unittest.TestCase):
    def setUp(self):
        self.clock = RoundClock(window_s=10.0)
        self.clock.start(2500.0, 1000.0)

    def test_a_round_rolls_with_no_input(self):
        closed = self.clock.update(1010.5, 2501.0)
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].close_price, 2501.0)
        self.assertEqual(self.clock.index, 2)

    def test_the_next_round_opens_at_the_bell_not_at_the_frame(self):
        # The frame landed half a second late; the new round still opened on time.
        self.clock.update(1010.5, 2501.0)
        self.assertEqual(self.clock.opened_at, 1010.0)
        self.assertEqual(self.clock.ends_at, 1020.0)

    def test_a_long_stall_rolls_every_missed_round_at_once(self):
        closed = self.clock.update(1035.0, 2502.0)
        self.assertEqual(len(closed), 3)
        self.assertEqual(self.clock.index, 4)

    def test_without_a_bell_price_it_waits_rather_than_settling(self):
        closed = self.clock.update(1011.0, 2501.0, settleable=False)
        self.assertEqual(closed, [])
        self.assertTrue(self.clock.settling)
        self.assertEqual(self.clock.index, 1)

    def test_waiting_too_long_voids_rather_than_settling_late(self):
        self.clock.update(1011.0, 2501.0, settleable=False)
        closed = self.clock.update(1015.0, 2501.0, settleable=False)
        self.assertEqual(len(closed), 1)
        self.assertTrue(closed[0].voided)
        self.assertFalse(self.clock.settling)

    def test_a_late_price_settles_normally_inside_the_void_window(self):
        self.clock.update(1011.0, 2501.0, settleable=False)
        closed = self.clock.update(1012.0, 2503.0, settleable=True)
        self.assertEqual(len(closed), 1)
        self.assertFalse(closed[0].voided)
        self.assertEqual(closed[0].close_price, 2503.0)

    def test_horizon_grows_with_how_far_ahead_you_buy(self):
        self.assertAlmostEqual(self.clock.horizon(1002.0, 0), 8.0)
        self.assertAlmostEqual(self.clock.horizon(1002.0, 1), 18.0)

    def test_move_is_measured_against_the_open_not_against_spot(self):
        self.assertAlmostEqual(self.clock.move(2503.5), 3.5)
        self.clock.update(1010.0, 2510.0)
        self.assertAlmostEqual(self.clock.move(2510.0), 0.0)

    def test_a_zero_window_is_refused(self):
        with self.assertRaises(ValueError):
            RoundClock(0)


if __name__ == '__main__':
    unittest.main()
