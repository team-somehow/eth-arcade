import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest
from unittest import mock

from games.box import BoxGame
from games.box_model import BoxModel
from games.rush_model import RushModel
from wallet import MICRO, DemoFunding, Wallet, format_usdc, parse_usdc, places_for, stake_micro


def stake_env(text):
    return mock.patch.dict(os.environ, {'TICK_STAKE_USDC': text})


class StakeSettingTests(unittest.TestCase):
    def test_default_is_ten_usdc(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('TICK_STAKE_USDC', None)
            self.assertEqual(stake_micro(), 10 * MICRO)

    def test_amounts_parse_exactly(self):
        self.assertEqual(parse_usdc('0.001'), 1_000)
        self.assertEqual(parse_usdc(' 25 '), 25 * MICRO)
        # Float arithmetic makes this 569_999.
        self.assertEqual(parse_usdc('0.57'), 570_000)

    def test_bad_stakes_are_refused(self):
        for text in ('0', '-1', 'abc', '', '0.0000001', 'nan', 'inf'):
            with self.subTest(text=text), stake_env(text):
                with self.assertRaises(ValueError):
                    stake_micro()

    def test_both_games_stake_from_the_setting(self):
        with stake_env('0.001'):
            self.assertEqual(BoxModel(Wallet(MICRO, DemoFunding())).STAKE, 1_000)
            self.assertEqual(RushModel(Wallet(MICRO, DemoFunding())).STAKE, 1_000)
        self.assertEqual(BoxModel(Wallet(MICRO, DemoFunding()), stake=7).STAKE, 7)


class StakeDisplayTests(unittest.TestCase):
    def test_places_follow_the_amount(self):
        self.assertEqual(places_for(10 * MICRO), 0)
        self.assertEqual(places_for(1_500_000), 1)
        self.assertEqual(places_for(1_000), 3)
        self.assertEqual(places_for(1), 6)

    def test_balances_show_a_tiny_stake(self):
        with stake_env('0.001'):
            self.assertEqual(format_usdc(99_999_000), '99.999')
        with stake_env('10'):
            self.assertEqual(format_usdc(99_999_000), '100.00')

    def test_box_labels_show_the_stake(self):
        with stake_env('0.001'):
            game = BoxGame(seed=1, sound=False, source='sim', wallet=Wallet(MICRO, DemoFunding()))
            try:
                self.assertEqual(game.stake_text(), '0.001')
                self.assertEqual(game.stake_text(3_000), '0.003')
            finally:
                game.close()


if __name__ == '__main__':
    unittest.main()
