import unittest
from decimal import Decimal

from eth_abi import decode, encode

import names
from names import Ens, Standings, dns_encode, handle, name_of, namehash

PLAYER = '0x0Dd7D7Ad21d15A999dcc7218E7Df3F25700e696f'
OTHER = '0x7ee85B080701330bf53Be62B7E72fcDD034eCCac'
NET = Ens('http://fake', 11155111, '0x' + '22' * 20, '0x' + '11' * 20, 0)


class FakeResolver:
    """Answers addr(bytes32) from a table of names, as the resolver on Sepolia does."""

    def __init__(self, records):
        self.records = {namehash(name): address for name, address in records.items()}
        self.asked = []

    def __call__(self, method, call, block):
        node = bytes.fromhex(call['data'][10:74])
        self.asked.append(node)
        return '0x' + encode(['address'], [self.records.get(node, names.ZERO)]).hex()


class FakeEns:
    """The registry's LabelRegistered logs and the Universal Resolver, from tables."""

    def __init__(self, head, registered, stats):
        self.head, self.registered, self.stats = head, registered, stats
        self.scanned = []

    def __call__(self, method, *params):
        if method == 'eth_blockNumber':
            return hex(self.head)
        if method == 'eth_getLogs':
            first, last = int(params[0]['fromBlock'], 16), int(params[0]['toBlock'], 16)
            self.scanned.append((first, last))
            return [{'data': '0x' + encode(['string', 'address', 'uint64'],
                                           [label, owner, 0]).hex()}
                    for block, label, owner in self.registered if first <= block <= last]
        dns_name = decode(['bytes', 'bytes'], bytes.fromhex(params[0]['data'][10:]))[0]
        label = dns_name[1:1 + dns_name[0]].decode()
        records = self.stats.get(label, {})
        answers = [encode(['string'], [records.get(key, '')]) for key in names.STATS]
        return '0x' + encode(['bytes', 'address'],
                             [encode(['bytes[]'], [answers]), NET.resolver]).hex()


class StandingsTests(unittest.TestCase):
    def test_ranks_by_pnl_and_skips_names_without_stats(self):
        rpc = FakeEns(25_000, [(3, 'scorekeeper', OTHER), (12_000, 'fancy-panda', PLAYER),
                               (20_000, 'rusty-mink', OTHER)],
                      {'fancy-panda': {'tick.sessions': '2', 'tick.wins': '0', 'tick.pnl': '-0.5'},
                       'rusty-mink': {'tick.sessions': '1', 'tick.wins': '1', 'tick.pnl': '0.005',
                                      'tick.best': '0.005'}})
        rows = Standings(NET, rpc).read()
        self.assertEqual([(r.name, r.pnl) for r in rows],
                         [('rusty-mink.tick.eth', Decimal('0.005')),
                          ('fancy-panda.tick.eth', Decimal('-0.5'))])
        self.assertEqual(rows[1].player, PLAYER)

    def test_a_refresh_reads_only_new_blocks(self):
        rpc = FakeEns(15_000, [], {})
        standings = Standings(NET, rpc)
        standings.read()
        self.assertEqual(rpc.scanned, [(0, 9_999), (10_000, 15_000)])
        rpc.head = 15_004
        standings.read()
        self.assertEqual(rpc.scanned[-1], (15_001, 15_004))


class NamesTests(unittest.TestCase):
    def test_namehash_matches_ens(self):
        self.assertEqual(namehash('eth').hex(),
                         '93cdeb708b7545dc668eb9280176169d1c33cfd8ed6f04690a0bcc88a93fc4ae')
        self.assertEqual(namehash('foo.eth').hex(),
                         'de9b09fd7c5f901e23a3f19fecc54828e9c848539801e86591bd9801b019f84f')
        self.assertEqual(namehash(''), bytes(32))

    def test_dns_encoding(self):
        self.assertEqual(dns_encode('tick.eth'), b'\x04tick\x03eth\x00')
        self.assertEqual(dns_encode(''), b'\x00')

    def test_a_wallet_always_gets_the_same_handle(self):
        first = handle(PLAYER)
        self.assertEqual(first, handle(PLAYER.lower()))
        self.assertRegex(first, r'^[a-z]+-[a-z]+$')
        self.assertEqual(handle(PLAYER, 1), f'{first}-2')
        self.assertNotEqual(first, handle(OTHER))

    def test_finds_the_wallets_name(self):
        rpc = FakeResolver({f'{handle(PLAYER)}.tick.eth': PLAYER})
        self.assertEqual(name_of(PLAYER, NET, rpc), f'{handle(PLAYER)}.tick.eth')

    def test_skips_a_handle_another_wallet_holds(self):
        rpc = FakeResolver({f'{handle(PLAYER)}.tick.eth': OTHER,
                            f'{handle(PLAYER, 1)}.tick.eth': PLAYER})
        self.assertEqual(name_of(PLAYER, NET, rpc), f'{handle(PLAYER, 1)}.tick.eth')

    def test_an_unnamed_wallet_has_no_name(self):
        rpc = FakeResolver({})
        self.assertIsNone(name_of(PLAYER, NET, rpc))
        self.assertEqual(len(rpc.asked), 1)    # handles are taken in order: one look is enough

    def test_no_resolver_means_no_lookup(self):
        self.assertIsNone(name_of(PLAYER, Ens('http://fake', 1, '', '', 0)))


if __name__ == '__main__':
    unittest.main()
