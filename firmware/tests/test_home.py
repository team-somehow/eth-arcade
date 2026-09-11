import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pygame

from input import InputAction
from screens.home import QUIT_CONFIRM_S, HomeScreen


class QuitTests(unittest.TestCase):
    """B on the launcher asks first; Escape still leaves at once."""

    def setUp(self):
        pygame.init()
        self.home = HomeScreen('box')

    def test_one_b_only_asks(self):
        self.assertIsNone(self.home.handle_action(InputAction.B))
        self.assertTrue(self.home.quitting)
        self.assertEqual(self.home.handle_action(InputAction.B), 'quit')

    def test_the_question_times_out(self):
        self.home.handle_action(InputAction.B)
        self.home.t += QUIT_CONFIRM_S + .1
        self.assertFalse(self.home.quitting)
        self.assertIsNone(self.home.handle_action(InputAction.B))

    def test_any_other_input_backs_out(self):
        self.home.handle_action(InputAction.B)
        self.home.handle_action(InputAction.DOWN)
        self.assertFalse(self.home.quitting)
        self.assertIsNone(self.home.handle_action(InputAction.B))

    def test_a_still_plays_while_asking(self):
        self.home.handle_action(InputAction.B)
        self.assertEqual(self.home.handle_action(InputAction.A), 'game')

    def test_escape_quits_at_once(self):
        self.assertEqual(self.home.handle_action(InputAction.QUIT), 'quit')

    def test_the_question_draws(self):
        self.home.handle_action(InputAction.B)
        self.home.draw(pygame.Surface((480, 320)))


if __name__ == '__main__':
    unittest.main()
