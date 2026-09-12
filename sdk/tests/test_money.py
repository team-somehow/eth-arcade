"""Money is integers. These tests are why."""
import unittest

from tick.money import (MICRO, DemoFunding, Wallet, format_usdc, parse_usdc,
                        places_for, stake_micro, to_micro)


class TestAmounts(unittest.TestCase):
    def test_decimal_parsing_is_exact_where_float_is_not(self):
        # float('0.57') * 1e6 is 569999.9999999999
        self.assertEqual(parse_usdc('0.57'), 570_000)
        self.assertEqual(parse_usdc('10'), 10 * MICRO)
        self.assertEqual(parse_usdc('0.000001'), 1)

    def test_more_than_six_decimals_is_refused(self):
        with self.assertRaises(ValueError):
            parse_usdc('0.0000001')

    def test_nonsense_is_refused(self):
        for bad in ('', 'ten', 'nan', '1e400'):
            with self.assertRaises(ValueError):
                parse_usdc(bad)

    def test_to_micro_truncates_rather_than_rounds_up(self):
        self.assertEqual(to_micro(1.9999999), 1_999_999)

    def test_places_shows_a_small_stake_honestly(self):
        self.assertEqual(places_for(10 * MICRO), 0)
        self.assertEqual(places_for(1_000), 3)
        self.assertEqual(format_usdc(1_000, 3), '0.001')
        self.assertEqual(format_usdc(10 * MICRO, 2), '10.00')


class TestWallet(unittest.TestCase):
    def setUp(self):
        self.wallet = Wallet(100 * MICRO, DemoFunding())

    def test_debit_refuses_more_than_the_balance(self):
        self.assertFalse(self.wallet.debit(101 * MICRO))
        self.assertEqual(self.wallet.balance, 100 * MICRO)

    def test_debit_refuses_zero_and_negatives(self):
        self.assertFalse(self.wallet.debit(0))
        self.assertFalse(self.wallet.debit(-5))

    def test_credit_refuses_negatives(self):
        with self.assertRaises(ValueError):
            self.wallet.credit(-1)

    def test_a_thousand_small_bets_leave_no_drift(self):
        for _ in range(1000):
            self.assertTrue(self.wallet.debit(1))
            self.wallet.credit(1)
        self.assertEqual(self.wallet.balance, 100 * MICRO)

    def test_demo_funding_confirms_and_credits(self):
        deposit = self.wallet.load(25)
        self.assertEqual(deposit.status, 'confirmed')
        self.assertEqual(self.wallet.balance, 125 * MICRO)

    def test_an_unconfirmed_deposit_is_not_spendable(self):
        class Pending:
            name, live = 'X', True
            def load(self, amount):
                from tick.money import Deposit
                return Deposit(amount, 'pending', 'tx')
        wallet = Wallet(0, Pending())
        wallet.load(10)
        self.assertEqual(wallet.balance, 0)

    def test_cap_comes_from_the_funding_backend(self):
        self.assertIsNone(self.wallet.cap)
        class Capped(DemoFunding):
            cap = 50 * MICRO
        wallet = Wallet(40 * MICRO, Capped())
        self.assertFalse(wallet.would_exceed_cap(50 * MICRO))
        self.assertTrue(wallet.would_exceed_cap(51 * MICRO))


class TestStake(unittest.TestCase):
    def test_stake_comes_from_the_environment(self):
        import os
        old = os.environ.get('TICK_STAKE_USDC')
        os.environ['TICK_STAKE_USDC'] = '0.001'
        try:
            self.assertEqual(stake_micro(), 1_000)
        finally:
            os.environ.pop('TICK_STAKE_USDC', None)
            if old is not None:
                os.environ['TICK_STAKE_USDC'] = old


if __name__ == '__main__':
    unittest.main()
