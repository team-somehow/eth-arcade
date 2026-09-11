import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest

from buttons import RED_PIN, YELLOW_PIN, ButtonPad
from input import InputAction


class FakeButton:
    """Stands in for a gpiozero Button held to ground by a press."""

    def __init__(self, pressed=False):
        self.is_pressed = pressed
        self.closed = False

    def close(self):
        self.closed = True


class ButtonPadTests(unittest.TestCase):
    def setUp(self):
        self.red, self.yellow = FakeButton(), FakeButton()
        self.pad = ButtonPad(self.red, self.yellow)

    def test_the_panel_buttons_map_to_go_and_back(self):
        self.yellow.is_pressed = True
        self.assertEqual(self.pad.poll(), [InputAction.A])
        self.yellow.is_pressed = False
        self.red.is_pressed = True
        self.assertEqual(self.pad.poll(), [InputAction.B])

    def test_holding_a_button_does_not_repeat(self):
        self.red.is_pressed = True
        self.assertEqual(self.pad.poll(), [InputAction.B])
        for _ in range(30):                     # a second of holding it down
            self.assertEqual(self.pad.poll(), [])
        self.red.is_pressed = False
        self.assertEqual(self.pad.poll(), [])   # releasing is not an action
        self.red.is_pressed = True
        self.assertEqual(self.pad.poll(), [InputAction.B])

    def test_a_button_held_at_startup_does_not_fire(self):
        pad = ButtonPad(FakeButton(pressed=True), FakeButton(pressed=True))
        self.assertEqual(pad.poll(), [])

    def test_both_at_once_reports_both(self):
        self.red.is_pressed = self.yellow.is_pressed = True
        self.assertEqual(set(self.pad.poll()), {InputAction.A, InputAction.B})

    def test_closing_releases_both_pins(self):
        self.pad.close()
        self.assertTrue(self.red.closed and self.yellow.closed)

    def test_no_gpio_is_not_a_crash(self):
        # On a desktop there is no gpiozero, so the pad simply does not open.
        self.assertIsNone(ButtonPad.try_open())

    def test_the_documented_pins_are_the_ones_used(self):
        self.assertEqual((RED_PIN, YELLOW_PIN), (13, 26))


if __name__ == '__main__':
    unittest.main()
