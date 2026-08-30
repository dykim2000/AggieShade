from datetime import datetime
import unittest

from fastapi import HTTPException

from app.main import get_solar_position


class SolarPositionApiTests(unittest.TestCase):
    def test_response_uses_utc_and_exposes_shadow_contract(self) -> None:
        response = get_solar_position(datetime.fromisoformat("2026-06-21T13:00:00-05:00"))
        payload = response.model_dump(mode="json")

        self.assertEqual(payload["observed_at"], "2026-06-21T18:00:00Z")
        self.assertEqual(payload["bucket_start"], "2026-06-21T18:00:00Z")
        self.assertTrue(payload["daylight"])
        self.assertIsNotNone(payload["shadow_azimuth_degrees"])
        self.assertIn("NOAA", payload["method"])
        self.assertTrue(payload["reference_url"].startswith("https://"))

    def test_naive_timestamp_returns_bad_request(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_solar_position(datetime(2026, 6, 21, 13))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("UTC offset", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
