"""Approximate solar position for campus shade calculations.

The implementation follows NOAA Global Monitoring Laboratory's published
general solar-position equations.  They are appropriate for the prototype's
15-minute time buckets; higher-precision astronomy can replace this module
behind the same result contract if field validation shows that it is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import acos, atan2, cos, degrees, pi, radians, sin, tan


TAMU_LATITUDE = 30.6214
TAMU_LONGITUDE = -96.3408
TIME_BUCKET_MINUTES = 15
SUPPORTED_YEAR_RANGE = (1800, 2100)
SOLAR_METHOD = "NOAA GML approximate solar equations"
SOLAR_REFERENCE_URL = "https://www.gml.noaa.gov/grad/solcalc/solareqns.PDF"


@dataclass(frozen=True)
class SolarPosition:
    observed_at: datetime
    bucket_start: datetime
    latitude: float
    longitude: float
    geometric_altitude_degrees: float
    apparent_altitude_degrees: float
    azimuth_degrees: float
    shadow_azimuth_degrees: float | None
    daylight: bool
    method: str = SOLAR_METHOD


def _validate_timestamp(observed_at: datetime) -> datetime:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must include a UTC offset")
    observed_at_utc = observed_at.astimezone(timezone.utc)
    first_year, last_year = SUPPORTED_YEAR_RANGE
    if not first_year <= observed_at_utc.year <= last_year:
        raise ValueError(f"observed_at year must be between {first_year} and {last_year}")
    return observed_at_utc


def time_bucket_start(observed_at: datetime, bucket_minutes: int = TIME_BUCKET_MINUTES) -> datetime:
    """Return the inclusive UTC start of the timestamp's cache bucket."""

    if bucket_minutes < 1 or 60 % bucket_minutes != 0:
        raise ValueError("bucket_minutes must be a positive divisor of 60")
    observed_at_utc = _validate_timestamp(observed_at)
    minute = observed_at_utc.minute - observed_at_utc.minute % bucket_minutes
    return observed_at_utc.replace(minute=minute, second=0, microsecond=0)


def _atmospheric_refraction_degrees(geometric_altitude_degrees: float) -> float:
    """NOAA's standard approximate refraction correction for solar elevation."""

    altitude = geometric_altitude_degrees
    if altitude > 85:
        return 0.0
    if altitude > 5:
        tangent = tan(radians(altitude))
        correction_arcseconds = 58.1 / tangent - 0.07 / tangent**3 + 0.000086 / tangent**5
    elif altitude > -0.575:
        correction_arcseconds = (
            1735
            - 518.2 * altitude
            + 103.4 * altitude**2
            - 12.79 * altitude**3
            + 0.711 * altitude**4
        )
    else:
        correction_arcseconds = -20.774 / tan(radians(altitude))
    return correction_arcseconds / 3600


def solar_position(
    observed_at: datetime,
    *,
    latitude: float = TAMU_LATITUDE,
    longitude: float = TAMU_LONGITUDE,
) -> SolarPosition:
    """Calculate solar altitude and azimuth for a timezone-aware instant.

    Longitude follows the standard east-positive convention, so College
    Station is negative. Azimuth is degrees clockwise from true north.
    """

    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90 degrees")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180 degrees")

    observed_at_utc = _validate_timestamp(observed_at)
    days_in_year = 366 if _is_leap_year(observed_at_utc.year) else 365
    decimal_hour = (
        observed_at_utc.hour
        + observed_at_utc.minute / 60
        + observed_at_utc.second / 3_600
        + observed_at_utc.microsecond / 3_600_000_000
    )
    fractional_year = 2 * pi / days_in_year * (
        observed_at_utc.timetuple().tm_yday - 1 + (decimal_hour - 12) / 24
    )

    equation_of_time_minutes = 229.18 * (
        0.000075
        + 0.001868 * cos(fractional_year)
        - 0.032077 * sin(fractional_year)
        - 0.014615 * cos(2 * fractional_year)
        - 0.040849 * sin(2 * fractional_year)
    )
    declination = (
        0.006918
        - 0.399912 * cos(fractional_year)
        + 0.070257 * sin(fractional_year)
        - 0.006758 * cos(2 * fractional_year)
        + 0.000907 * sin(2 * fractional_year)
        - 0.002697 * cos(3 * fractional_year)
        + 0.00148 * sin(3 * fractional_year)
    )

    utc_minutes = decimal_hour * 60
    true_solar_minutes = (utc_minutes + equation_of_time_minutes + 4 * longitude) % 1_440
    hour_angle_degrees = true_solar_minutes / 4 - 180
    hour_angle = radians(hour_angle_degrees)
    latitude_radians = radians(latitude)

    cosine_zenith = (
        sin(latitude_radians) * sin(declination)
        + cos(latitude_radians) * cos(declination) * cos(hour_angle)
    )
    cosine_zenith = max(-1.0, min(1.0, cosine_zenith))
    zenith_degrees = degrees(acos(cosine_zenith))
    geometric_altitude = 90 - zenith_degrees

    azimuth = (
        degrees(
            atan2(
                sin(hour_angle),
                cos(hour_angle) * sin(latitude_radians) - tan(declination) * cos(latitude_radians),
            )
        )
        + 180
    ) % 360
    apparent_altitude = geometric_altitude + _atmospheric_refraction_degrees(geometric_altitude)
    daylight = apparent_altitude > 0
    shadow_azimuth = (azimuth + 180) % 360 if daylight else None

    return SolarPosition(
        observed_at=observed_at_utc,
        bucket_start=time_bucket_start(observed_at_utc),
        latitude=latitude,
        longitude=longitude,
        geometric_altitude_degrees=round(geometric_altitude, 5),
        apparent_altitude_degrees=round(apparent_altitude, 5),
        azimuth_degrees=round(azimuth, 5),
        shadow_azimuth_degrees=round(shadow_azimuth, 5) if shadow_azimuth is not None else None,
        daylight=daylight,
    )


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
