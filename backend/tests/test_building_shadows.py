from datetime import datetime, timezone
import unittest

from shapely.geometry import MultiPolygon, Polygon

from app.shade.buildings import (
    EXCLUDED_BUILDING_COUNT,
    MAX_BUILDING_SHADOW_LENGTH_M,
    SHADE_READY_BUILDINGS,
    building_shadow_cache_info,
    building_shadows_at,
    clear_building_shadow_cache,
    shade_ready_buildings_from_dataset,
    swept_footprint,
)


class BuildingShadowTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_building_shadow_cache()

    def test_loads_every_shade_ready_building_from_snapshot(self) -> None:
        self.assertEqual(len(SHADE_READY_BUILDINGS), 109)
        self.assertEqual(EXCLUDED_BUILDING_COUNT, 62)
        self.assertEqual(
            len({building.source_id for building in SHADE_READY_BUILDINGS}),
            109,
        )
        self.assertTrue(all(building.height_m > 0 for building in SHADE_READY_BUILDINGS))
        self.assertTrue(
            all(
                isinstance(building.footprint, (Polygon, MultiPolygon))
                and building.footprint.is_valid
                and not building.footprint.is_empty
                for building in SHADE_READY_BUILDINGS
            )
        )

    def test_snapshot_preserves_multipart_buildings_and_courtyard_holes(self) -> None:
        multipart = next(
            building for building in SHADE_READY_BUILDINGS if building.source_id == 177
        )
        courtyard = next(
            building for building in SHADE_READY_BUILDINGS if building.source_id == 500
        )

        self.assertIsInstance(multipart.footprint, MultiPolygon)
        self.assertEqual(len(multipart.footprint.geoms), 4)
        self.assertIsInstance(courtyard.footprint, Polygon)
        self.assertEqual(len(courtyard.footprint.interiors), 1)

    def test_loader_reconstructs_ring_topology_and_excludes_bad_records(self) -> None:
        outer = [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]
        hole = [[2, 2], [4, 2], [4, 4], [2, 4], [2, 2]]
        second_part = [[20, 0], [20, 2], [22, 2], [22, 0], [20, 0]]
        dataset = {
            "buildings": [
                {
                    "source_id": "complex",
                    "estimated_height_m": 10,
                    "height_source": "floor_count",
                    "footprint_m": [outer, hole, second_part],
                    "footprint_wgs84": [outer, hole, second_part],
                    "shade_ready": True,
                    "quality_flags": ["height_estimated_from_floors"],
                },
                {
                    "source_id": "missing-height",
                    "estimated_height_m": None,
                    "height_source": None,
                    "footprint_m": [outer],
                    "footprint_wgs84": [outer],
                    "shade_ready": True,
                    "quality_flags": ["missing_floor_count"],
                },
                {
                    "source_id": "not-ready",
                    "estimated_height_m": 10,
                    "height_source": "floor_count",
                    "footprint_m": [outer],
                    "footprint_wgs84": [outer],
                    "shade_ready": False,
                    "quality_flags": [],
                },
                {
                    "source_id": "invalid-geometry",
                    "estimated_height_m": 10,
                    "height_source": "floor_count",
                    "footprint_m": [[[0, 0], [1, 1]]],
                    "footprint_wgs84": [[[0, 0], [1, 1]]],
                    "shade_ready": True,
                    "quality_flags": ["invalid_geometry"],
                },
            ]
        }

        buildings, excluded_count = shade_ready_buildings_from_dataset(dataset)

        self.assertEqual(len(buildings), 1)
        self.assertEqual(excluded_count, 3)
        building = buildings[0]
        self.assertEqual(building.source_id, "complex")
        self.assertEqual(building.height_m, 10)
        self.assertEqual(building.height_source, "floor_count")
        self.assertEqual(building.quality_flags, ("height_estimated_from_floors",))
        self.assertIsInstance(building.footprint, MultiPolygon)
        self.assertEqual(len(building.footprint.geoms), 2)
        self.assertEqual(sum(len(part.interiors) for part in building.footprint.geoms), 1)
        self.assertAlmostEqual(building.footprint.area, 100)

    def test_sweeps_square_exactly_in_shadow_direction(self) -> None:
        footprint = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        expected = Polygon([(0, 0), (5, 0), (5, 2), (0, 2)])

        geometry = swept_footprint(
            footprint,
            shadow_length_m=3,
            shadow_azimuth_degrees=90,
        )

        self.assertTrue(geometry.equals(expected))
        self.assertEqual(geometry.bounds, (0, 0, 5, 2))
        self.assertAlmostEqual(geometry.area, 10)

    def test_sweep_preserves_the_unshadowed_part_of_a_courtyard(self) -> None:
        footprint = Polygon(
            [(0, 0), (10, 0), (10, 10), (0, 10)],
            holes=[[(3, 3), (7, 3), (7, 7), (3, 7)]],
        )
        expected = Polygon(
            [(0, 0), (12, 0), (12, 10), (0, 10)],
            holes=[[(5, 3), (7, 3), (7, 7), (5, 7)]],
        )

        geometry = swept_footprint(
            footprint,
            shadow_length_m=2,
            shadow_azimuth_degrees=90,
        )

        self.assertTrue(geometry.equals(expected))
        self.assertEqual(len(geometry.interiors), 1)
        self.assertAlmostEqual(geometry.area, 112)

    def test_morning_midday_and_evening_change_length_and_direction(self) -> None:
        morning = building_shadows_at(datetime(2026, 6, 21, 12, tzinfo=timezone.utc))
        midday = building_shadows_at(datetime(2026, 6, 21, 18, tzinfo=timezone.utc))
        evening = building_shadows_at(datetime(2026, 6, 22, 0, tzinfo=timezone.utc))

        morning_shadow = morning.shadows[0]
        midday_shadow = midday.shadows[0]
        evening_shadow = evening.shadows[0]
        self.assertGreater(morning_shadow.shadow_length_m, midday_shadow.shadow_length_m)
        self.assertGreater(evening_shadow.shadow_length_m, midday_shadow.shadow_length_m)

        morning_bounds = morning_shadow.geometry.bounds
        midday_bounds = midday_shadow.geometry.bounds
        evening_bounds = evening_shadow.geometry.bounds
        footprint_bounds = morning_shadow.footprint_bounds
        self.assertLess(morning_bounds[0], footprint_bounds[0])
        self.assertLess(morning_bounds[1], footprint_bounds[1])
        self.assertLess(midday_bounds[0], footprint_bounds[0])
        self.assertGreater(midday_bounds[3], footprint_bounds[3])
        self.assertGreater(evening_bounds[2], footprint_bounds[2])
        self.assertLess(evening_bounds[1], footprint_bounds[1])

    def test_nighttime_returns_no_building_shadow_geometry(self) -> None:
        bucket = building_shadows_at(datetime(2026, 6, 22, 6, tzinfo=timezone.utc))

        self.assertFalse(bucket.solar.daylight)
        self.assertIsNone(bucket.solar.shadow_azimuth_degrees)
        self.assertEqual(bucket.shadows, ())
        self.assertEqual(bucket.eligible_building_count, 109)
        self.assertEqual(bucket.excluded_building_count, 62)

    def test_near_horizon_lengths_are_capped(self) -> None:
        bucket = building_shadows_at(datetime(2026, 6, 21, 12, tzinfo=timezone.utc))

        self.assertTrue(any(shadow.length_capped for shadow in bucket.shadows))
        self.assertLessEqual(
            max(shadow.shadow_length_m for shadow in bucket.shadows),
            MAX_BUILDING_SHADOW_LENGTH_M,
        )

    def test_timestamps_in_same_bucket_reuse_cached_geometry(self) -> None:
        first = building_shadows_at(datetime(2026, 6, 21, 18, 1, tzinfo=timezone.utc))
        second = building_shadows_at(datetime(2026, 6, 21, 18, 14, tzinfo=timezone.utc))
        cache_info = building_shadow_cache_info()

        self.assertIs(first, second)
        self.assertEqual(first.bucket_start, datetime(2026, 6, 21, 18, tzinfo=timezone.utc))
        self.assertEqual(cache_info.misses, 1)
        self.assertEqual(cache_info.hits, 1)


if __name__ == "__main__":
    unittest.main()
