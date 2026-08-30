from datetime import datetime, timedelta, timezone
import unittest

from app.shade.solar import (
    SOLAR_REFERENCE_URL,
    solar_position,
    time_bucket_start,
)


class SolarPositionTests(unittest.TestCase):
    def test_matches_noaa_college_station_reference_values(self) -> None:
        # NOAA Solar Geometry Calculator results, uncorrected for refraction.
        # https://gml.noaa.gov/grad/antuv/SolarCalc.jsp
        reference_values = (
            ("2026-06-21T12:00:00+00:00", 6.26498, 66.42480),
            ("2026-06-21T18:00:00+00:00", 80.59973, 138.22519),
            ("2026-06-22T00:00:00+00:00", 17.24100, 287.46865),
            ("2026-06-22T06:00:00+00:00", -35.54974, 352.28348),
        )

        for stamp, expected_altitude, expected_azimuth in reference_values:
            with self.subTest(stamp=stamp):
                position = solar_position(datetime.fromisoformat(stamp))
                self.assertAlmostEqual(
                    position.geometric_altitude_degrees,
                    expected_altitude,
                    delta=0.55,
                )
                self.assertAlmostEqual(position.azimuth_degrees, expected_azimuth, delta=0.55)

    def test_same_instant_is_independent_of_input_offset(self) -> None:
        utc_time = datetime(2026, 6, 21, 18, tzinfo=timezone.utc)
        central_daylight_time = datetime(
            2026,
            6,
            21,
            13,
            tzinfo=timezone(timedelta(hours=-5)),
        )
        self.assertEqual(solar_position(utc_time), solar_position(central_daylight_time))

    def test_bucket_start_is_utc_and_floored_to_fifteen_minutes(self) -> None:
        observed_at = datetime(
            2026,
            8,
            30,
            10,
            23,
            59,
            tzinfo=timezone(timedelta(hours=-5)),
        )
        self.assertEqual(
            time_bucket_start(observed_at),
            datetime(2026, 8, 30, 15, 15, tzinfo=timezone.utc),
        )

    def test_daylight_position_points_shadow_away_from_sun(self) -> None:
        position = solar_position(datetime(2026, 6, 21, 18, tzinfo=timezone.utc))
        self.assertTrue(position.daylight)
        self.assertIsNotNone(position.shadow_azimuth_degrees)
        self.assertAlmostEqual(
            position.shadow_azimuth_degrees,
            (position.azimuth_degrees + 180) % 360,
            places=4,
        )
        self.assertGreater(position.apparent_altitude_degrees, position.geometric_altitude_degrees)

    def test_nighttime_has_no_shadow_direction(self) -> None:
        position = solar_position(datetime(2026, 6, 22, 6, tzinfo=timezone.utc))
        self.assertFalse(position.daylight)
        self.assertLess(position.apparent_altitude_degrees, 0)
        self.assertIsNone(position.shadow_azimuth_degrees)

    def test_timestamp_must_be_timezone_aware_and_in_supported_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "UTC offset"):
            solar_position(datetime(2026, 6, 21, 12))
        with self.assertRaisesRegex(ValueError, "between 1800 and 2100"):
            solar_position(datetime(2200, 6, 21, 12, tzinfo=timezone.utc))

    def test_coordinates_and_bucket_size_are_validated(self) -> None:
        observed_at = datetime(2026, 6, 21, 12, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "latitude"):
            solar_position(observed_at, latitude=91)
        with self.assertRaisesRegex(ValueError, "longitude"):
            solar_position(observed_at, longitude=-181)
        with self.assertRaisesRegex(ValueError, "divisor of 60"):
            time_bucket_start(observed_at, bucket_minutes=7)

    def test_result_names_the_published_method(self) -> None:
        position = solar_position(datetime(2026, 6, 21, 18, tzinfo=timezone.utc))
        self.assertIn("NOAA", position.method)
        self.assertTrue(SOLAR_REFERENCE_URL.startswith("https://"))


if __name__ == "__main__":
    unittest.main()
