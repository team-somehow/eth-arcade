"""The odds maths, on its own: no feed, no wallet, no game."""
import math
import unittest

from tick.pricing import (DEFAULT_VARIANCE, annualized, multiple, normal_cdf,
                          probability, scale_to_window, sigma)


class TestPricing(unittest.TestCase):
    def test_normal_cdf_is_symmetric(self):
        self.assertAlmostEqual(normal_cdf(0), 0.5)
        self.assertAlmostEqual(normal_cdf(1) + normal_cdf(-1), 1.0)

    def test_sigma_grows_with_the_square_root_of_time(self):
        one = sigma(2500, DEFAULT_VARIANCE, 10)
        four = sigma(2500, DEFAULT_VARIANCE, 40)
        self.assertAlmostEqual(four / one, 2.0, places=6)

    def test_a_band_of_one_sigma_is_about_68_percent(self):
        price, horizon = 2500.0, 10.0
        band = sigma(price, DEFAULT_VARIANCE, horizon)
        chance = probability(price, price - band, price + band, DEFAULT_VARIANCE, horizon)
        self.assertAlmostEqual(chance, 0.6827, places=3)

    def test_a_one_sided_range_is_half(self):
        chance = probability(2500, 2500, 10 ** 9, DEFAULT_VARIANCE, 10)
        self.assertAlmostEqual(chance, 0.5, places=3)

    def test_fair_multiple_is_one_over_the_chance(self):
        self.assertAlmostEqual(multiple(0.25), 4.0)
        self.assertAlmostEqual(multiple(0.5, edge=0.1), 1.8)

    def test_multiple_is_capped_and_never_infinite(self):
        self.assertEqual(multiple(0.0), 25.0)
        self.assertEqual(multiple(1e-12, cap=25), 25.0)

    def test_scaling_a_window_moves_geometry_by_root_time(self):
        self.assertAlmostEqual(scale_to_window(8.0, 20.0, 20.0), 8.0)
        self.assertAlmostEqual(scale_to_window(8.0, 5.0, 20.0), 4.0)

    def test_annualized_round_trips(self):
        self.assertAlmostEqual(annualized(DEFAULT_VARIANCE), 0.55, places=6)

    def test_an_impossible_range_is_zero(self):
        self.assertEqual(probability(2500, 2600, 2500, DEFAULT_VARIANCE, 10), 0.0)

    def test_a_wilder_market_pays_more_for_the_same_box(self):
        calm = probability(2500, 2499, 2501, DEFAULT_VARIANCE, 10)
        wild = probability(2500, 2499, 2501, DEFAULT_VARIANCE * 16, 10)
        self.assertGreater(multiple(wild), multiple(calm))
        self.assertTrue(math.isfinite(multiple(wild)))


if __name__ == '__main__':
    unittest.main()
