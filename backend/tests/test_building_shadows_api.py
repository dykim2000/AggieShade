from datetime import datetime, timezone
import unittest

from fastapi import HTTPException
from shapely.geometry import shape

from app.main import get_building_shadow_map, get_building_shadows


class BuildingShadowApiTests(unittest.TestCase):
    def test_daytime_response_contains_metric_building_geometry(self) -> None:
        response = get_building_shadows(datetime.fromisoformat("2026-06-21T13:07:00-05:00"))
        payload = response.model_dump(mode="json")

        self.assertEqual(payload["bucket_start"], "2026-06-21T18:00:00Z")
        self.assertEqual(payload["bucket_minutes"], 15)
        self.assertEqual(payload["crs"], "EPSG:32614")
        self.assertTrue(payload["daylight"])
        self.assertEqual(payload["eligible_building_count"], 109)
        self.assertEqual(payload["excluded_building_count"], 62)
        self.assertEqual(payload["shadow_count"], 109)
        self.assertEqual(
            payload["polygon_count"],
            sum(len(shadow["polygons_m"]) for shadow in payload["shadows"]),
        )
        self.assertGreaterEqual(payload["polygon_count"], payload["shadow_count"])
        self.assertEqual(payload["shadow_length_cap_m"], 100.0)

        shadow = payload["shadows"][0]
        self.assertGreater(shadow["estimated_height_m"], 0)
        self.assertEqual(shadow["height_source"], "floor_count")
        self.assertIn("height_estimated_from_floors", shadow["quality_flags"])
        self.assertGreater(shadow["shadow_length_m"], 0)
        self.assertTrue(shadow["polygons_m"])
        first_ring = shadow["polygons_m"][0][0]
        self.assertEqual(first_ring[0], first_ring[-1])
        self.assertIn("easting", first_ring[0])
        self.assertIn("northing", first_ring[0])
        self.assertGreater(first_ring[0]["easting"], 700_000)
        self.assertGreater(first_ring[0]["northing"], 3_000_000)

    def test_nighttime_response_has_counts_but_no_geometry(self) -> None:
        response = get_building_shadows(datetime(2026, 6, 22, 6, tzinfo=timezone.utc))

        self.assertFalse(response.daylight)
        self.assertIsNone(response.shadow_azimuth_degrees)
        self.assertEqual(response.eligible_building_count, 109)
        self.assertEqual(response.excluded_building_count, 62)
        self.assertEqual(response.shadow_count, 0)
        self.assertEqual(response.polygon_count, 0)
        self.assertEqual(response.maximum_generated_shadow_length_m, 0)
        self.assertEqual(response.shadows, [])

    def test_map_response_is_valid_topology_preserving_wgs84_geojson(self) -> None:
        response = get_building_shadow_map(
            datetime(2026, 6, 21, 18, tzinfo=timezone.utc)
        )
        payload = response.model_dump(mode="json")

        self.assertEqual(payload["bucket_start"], "2026-06-21T18:00:00Z")
        self.assertEqual(payload["bucket_minutes"], 15)
        self.assertTrue(payload["daylight"])
        self.assertEqual(payload["eligible_building_count"], 109)
        self.assertEqual(payload["excluded_building_count"], 62)
        self.assertEqual(payload["shadow_count"], 109)
        self.assertEqual(payload["geojson"]["type"], "FeatureCollection")

        features = payload["geojson"]["features"]
        self.assertEqual(len(features), 109)
        self.assertEqual(
            payload["polygon_count"],
            sum(len(feature["geometry"]["coordinates"]) for feature in features),
        )
        self.assertTrue(all(feature["type"] == "Feature" for feature in features))
        self.assertTrue(
            all(feature["geometry"]["type"] == "MultiPolygon" for feature in features)
        )
        self.assertTrue(
            all(shape(feature["geometry"]).is_valid for feature in features),
            "every map-ready building shadow should be valid GeoJSON geometry",
        )

        first_ring = features[0]["geometry"]["coordinates"][0][0]
        self.assertEqual(first_ring[0], first_ring[-1])
        self.assertTrue(
            all(
                -96.36 < longitude < -96.32 and 30.59 < latitude < 30.64
                for longitude, latitude in first_ring
            )
        )
        self.assertTrue(
            any(
                len(polygon) > 1
                for feature in features
                for polygon in feature["geometry"]["coordinates"]
            ),
            "at least one courtyard hole should survive GeoJSON conversion",
        )

    def test_naive_timestamp_returns_bad_request(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_building_shadows(datetime(2026, 6, 21, 13))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("UTC offset", raised.exception.detail)

        with self.assertRaises(HTTPException) as map_raised:
            get_building_shadow_map(datetime(2026, 6, 21, 13))
        self.assertEqual(map_raised.exception.status_code, 400)
        self.assertIn("UTC offset", map_raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
