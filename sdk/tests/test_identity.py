"""Names, without touching a network: the parts that are pure functions."""
import unittest

from tick.identity import (ADJECTIVES, NOUNS, coin_type, dns_encode, ens, handle,
                           name_of, namehash)


class FakeRpc:
    """Answers `addr(bytes32)` from a table of name -> address."""

    def __init__(self, owners):
        self.owners = owners
        self.calls = 0

    def __call__(self, method, *params):
        self.calls += 1
        # The last 20 bytes of the 32-byte return value are the address.
        for name, address in self.owners.items():
            if namehash(name).hex() in params[0]['data']:
                return '0x' + address[2:].rjust(64, '0')
        return '0x' + '0' * 64


class TestHandles(unittest.TestCase):
    def test_a_handle_is_derived_from_the_address_and_is_stable(self):
        address = '0x' + 'ab' * 20
        self.assertEqual(handle(address), handle(address))
        adjective, noun = handle(address).split('-')
        self.assertIn(adjective, ADJECTIVES)
        self.assertIn(noun, NOUNS)

    def test_different_wallets_get_different_handles(self):
        made = {handle('0x' + f'{i:040x}') for i in range(200)}
        self.assertGreater(len(made), 150)     # collisions exist, and fall through to -2

    def test_a_later_attempt_is_numbered(self):
        address = '0x' + 'ab' * 20
        self.assertEqual(handle(address, 1), handle(address) + '-2')


class TestNames(unittest.TestCase):
    def test_namehash_matches_the_ens_specification(self):
        self.assertEqual(namehash('').hex(), '00' * 32)
        self.assertEqual(
            namehash('eth').hex(),
            '93cdeb708b7545dc668eb9280176169d1c33cfd8ed6f04690a0bcc88a93fc4ae')

    def test_dns_encoding_is_length_prefixed(self):
        self.assertEqual(dns_encode('a.eth'), b'\x01a\x03eth\x00')
        self.assertEqual(dns_encode(''), b'\x00')

    def test_a_name_is_trusted_only_when_it_points_back(self):
        wallet = '0x' + 'AB' * 20
        mine = f'{handle(wallet)}.tick.eth'
        rpc = FakeRpc({mine: wallet})
        self.assertEqual(name_of(wallet, rpc=rpc), mine)

    def test_a_handle_owned_by_someone_else_falls_through(self):
        wallet = '0x' + 'AB' * 20
        other = '0x' + 'CD' * 20
        first = f'{handle(wallet)}.tick.eth'
        second = f'{handle(wallet, 1)}.tick.eth'
        rpc = FakeRpc({first: other, second: wallet})
        self.assertEqual(name_of(wallet, rpc=rpc), second)

    def test_an_unregistered_handle_stops_the_search_at_once(self):
        wallet = '0x' + 'AB' * 20
        rpc = FakeRpc({})
        self.assertIsNone(name_of(wallet, rpc=rpc))
        self.assertEqual(rpc.calls, 1)       # no point asking about -2 and -3


class TestConfig(unittest.TestCase):
    def test_the_coin_type_follows_ensip_11(self):
        self.assertEqual(coin_type(1), 0x80000001)
        self.assertEqual(coin_type(5042002), 0x80000000 | 5042002)

    def test_settings_override_every_address(self):
        import os
        os.environ['TICK_ENS_PARENT'] = 'mygame.eth'
        try:
            self.assertEqual(ens().parent, 'mygame.eth')
        finally:
            os.environ.pop('TICK_ENS_PARENT')

    def test_a_leaderboard_reads_nothing_until_asked(self):
        from tick.identity import Leaderboard
        board = Leaderboard(read=lambda: [])
        self.assertIsNone(board.rows)
        board.refresh()
        self.assertEqual(board.rows, [])

    def test_a_leaderboard_keeps_its_last_rows_when_the_rpc_dies(self):
        from tick.identity import Leaderboard
        state = {'fail': False}

        def read():
            if state['fail']:
                raise OSError('sepolia is down')
            return ['a row']

        board = Leaderboard(read=read)
        board.refresh()
        state['fail'] = True
        self.assertFalse(board.refresh())
        self.assertEqual(board.rows, ['a row'])
        self.assertIn('sepolia', board.error)


if __name__ == '__main__':
    unittest.main()
