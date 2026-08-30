from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import unittest

from app.gis.tamu import (
    ArcGISClient,
    ArcGISError,
    BUILDING_FIELDS,
    DEFAULT_CAMPUS_BBOX,
    TREE_FIELDS,
    build_shade_dataset,
    wgs84_to_utm14,
)


FIXTURE_PATH = Path(__file__).with_name("fixtures") / "tamu_tiny.json"


class ArcGISClientTests(unittest.TestCase):
    def test_fetch_features_paginates_and_preserves_query_bounds(self) -> None:
        requested_offsets: list[str] = []

        def transport(url: str) -> bytes:
            query = parse_qs(urlparse(url).query)
            requested_offsets.append(query["resultOffset"][0])
            self.assertEqual(query["geometry"][0], ",".join(str(value) for value in DEFAULT_CAMPUS_BBOX))
            self.assertEqual(query["outSR"][0], "4326")
            offset = int(query["resultOffset"][0])
            if offset == 0:
                payload = {
                    "features": [
                        {"attributes": {"OBJECTID": 1}},
                        {"attributes": {"OBJECTID": 2}},
                    ],
                    "exceededTransferLimit": True,
                }
            else:
                payload = {"features": [{"attributes": {"OBJECTID": 3}}]}
            return json.dumps(payload).encode()

        client = ArcGISClient(transport=transport, page_size=2)
        features = client.fetch_features(4, TREE_FIELDS)

        self.assertEqual([feature["attributes"]["OBJECTID"] for feature in features], [1, 2, 3])
        self.assertEqual(requested_offsets, ["0", "2"])

    def test_fetch_features_rejects_arcgis_errors(self) -> None:
        client = ArcGISClient(transport=lambda _url: b'{"error":{"message":"Layer unavailable"}}')
        with self.assertRaisesRegex(ArcGISError, "Layer unavailable"):
            client.fetch_features(2, BUILDING_FIELDS)

    def test_fetch_features_rejects_invalid_bbox(self) -> None:
        client = ArcGISClient(transport=lambda _url: b"{}")
        with self.assertRaises(ValueError):
            client.fetch_features(4, TREE_FIELDS, (-96.3, 30.6, -96.4, 30.7))


class TamuNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.dataset = build_shade_dataset(
            cls.fixture["trees"],
            cls.fixture["buildings"],
            generated_at=datetime(2026, 8, 30, 15, 0, tzinfo=timezone.utc),
        )

    def test_utm_projection_uses_metric_zone_14_coordinates(self) -> None:
        self.assertEqual(wgs84_to_utm14(-99, 0), (500000.0, 0.0))
        easting, northing = wgs84_to_utm14(-96.3408, 30.6214)
        self.assertGreater(easting, 750_000)
        self.assertLess(easting, 760_000)
        self.assertGreater(northing, 3_390_000)
        self.assertLess(northing, 3_400_000)

        # Cross-checked against TAMU ArcGIS with outSR=32614 for tree OBJECTID 1.
        easting, northing = wgs84_to_utm14(-96.330805123295079, 30.622790451569642)
        self.assertAlmostEqual(easting, 755_859.875963, places=3)
        self.assertAlmostEqual(northing, 3_390_836.050557, places=3)

    def test_tree_dimensions_are_normalized_to_meters(self) -> None:
        tree = self.dataset["trees"][0]
        self.assertEqual(tree["height_m"], 12.192)
        self.assertEqual(tree["canopy_diameter_m"], 6.096)
        self.assertEqual(tree["canopy_radius_m"], 3.048)
        self.assertTrue(tree["shade_ready"])
        self.assertEqual(tree["quality_flags"], [])
        self.assertEqual(len(tree["point_m"]), 2)

    def test_unusable_trees_keep_explanatory_quality_flags(self) -> None:
        dead_tree = self.dataset["trees"][1]
        removed_tree = self.dataset["trees"][2]
        self.assertFalse(dead_tree["shade_ready"])
        self.assertEqual(dead_tree["quality_flags"], ["missing_height", "missing_canopy_spread", "dead"])
        self.assertFalse(removed_tree["shade_ready"])
        self.assertIn("health_unknown", removed_tree["quality_flags"])
        self.assertIn("status_unknown", removed_tree["quality_flags"])
        self.assertIn("removed", removed_tree["quality_flags"])

    def test_building_height_is_estimated_from_floor_count(self) -> None:
        building = self.dataset["buildings"][0]
        self.assertEqual(building["name"], "Zachry Engineering Education Complex")
        self.assertEqual(building["building_number"], "0518")
        self.assertEqual(building["estimated_height_m"], 17.5)
        self.assertEqual(building["height_source"], "floor_count")
        self.assertTrue(building["shade_ready"])
        self.assertEqual(building["footprint_wgs84"][0][0], building["footprint_wgs84"][0][-1])

    def test_missing_values_are_not_silently_imputed(self) -> None:
        missing_floor = self.dataset["buildings"][1]
        invalid_geometry = self.dataset["buildings"][2]
        self.assertIsNone(missing_floor["estimated_height_m"])
        self.assertEqual(missing_floor["quality_flags"], ["missing_floor_count"])
        self.assertFalse(missing_floor["shade_ready"])
        self.assertIn("invalid_geometry", invalid_geometry["quality_flags"])
        self.assertFalse(invalid_geometry["shade_ready"])

    def test_dataset_includes_provenance_assumptions_and_summary(self) -> None:
        self.assertEqual(self.dataset["generated_at"], "2026-08-30T15:00:00Z")
        self.assertEqual(self.dataset["source"]["target_metric_crs"], "EPSG:32614")
        self.assertEqual(self.dataset["assumptions"]["tree_dimension_source_unit"], "feet")
        self.assertIn("does not declare units", self.dataset["assumptions"]["tree_dimension_unit_status"])
        self.assertEqual(
            self.dataset["summary"],
            {
                "tree_count": 3,
                "shade_ready_tree_count": 1,
                "building_count": 3,
                "shade_ready_building_count": 1,
                "tree_quality_flags": {
                    "dead": 1,
                    "health_unknown": 1,
                    "missing_canopy_spread": 1,
                    "missing_height": 1,
                    "removed": 1,
                    "status_unknown": 1,
                },
                "building_quality_flags": {
                    "height_estimated_from_floors": 2,
                    "invalid_geometry": 1,
                    "missing_floor_count": 1,
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
