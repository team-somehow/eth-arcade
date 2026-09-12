"""What the market refuses to price, and why."""
import unittest

from tick.market import Market, moved
from tick.pricing import DEFAULT_VARIANCE
from tick.testing import ScriptedFeed
from tick.ticks import PriceTick


def feed_market(rows, **kwargs):
    return Market(feed=ScriptedFeed(rows, **kwargs))


class TestAcceptance(unittest.TestCase):
    def setUp(self):
        self.market = Market(feed=ScriptedFeed([]))

    def test_a_duplicate_or_older_sequence_is_dropped(self):
        self.assertTrue(self.market.accept(PriceTick(2500, 5, 100.0), 100.0))
        self.assertFalse(self.market.accept(PriceTick(2600, 5, 100.0), 100.0))
        self.assertFalse(self.market.accept(PriceTick(2600, 4, 100.0), 100.0))
        self.assertEqual(self.market.price, 2500)

    def test_a_tick_born_stale_cannot_price_anything(self):
        self.assertFalse(self.market.accept(PriceTick(2500, 1, 100.0, source_age=9.0), 100.0))
        self.assertIsNone(self.market.tick)

    def test_impossible_prices_are_dropped(self):
        for bad in (0.0, -1.0, float('nan'), float('inf')):
            self.assertFalse(self.market.accept(PriceTick(bad, 1, 100.0), 100.0))

    def test_a_negative_source_age_is_dropped(self):
        self.assertFalse(self.market.accept(PriceTick(2500, 1, 100.0, -1.0), 100.0))

    def test_freshness_counts_arrival_and_source_age_together(self):
        self.market.accept(PriceTick(2500, 1, 100.0, source_age=3.0), 100.0)
        self.assertTrue(self.market.fresh(100.5))
        self.assertFalse(self.market.fresh(102.0))    # 2s waiting + 3s source age


class TestStillness(unittest.TestCase):
    def test_a_flat_feed_is_quiet_and_sells_nothing(self):
        market = feed_market([(i * 0.5, 2500.0) for i in range(80)])
        now, last = 1000.0, 1000.0
        for _ in range(1200):
            now += 1 / 30
            market.poll(now - last, now)
            last = now
        self.assertTrue(market.quiet(now))
        self.assertFalse(market.sellable(now))
        self.assertEqual(market.why_not(now), 'MARKET QUIET / NO BETS')

    def test_stillness_is_counted_as_calm_not_skipped(self):
        """A minute that moved once is calmer than a minute that moved constantly."""
        busy = feed_market([(i * 0.5, 2500.0 + (i % 2) * 3) for i in range(120)])
        calm = feed_market([(i * 0.5, 2500.0 + (3 if i > 100 else 0)) for i in range(120)])
        for market in (busy, calm):
            now, last = 1000.0, 1000.0
            for _ in range(1800):
                now += 1 / 30
                market.poll(now - last, now)
                last = now
        self.assertLess(calm.variance, busy.variance)

    def test_nothing_is_priced_until_the_feed_has_been_read(self):
        market = feed_market([(0.0, 2500.0)])
        market.poll(0.1, 1000.0)
        self.assertFalse(market.ready)
        self.assertEqual(market.why_not(1000.0), 'READING THE MARKET')

    def test_a_spike_cannot_inflate_the_odds(self):
        steady = [(i * 0.1, 2500.0 + (i % 7) * 0.2) for i in range(300)]
        spiked = list(steady)
        spiked[150] = (15.0, 4000.0)
        a, b = feed_market(steady), feed_market(spiked)
        for market in (a, b):
            now, last = 1000.0, 1000.0
            for _ in range(1200):
                now += 1 / 30
                market.poll(now - last, now)
                last = now
        # The cap is 4x the median move, so one wild print cannot run away with it.
        self.assertLess(b.variance, a.variance * 40)

    def test_variance_never_collapses_to_zero(self):
        market = feed_market([(i * 0.5, 2500.0) for i in range(40)])
        now, last = 1000.0, 1000.0
        for _ in range(900):
            now += 1 / 30
            market.poll(now - last, now)
            last = now
        self.assertGreaterEqual(market.variance, DEFAULT_VARIANCE / 20)


class TestMoved(unittest.TestCase):
    def test_float_noise_is_not_a_move(self):
        self.assertFalse(moved(2500.0, 2500.0 + 1e-9))
        self.assertTrue(moved(2500.0, 2500.01))


if __name__ == '__main__':
    unittest.main()
