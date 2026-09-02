import json
from pathlib import Path
import unittest

from app.field_analysis import analyze_field_dataset, bearing_error_degrees, percent_error


SYNTHETIC_PATH = Path(__file__).parents[2] / "field_validation" / "synthetic_observations.json"


class FieldAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = json.loads(SYNTHETIC_PATH.read_text(encoding="utf-8"))

    def test_bearing_error_wraps_around_north(self) -> None:
        self.assertEqual(bearing_error_degrees(358, 2), 4)
        self.assertEqual(bearing_error_degrees(10, 350), 20)

    def test_percent_error_handles_zero_observation(self) -> None:
        self.assertIsNone(percent_error(0, 4))
        self.assertEqual(percent_error(100, 90), 10)

    def test_synthetic_dataset_produces_known_summary(self) -> None:
        report = analyze_field_dataset(self.dataset)

        self.assertEqual(report["observation_count"], 4)
        self.assertEqual(report["shadow_summary"]["count"], 2)
        self.assertEqual(report["shadow_summary"]["mean_absolute_bearing_error_degrees"], 7.0)
        self.assertEqual(report["shadow_summary"]["mean_absolute_length_error_m"], 2.0)
        self.assertEqual(report["shadow_summary"]["mean_absolute_length_error_percent"], 15.0)
        self.assertEqual(
            report["shadow_summary"]["mean_absolute_walkway_shade_error_percentage_points"], 7.5
        )
        self.assertEqual(report["route_summary"]["count"], 2)
        self.assertEqual(report["route_summary"]["mean_absolute_distance_error_m"], 75.0)
        self.assertEqual(report["route_summary"]["mean_absolute_duration_error_seconds"], 75.0)
        self.assertEqual(report["route_summary"]["mean_absolute_shade_error_percentage_points"], 7.5)


if __name__ == "__main__":
    unittest.main()
