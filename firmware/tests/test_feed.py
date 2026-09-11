import http.server
import json
import os
import threading
import time
import unittest
from unittest import mock

from markets.feed import (ASSETS, CoinbaseFeed, PoolBook, SimulatedFeed, SubstreamsFeed,
                          current_asset, open_feed, parse_coinbase, weighted_median)

NOW = 1_800_000_000.0


def line(chain, block, seconds_ago=1.0, prices=(), now=NOW):
    """One line as substreams/stream.sh prints it."""
    data = {'blockNumber': str(block), 'timestampMs': str(int((now - seconds_ago) * 1000))}
    if prices:
        data['prices'] = [{'pool': pool, 'price': price, 'liquidity': str(liquidity)}
                          for pool, price, liquidity in prices]
    return json.dumps({'chain': chain, '@block': block, '@data': data})


class WeightedMedianTest(unittest.TestCase):
    def test_the_heavy_side_wins(self):
        self.assertEqual(weighted_median([(1.0, 1), (2.0, 1), (3.0, 10)]), 3.0)

    def test_equal_weights_give_the_plain_median(self):
        self.assertEqual(weighted_median([(3.0, 1), (1.0, 1), (2.0, 1)]), 2.0)

    def test_one_thin_outlier_cannot_move_it(self):
        self.assertEqual(weighted_median([(2500.0, 5), (2501.0, 5), (9999.0, 1)]), 2501.0)
        self.assertEqual(weighted_median([(2500.0, 5), (2501.0, 5), (1.0, 1)]), 2500.0)

    def test_nothing_to_weigh_is_an_error(self):
        with self.assertRaises(ValueError):
            weighted_median([(1.0, 0)])


class PoolBookTest(unittest.TestCase):
    def test_a_block_without_swaps_still_reads_the_last_prices(self):
        book = PoolBook()
        book.apply(line('base', 10, 3, [('0xa', 2500.0, 100)]), NOW)
        block_time = book.apply(line('base', 11, 1), NOW)
        self.assertEqual(block_time, NOW - 1)
        self.assertEqual(book.price(NOW), 2500.0)

    def test_pools_on_both_chains_are_averaged_by_liquidity(self):
        book = PoolBook()
        book.apply(line('arbitrum', 5, 1, [('0xa', 2500.0, 10), ('0xb', 2502.0, 1)]), NOW)
        book.apply(line('base', 9, 1, [('0xc', 2501.0, 3)]), NOW)
        self.assertAlmostEqual(book.price(NOW), (25000 + 2502 + 7503) / 14)
        book.apply(line('base', 10, 1, [('0xc', 2501.0, 30)]), NOW)
        self.assertAlmostEqual(book.price(NOW), (25000 + 2502 + 75030) / 41)

    def test_a_trade_in_any_pool_moves_the_price(self):
        book = PoolBook()
        book.apply(line('base', 10, 1, [('0xbig', 2500.0, 100), ('0xsmall', 2500.0, 10)]), NOW)
        before = book.price(NOW)
        book.apply(line('base', 11, 1, [('0xsmall', 2501.0, 10)]), NOW)
        self.assertGreater(book.price(NOW), before)

    def test_a_pool_far_from_the_rest_is_left_out(self):
        book = PoolBook()
        book.apply(line('base', 10, 1, [('0xa', 2500.0, 5), ('0xb', 2501.0, 5), ('0xc', 2600.0, 1)]), NOW)
        self.assertAlmostEqual(book.price(NOW), 2500.5)

    def test_old_and_repeated_blocks_are_skipped(self):
        book = PoolBook()
        book.apply(line('base', 10, 1, [('0xa', 2500.0, 1)]), NOW)
        self.assertIsNone(book.apply(line('base', 10, 1, [('0xa', 1.0, 1)]), NOW))
        self.assertIsNone(book.apply(line('base', 9, 1, [('0xa', 1.0, 1)]), NOW))
        self.assertEqual(book.price(NOW), 2500.0)

    def test_a_stalled_chain_drops_out(self):
        book = PoolBook()
        book.apply(line('arbitrum', 5, 30, [('0xa', 2400.0, 100)]), NOW)
        book.apply(line('base', 9, 1, [('0xc', 2500.0, 1)]), NOW)
        self.assertEqual(book.price(NOW), 2500.0)

    def test_bad_prices_are_ignored_and_future_blocks_rejected(self):
        book = PoolBook()
        book.apply(line('base', 10, 1, [('0xa', -1.0, 5), ('0xb', 2500.0, 0)]), NOW)
        self.assertIsNone(book.price(NOW))
        with self.assertRaises(ValueError):
            book.apply(line('base', 11, -60), NOW)

    def test_lines_without_data_are_skipped(self):
        self.assertIsNone(PoolBook().apply('{"chain": "base"}', NOW))


class SubstreamsFeedTest(unittest.TestCase):
    """The real feed against a local stand-in for substreams/relay.py."""

    def serve(self, lines):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                for text in lines:
                    self.wfile.write(text.encode() + b'\n')
                    self.wfile.flush()
                time.sleep(.5)

            def log_message(self, *_):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return f'http://127.0.0.1:{server.server_address[1]}'

    def test_every_block_becomes_a_tick_aged_by_block_time(self):
        now = time.time()
        url = self.serve([
            line('base', 1, 2.0, [('0xa', 2500.0, 5)], now),
            line('base', 2, 1.0, now=now),
            line('arbitrum', 7, 1.0, [('0xb', 2510.0, 50)], now),
        ])
        feed = SubstreamsFeed(url)
        self.addCleanup(feed.close)
        ticks = []
        deadline = time.monotonic() + 3
        while len(ticks) < 3 and time.monotonic() < deadline:
            ticks += feed.poll(0, 0)
            time.sleep(.02)
        self.assertEqual([t.price for t in ticks[:2]], [2500.0, 2500.0])
        self.assertAlmostEqual(ticks[2].price, (2500 * 5 + 2510 * 50) / 55)
        self.assertEqual([t.sequence for t in ticks], [1, 2, 3])
        self.assertAlmostEqual(ticks[0].source_age, 2.0, delta=.5)
        self.assertAlmostEqual(ticks[1].source_age, 1.0, delta=.5)
        self.assertIn('2 pools', feed.status)

    def test_no_relay_reports_itself_and_yields_nothing(self):
        feed = SubstreamsFeed('http://127.0.0.1:9')
        self.addCleanup(feed.close)
        time.sleep(.3)
        self.assertEqual(feed.poll(0, 0), [])
        self.assertIn('unavailable', feed.status)


class CoinbaseFeedTest(unittest.TestCase):
    """The real poller against a local stand-in for the Coinbase ticker."""

    def serve(self, answers):
        served = iter(answers)
        last = [answers[-1]]

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps(next(served, last[0])).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return f'http://127.0.0.1:{server.server_address[1]}/ticker'

    def test_a_quiet_book_is_not_a_dead_feed(self):
        from datetime import datetime, timezone

        def trade(trade_id, price, seconds_ago):
            stamp = datetime.fromtimestamp(time.time() - seconds_ago, timezone.utc)
            return {'trade_id': trade_id, 'price': str(price),
                    'time': stamp.isoformat().replace('+00:00', 'Z')}

        url = self.serve([
            trade(10, 2500.0, 10),      # nobody has traded for ten seconds
            trade(10, 2500.0, 10),      # still nobody: the same answer again
            trade(9, 2490.0, 12),       # a lagging cache node, older still
            trade(11, 2501.0, .1),      # a fresh trade
        ])

        class Local(CoinbaseFeed):
            URL = url
            INTERVAL = .02

        feed = Local()
        self.addCleanup(feed.close)
        ticks = []
        deadline = time.monotonic() + 3
        while len(ticks) < 3 and time.monotonic() < deadline:
            ticks += feed.poll(0, 0)
            time.sleep(.01)
        # The repeat is a tick (the price is confirmed, not dead); the older
        # trade is not (it would walk the price backwards).
        self.assertEqual([t.price for t in ticks[:3]], [2500.0, 2500.0, 2501.0])
        self.assertEqual([t.sequence for t in ticks[:3]], [1, 2, 3])
        # Aged by the answer, not by a trade from ten seconds ago.
        for tick in ticks[:3]:
            self.assertLessEqual(tick.source_age, CoinbaseFeed.CACHE_S)

    def test_nanosecond_timestamps_parse(self):
        # Coinbase's real format, which Python 3.9's fromisoformat rejects.
        data = {'trade_id': 1, 'price': '99.69', 'time': '2027-01-15T07:59:59.123456789Z'}
        tick = parse_coinbase(data, 0.0, NOW)
        self.assertEqual(tick.price, 99.69)
        self.assertAlmostEqual(tick.source_age, 0.876544, places=5)


class OpenFeedTest(unittest.TestCase):
    def test_sources(self):
        self.assertIsInstance(open_feed('sim', 1), SimulatedFeed)
        for source, kind in (('coinbase', CoinbaseFeed), ('substreams', SubstreamsFeed)):
            feed = open_feed(source)
            self.addCleanup(feed.close)
            self.assertIsInstance(feed, kind)
        with self.assertRaises(ValueError):
            open_feed('subgraph')


class AssetTest(unittest.TestCase):
    def test_eth_is_the_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(current_asset().symbol, 'ETH')

    def test_tick_asset_picks_the_coin(self):
        for key, symbol in (('btc', 'BTC'), ('SOL', 'SOL'), (' eth ', 'ETH'), ('hbar', 'HBAR')):
            with mock.patch.dict(os.environ, {'TICK_ASSET': key}):
                self.assertEqual(current_asset().symbol, symbol)
        with mock.patch.dict(os.environ, {'TICK_ASSET': 'doge'}):
            with self.assertRaises(ValueError):
                current_asset()

    def test_sim_starts_at_the_coins_price(self):
        for key in ('btc', 'sol', 'hbar'):
            feed = open_feed('sim', 1, ASSETS[key])
            self.assertEqual(feed.price, ASSETS[key].start)
            self.assertIn(ASSETS[key].symbol, feed.status)
            self.assertTrue(feed.poll(1.0, 0))

    def test_coinbase_polls_the_coins_product(self):
        feed = open_feed('coinbase', asset=ASSETS['sol'])
        self.addCleanup(feed.close)
        self.assertIn('/products/SOL-USD/', feed.url)

    def test_a_sub_dollar_coin_shows_enough_decimals(self):
        self.assertEqual(ASSETS['hbar'].format(0.073551), '0.07355')
        self.assertEqual(ASSETS['hbar'].format(0.00012, sign=True), '+0.00012')
        self.assertEqual(ASSETS['eth'].format(2473.334), '2,473.33')

    def test_substreams_only_prices_eth(self):
        with self.assertRaises(ValueError):
            open_feed('substreams', asset=ASSETS['btc'])


if __name__ == '__main__':
    unittest.main()
