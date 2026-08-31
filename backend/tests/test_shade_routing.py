from datetime import datetime, timezone
import unittest

from shapely.geometry import LineString, Polygon

from app.campus import EDGE_KEYS
from app.shade.routing import (
    SHADE_DISCOUNT,
    clear_shade_edge_cache,
    edge_shade_at,
    shade_edge_cache_info,
    shade_fraction_for_line,
    shade_route_between,
)


class ShadeRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_shade_edge_cache()

    def test_line_coverage_counts_overlapping_shadows_once(self) -> None:
        line = LineString(((0, 0), (10, 0)))
        first_shadow = Polygon(((-1, -1), (4, -1), (4, 1), (-1, 1)))
        overlapping_shadow = Polygon(((2, -1), (7, -1), (7, 1), (2, 1)))

        fraction = shade_fraction_for_line(line, (first_shadow, overlapping_shadow))

        self.assertAlmostEqual(fraction, 0.7)
        self.assertEqual(shade_fraction_for_line(line, ()), 0)
        self.assertGreater(1 - SHADE_DISCOUNT * fraction, 0)

    def test_edge_scores_are_direction_independent_and_bounded(self) -> None:
        bucket = edge_shade_at(datetime(2026, 6, 21, 18, tzinfo=timezone.utc))
        edge_key = next(iter(EDGE_KEYS))
        left_id, right_id = tuple(edge_key)

        self.assertIn(frozenset((right_id, left_id)), bucket.edge_fractions)
        self.assertEqual(
            bucket.edge_fractions[edge_key],
            bucket.edge_fractions[frozenset((right_id, left_id))],
        )
        self.assertTrue(all(0 <= fraction <= 1 for fraction in bucket.edge_fractions.values()))

    def test_same_bucket_reuses_cached_edge_scores(self) -> None:
        first = edge_shade_at(datetime(2026, 6, 21, 18, 1, tzinfo=timezone.utc))
        second = edge_shade_at(datetime(2026, 6, 21, 18, 14, tzinfo=timezone.utc))
        next_bucket = edge_shade_at(datetime(2026, 6, 21, 18, 15, tzinfo=timezone.utc))
        cache_info = shade_edge_cache_info()

        self.assertIs(first, second)
        self.assertIsNot(first, next_bucket)
        self.assertEqual(cache_info.hits, 1)
        self.assertEqual(cache_info.misses, 2)

    def test_shadiest_route_trades_a_small_detour_for_more_shade(self) -> None:
        observed_at = datetime(2026, 6, 21, 18, tzinfo=timezone.utc)
        fastest = shade_route_between(
            "zachry",
            "msc",
            preference="fastest",
            observed_at=observed_at,
        )
        shadiest = shade_route_between(
            "zachry",
            "msc",
            preference="shadiest",
            observed_at=observed_at,
        )

        self.assertTrue(fastest.daylight)
        self.assertEqual(fastest.shade_bucket_start, observed_at)
        self.assertNotEqual(fastest.geometry, shadiest.geometry)
        self.assertGreaterEqual(shadiest.distance_m, fastest.distance_m)
        self.assertLess(shadiest.distance_m, fastest.distance_m * 1.25)
        self.assertGreater(shadiest.shaded_distance_m, fastest.shaded_distance_m)
        self.assertGreater(shadiest.shade_percentage, fastest.shade_percentage)
        self.assertLessEqual(shadiest.shade_percentage, 100)

    def test_nighttime_shadiest_route_matches_fastest(self) -> None:
        observed_at = datetime(2026, 6, 22, 6, tzinfo=timezone.utc)
        fastest = shade_route_between(
            "zachry",
            "msc",
            preference="fastest",
            observed_at=observed_at,
        )
        shadiest = shade_route_between(
            "zachry",
            "msc",
            preference="shadiest",
            observed_at=observed_at,
        )

        self.assertFalse(shadiest.daylight)
        self.assertEqual(shadiest.geometry, fastest.geometry)
        self.assertEqual(shadiest.distance_m, fastest.distance_m)
        self.assertEqual(shadiest.shaded_distance_m, 0)
        self.assertEqual(shadiest.shade_percentage, 0)


if __name__ == "__main__":
    unittest.main()
