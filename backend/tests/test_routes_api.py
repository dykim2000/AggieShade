from datetime import datetime, timezone
import unittest

from fastapi import HTTPException
from pydantic import ValidationError

from app.main import create_route
from app.models import RouteRequest


class RoutesApiTests(unittest.TestCase):
    def test_route_response_includes_time_aware_shade_metrics(self) -> None:
        response = create_route(
            RouteRequest(
                origin_id="zachry",
                destination_id="msc",
                preference="shadiest",
                at=datetime(2026, 6, 21, 18, 7, tzinfo=timezone.utc),
            )
        )
        payload = response.model_dump(mode="json")

        self.assertEqual(payload["preference"], "shadiest")
        self.assertEqual(payload["shade_bucket_start"], "2026-06-21T18:00:00Z")
        self.assertTrue(payload["daylight"])
        self.assertGreater(payload["shaded_distance_m"], 0)
        self.assertGreater(payload["shade_percentage"], 0)
        self.assertLessEqual(payload["shade_percentage"], 100)
        self.assertGreater(len(payload["geometry"]), 10)

    def test_route_rejects_a_naive_timestamp(self) -> None:
        request = RouteRequest(
            origin_id="zachry",
            destination_id="msc",
            preference="shadiest",
            at=datetime(2026, 6, 21, 13),
        )

        with self.assertRaises(HTTPException) as raised:
            create_route(request)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("UTC offset", raised.exception.detail)

    def test_route_rejects_unknown_or_identical_buildings(self) -> None:
        observed_at = datetime(2026, 6, 21, 18, tzinfo=timezone.utc)
        with self.assertRaises(HTTPException) as unknown:
            create_route(
                RouteRequest(
                    origin_id="not-a-building",
                    destination_id="msc",
                    preference="fastest",
                    at=observed_at,
                )
            )
        self.assertEqual(unknown.exception.status_code, 404)

        with self.assertRaises(HTTPException) as identical:
            create_route(
                RouteRequest(
                    origin_id="msc",
                    destination_id="msc",
                    preference="fastest",
                    at=observed_at,
                )
            )
        self.assertEqual(identical.exception.status_code, 400)

        with self.assertRaises(HTTPException) as shared_access:
            create_route(
                RouteRequest(
                    origin_id="tamu-1427",
                    destination_id="tamu-0426",
                    preference="shadiest",
                    at=observed_at,
                )
            )
        self.assertEqual(shared_access.exception.status_code, 422)
        self.assertIn("same pedestrian access point", shared_access.exception.detail)

    def test_route_preference_is_validated(self) -> None:
        with self.assertRaises(ValidationError):
            RouteRequest.model_validate(
                {
                    "origin_id": "zachry",
                    "destination_id": "msc",
                    "preference": "coolest-sounding",
                    "at": "2026-06-21T18:00:00Z",
                }
            )


if __name__ == "__main__":
    unittest.main()
