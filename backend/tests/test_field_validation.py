from copy import deepcopy
import json
from pathlib import Path
import unittest

from app.field_validation import validate_field_dataset


EXAMPLE_PATH = Path(__file__).parents[2] / "field_validation" / "example_observations.json"


class FieldValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    def test_example_dataset_is_valid(self) -> None:
        validate_field_dataset(self.dataset)

    def test_timestamps_must_include_timezone(self) -> None:
        dataset = deepcopy(self.dataset)
        dataset["observations"][0]["observed_at"] = "2026-09-02T13:15:00"
        with self.assertRaisesRegex(ValueError, "timezone offset"):
            validate_field_dataset(dataset)

    def test_fractions_must_be_between_zero_and_one(self) -> None:
        dataset = deepcopy(self.dataset)
        dataset["observations"][1]["observed"]["shade_fraction"] = 1.1
        with self.assertRaisesRegex(ValueError, "at most 1"):
            validate_field_dataset(dataset)

    def test_observation_ids_must_be_unique(self) -> None:
        dataset = deepcopy(self.dataset)
        dataset["observations"][1]["observation_id"] = dataset["observations"][0]["observation_id"]
        with self.assertRaisesRegex(ValueError, "duplicate observation_id"):
            validate_field_dataset(dataset)


if __name__ == "__main__":
    unittest.main()
