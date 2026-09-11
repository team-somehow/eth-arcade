"""The scorekeeper's arithmetic, without a network.

    firmware/.venv/bin/python -m unittest discover -s ens
"""
import unittest

from eth_abi import encode

import scorekeeper as sk

PLAYER = '0x0Dd7D7Ad21d15A999dcc7218E7Df3F25700e696f'


def opened(sid, player, deposit):
    return {'topics': [sk.OPENED, hex(sid), '0x' + player[2:].lower().rjust(64, '0'),
                       '0x' + '00' * 32],
            'data': '0x' + encode(['uint256', 'uint256'], [deposit, deposit * 4]).hex(),
            'transactionHash': f'0xopen{sid}'}


def closed(sid, payout):
    return {'topics': [sk.CLOSED, hex(sid)],
            'data': '0x' + encode(['uint256', 'uint256', 'int256'], [payout, payout, 0]).hex(),
            'transactionHash': f'0xclose{sid}'}


def reclaimed(sid, refund):
    return {'topics': [sk.RECLAIMED, hex(sid)], 'data': '0x' + encode(['uint256'], [refund]).hex(),
            'transactionHash': f'0xreclaim{sid}'}


class ScorekeeperTests(unittest.TestCase):
    def setUp(self):
        self.keeper = sk.Scorekeeper(None, None, None, '0xescrow', 1)

    def feed(self, *logs):
        for log in logs:
            self.keeper.apply(log)
        return self.keeper.stats[PLAYER].records()

    def test_usdc_reads_like_money(self):
        self.assertEqual(sk.usdc(45_000), '0.045')
        self.assertEqual(sk.usdc(-5_000), '-0.005')
        self.assertEqual(sk.usdc(0), '0')
        self.assertEqual(sk.usdc(10_000_000), '10')

    def test_a_win_and_a_loss(self):
        records = self.feed(opened(1, PLAYER, 40_000), closed(1, 45_000),
                            opened(2, PLAYER, 100_000), closed(2, 0))
        self.assertEqual(records, {
            'tick.sessions': '2', 'tick.wins': '1', 'tick.deposited': '0.14',
            'tick.paid': '0.045', 'tick.pnl': '-0.095', 'tick.best': '0.005',
            'tick.last_tx': '0xclose2'})

    def test_a_losing_player_keeps_their_least_bad_session_as_best(self):
        records = self.feed(opened(1, PLAYER, 50_000), closed(1, 10_000),
                            opened(2, PLAYER, 50_000), closed(2, 40_000))
        self.assertEqual(records['tick.best'], '-0.01')

    def test_a_reclaim_breaks_even(self):
        records = self.feed(opened(1, PLAYER, 40_000), reclaimed(1, 40_000))
        self.assertEqual((records['tick.sessions'], records['tick.wins'], records['tick.pnl']),
                         ('1', '0', '0'))

    def test_a_player_is_known_from_the_deposit_and_scored_on_the_close(self):
        records = self.feed(opened(1, PLAYER, 40_000))
        self.assertEqual(records['tick.sessions'], '0')

    def test_a_close_from_before_the_scan_is_ignored(self):
        self.keeper.apply(closed(9, 45_000))
        self.assertEqual(self.keeper.stats, {})


if __name__ == '__main__':
    unittest.main()
