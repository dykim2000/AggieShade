from datetime import datetime, timezone
import unittest

from app.shade.trees import (
    EXCLUDED_TREE_COUNT,
    MAX_TREE_SHADOW_LENGTH_M,
    SHADE_READY_TREES,
    clear_tree_shadow_cache,
    shade_ready_trees_from_dataset,
    tree_shadow_cache_info,
    tree_shadow_polygon,
    tree_shadows_at,
)


class TreeShadowTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_tree_shadow_cache()

    def test_loads_every_shade_ready_tree_from_snapshot(self) -> None:
        self.assertEqual(len(SHADE_READY_TREES), 2_058)
        self.assertEqual(EXCLUDED_TREE_COUNT, 829)
        self.assertEqual(len({tree.source_id for tree in SHADE_READY_TREES}), 2_058)
        self.assertTrue(all(tree.height_m > 0 for tree in SHADE_READY_TREES))
        self.assertTrue(all(tree.canopy_radius_m > 0 for tree in SHADE_READY_TREES))

    def test_missing_or_invalid_tree_data_is_excluded(self) -> None:
        dataset = {
            "trees": [
                {
                    "source_id": 1,
                    "point_m": [100.0, 200.0],
                    "height_m": 8.0,
                    "canopy_radius_m": 2.0,
                    "shade_ready": True,
                },
                {
                    "source_id": 2,
                    "point_m": [101.0, 201.0],
                    "height_m": None,
                    "canopy_radius_m": 2.0,
                    "shade_ready": True,
                },
                {
                    "source_id": 3,
                    "point_m": [102.0, 202.0],
                    "height_m": 8.0,
                    "canopy_radius_m": 2.0,
                    "shade_ready": False,
                },
            ]
        }

        trees, excluded_count = shade_ready_trees_from_dataset(dataset)

        self.assertEqual(len(trees), 1)
        self.assertEqual(trees[0].source_id, 1)
        self.assertEqual(excluded_count, 2)

    def test_canopy_projection_is_a_closed_metric_capsule(self) -> None:
        polygon = tree_shadow_polygon(
            center_m=(0.0, 0.0),
            canopy_radius_m=2.0,
            shadow_length_m=10.0,
            shadow_azimuth_degrees=90.0,
        )

        self.assertEqual(polygon[0], polygon[-1])
        self.assertEqual(len(polygon), 19)
        self.assertAlmostEqual(min(point[0] for point in polygon), -2.0, places=3)
        self.assertAlmostEqual(max(point[0] for point in polygon), 12.0, places=3)
        self.assertAlmostEqual(min(point[1] for point in polygon), -2.0, places=3)
        self.assertAlmostEqual(max(point[1] for point in polygon), 2.0, places=3)

    def test_morning_midday_and_evening_change_length_and_direction(self) -> None:
        morning = tree_shadows_at(datetime(2026, 6, 21, 12, tzinfo=timezone.utc))
        midday = tree_shadows_at(datetime(2026, 6, 21, 18, tzinfo=timezone.utc))
        evening = tree_shadows_at(datetime(2026, 6, 22, 0, tzinfo=timezone.utc))

        morning_shadow = morning.shadows[0]
        midday_shadow = midday.shadows[0]
        evening_shadow = evening.shadows[0]
        self.assertGreater(morning_shadow.shadow_length_m, midday_shadow.shadow_length_m)
        self.assertGreater(evening_shadow.shadow_length_m, midday_shadow.shadow_length_m)

        morning_offset = self._polygon_mean_offset(morning_shadow.polygon_m, morning_shadow.center_m)
        midday_offset = self._polygon_mean_offset(midday_shadow.polygon_m, midday_shadow.center_m)
        evening_offset = self._polygon_mean_offset(evening_shadow.polygon_m, evening_shadow.center_m)
        self.assertLess(morning_offset[0], 0)
        self.assertLess(morning_offset[1], 0)
        self.assertLess(midday_offset[0], 0)
        self.assertGreater(midday_offset[1], 0)
        self.assertGreater(evening_offset[0], 0)
        self.assertLess(evening_offset[1], 0)

    def test_nighttime_returns_no_shadow_polygons(self) -> None:
        bucket = tree_shadows_at(datetime(2026, 6, 22, 6, tzinfo=timezone.utc))

        self.assertFalse(bucket.solar.daylight)
        self.assertIsNone(bucket.solar.shadow_azimuth_degrees)
        self.assertEqual(bucket.shadows, ())
        self.assertEqual(bucket.eligible_tree_count, 2_058)

    def test_near_horizon_lengths_are_capped(self) -> None:
        bucket = tree_shadows_at(datetime(2026, 6, 21, 12, tzinfo=timezone.utc))

        self.assertTrue(any(shadow.length_capped for shadow in bucket.shadows))
        self.assertLessEqual(
            max(shadow.shadow_length_m for shadow in bucket.shadows),
            MAX_TREE_SHADOW_LENGTH_M,
        )

    def test_timestamps_in_same_bucket_reuse_cached_geometry(self) -> None:
        first = tree_shadows_at(datetime(2026, 6, 21, 18, 1, tzinfo=timezone.utc))
        second = tree_shadows_at(datetime(2026, 6, 21, 18, 14, tzinfo=timezone.utc))
        cache_info = tree_shadow_cache_info()

        self.assertIs(first, second)
        self.assertEqual(first.bucket_start, datetime(2026, 6, 21, 18, tzinfo=timezone.utc))
        self.assertEqual(cache_info.misses, 1)
        self.assertEqual(cache_info.hits, 1)

    @staticmethod
    def _polygon_mean_offset(
        polygon: tuple[tuple[float, float], ...],
        center: tuple[float, float],
    ) -> tuple[float, float]:
        points = polygon[:-1]
        return (
            sum(point[0] - center[0] for point in points) / len(points),
            sum(point[1] - center[1] for point in points) / len(points),
        )


if __name__ == "__main__":
    unittest.main()
