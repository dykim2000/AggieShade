from datetime import datetime, timezone
import unittest

from fastapi import HTTPException

from app.main import get_tree_shadows


class TreeShadowApiTests(unittest.TestCase):
    def test_daytime_response_contains_metric_tree_polygons(self) -> None:
        response = get_tree_shadows(datetime.fromisoformat("2026-06-21T13:07:00-05:00"))
        payload = response.model_dump(mode="json")

        self.assertEqual(payload["bucket_start"], "2026-06-21T18:00:00Z")
        self.assertEqual(payload["bucket_minutes"], 15)
        self.assertEqual(payload["crs"], "EPSG:32614")
        self.assertTrue(payload["daylight"])
        self.assertEqual(payload["eligible_tree_count"], 2_058)
        self.assertEqual(payload["excluded_tree_count"], 829)
        self.assertEqual(payload["shadow_count"], 2_058)
        self.assertEqual(payload["shadow_length_cap_m"], 100.0)

        shadow = payload["shadows"][0]
        self.assertGreater(shadow["height_m"], 0)
        self.assertGreater(shadow["canopy_radius_m"], 0)
        self.assertGreater(shadow["shadow_length_m"], 0)
        self.assertEqual(shadow["polygon_m"][0], shadow["polygon_m"][-1])
        self.assertIn("easting", shadow["polygon_m"][0])
        self.assertIn("northing", shadow["polygon_m"][0])

    def test_nighttime_response_is_empty(self) -> None:
        response = get_tree_shadows(datetime(2026, 6, 22, 6, tzinfo=timezone.utc))

        self.assertFalse(response.daylight)
        self.assertIsNone(response.shadow_azimuth_degrees)
        self.assertEqual(response.shadow_count, 0)
        self.assertEqual(response.shadows, [])
        self.assertEqual(response.maximum_generated_shadow_length_m, 0)

    def test_naive_timestamp_returns_bad_request(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_tree_shadows(datetime(2026, 6, 21, 13))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("UTC offset", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
