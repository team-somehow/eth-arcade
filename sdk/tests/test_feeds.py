"""Feeds: determinism, pool combination, recording round trips."""
import json
import tempfile
import unittest
from pathlib import Path

from tick.feeds import (PoolBook, ReplayFeed, Recorder, SimulatedFeed, open_feed,
                        parse_block, weighted_median)
from tick.feeds.coinbase import parse_coinbase
from tick.ticks import ASSETS


def drive(feed, seconds=10.0, dt=1 / 30, start=1000.0):
    now, out = start, []
    for _ in range(int(seconds / dt)):
        now += dt
        out.extend(feed.poll(dt, now))
    return out


class TestSimulated(unittest.TestCase):
    def test_the_same_seed_is_the_same_market(self):
        a = [t.price for t in drive(SimulatedFeed(7))]
        b = [t.price for t in drive(SimulatedFeed(7))]
        self.assertEqual(a, b)
        self.assertNotEqual(a, [t.price for t in drive(SimulatedFeed(8))])

    def test_tick_spacing_does_not_depend_on_the_frame_rate(self):
        slow = len(drive(SimulatedFeed(1), 10.0, dt=1 / 10))
        fast = len(drive(SimulatedFeed(1), 10.0, dt=1 / 60))
        self.assertEqual(slow, fast)

    def test_sequence_numbers_only_rise(self):
        ticks = drive(SimulatedFeed(3))
        self.assertEqual([t.sequence for t in ticks], list(range(1, len(ticks) + 1)))


class TestPoolBook(unittest.TestCase):
    def line(self, chain, number, pools, ms=1_700_000_000_000):
        return json.dumps({'chain': chain, '@block': number, '@data': {
            'blockNumber': number, 'timestampMs': ms,
            'prices': [{'pool': p, 'price': v, 'liquidity': l} for p, v, l in pools]}})

    def test_pools_are_weighted_by_liquidity(self):
        book = PoolBook()
        now = 1_700_000_000.0
        book.apply(self.line('arb', 1, [('0xa', 2500.0, 9.0), ('0xb', 2510.0, 1.0)]), now)
        self.assertAlmostEqual(book.price(now), 2501.0)

    def test_a_pool_far_from_the_rest_is_left_out(self):
        book = PoolBook()
        now = 1_700_000_000.0
        book.apply(self.line('arb', 1, [('0xa', 2500.0, 9.0), ('0xb', 2500.5, 8.0),
                                        ('0xc', 3000.0, 5.0)]), now)
        self.assertLess(book.price(now), 2501.0)

    def test_a_block_already_seen_is_skipped(self):
        book = PoolBook()
        now = 1_700_000_000.0
        line = self.line('arb', 5, [('0xa', 2500.0, 1.0)])
        self.assertIsNotNone(book.apply(line, now))
        self.assertIsNone(book.apply(line, now))

    def test_a_block_from_the_future_is_refused(self):
        book = PoolBook()
        with self.assertRaises(ValueError):
            book.apply(self.line('arb', 1, [('0xa', 2500.0, 1.0)], ms=2_000_000_000_000),
                       1_700_000_000.0)

    def test_a_chain_that_stops_streaming_stops_counting(self):
        book = PoolBook()
        now = 1_700_000_000.0
        book.apply(self.line('arb', 1, [('0xa', 2500.0, 1.0)], ms=int(now * 1000)), now)
        self.assertIsNotNone(book.price(now))
        self.assertIsNone(book.price(now + 60))

    def test_broken_pool_numbers_are_dropped_not_averaged(self):
        block = parse_block(self.line('arb', 1, [('0xa', 2500.0, 1.0), ('0xb', -1.0, 1.0),
                                                 ('0xc', 2501.0, 0.0)]))
        self.assertEqual([p.pool for p in block.prices], ['0xa'])

    def test_weighted_median_splits_the_weight(self):
        self.assertEqual(weighted_median([(1.0, 1.0), (2.0, 5.0), (3.0, 1.0)]), 2.0)
        with self.assertRaises(ValueError):
            weighted_median([])


class TestCoinbaseParsing(unittest.TestCase):
    def payload(self, **over):
        data = {'price': '2500.12', 'trade_id': 42, 'time': '2026-01-01T00:00:00.123456789Z'}
        data.update(over)
        return data

    def test_a_good_payload_becomes_a_tick(self):
        tick = parse_coinbase(self.payload(), 100.0, 1_767_225_600.5)
        self.assertAlmostEqual(tick.price, 2500.12)
        self.assertEqual(tick.sequence, 42)

    def test_a_stamp_from_the_future_is_refused(self):
        with self.assertRaises(ValueError):
            parse_coinbase(self.payload(time='2030-01-01T00:00:00.000000Z'), 100.0, 1_767_225_600.0)

    def test_a_stamp_without_a_zone_is_refused(self):
        with self.assertRaises(ValueError):
            parse_coinbase(self.payload(time='2026-01-01T00:00:00.000000'), 100.0, 1_767_225_600.0)

    def test_a_nonsense_price_is_refused(self):
        with self.assertRaises(ValueError):
            parse_coinbase(self.payload(price='-1'), 100.0, 1_767_225_600.0)


class TestReplay(unittest.TestCase):
    def test_a_recording_round_trips(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'market.ndjson'
            with Recorder(SimulatedFeed(11), path) as recorder:
                original = [t.price for t in drive(recorder, 5.0)]
            replayed = [t.price for t in drive(ReplayFeed(path), 6.0)]
            self.assertEqual(original, replayed)

    def test_speed_compresses_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'market.ndjson'
            with Recorder(SimulatedFeed(11), path) as recorder:
                drive(recorder, 10.0)
            fast = drive(ReplayFeed(path, speed=10.0), 1.2)
            self.assertGreater(len(fast), 150)

    def test_an_empty_recording_is_refused(self):
        with self.assertRaises(ValueError):
            ReplayFeed(rows=[])


class TestOpenFeed(unittest.TestCase):
    def test_the_name_picks_the_feed(self):
        self.assertEqual(open_feed('sim').name, 'SIMULATED')
        self.assertEqual(open_feed('frozen').name, 'FROZEN')

    def test_an_unknown_source_says_what_is_allowed(self):
        with self.assertRaises(ValueError) as caught:
            open_feed('nasdaq')
        self.assertIn('substreams', str(caught.exception))

    def test_substreams_refuses_a_coin_it_does_not_price(self):
        with self.assertRaises(ValueError):
            open_feed('substreams', asset=ASSETS['sol'])


if __name__ == '__main__':
    unittest.main()
