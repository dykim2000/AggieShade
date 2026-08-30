"""Metric tree-canopy shadow geometry for the TAMU campus snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import json
from math import cos, pi, radians, sin, tan
from pathlib import Path
from typing import Mapping

from .solar import SolarPosition, solar_position, time_bucket_start


MetricPoint = tuple[float, float]
Wgs84Point = tuple[float, float]
SHADE_DATA_PATH = Path(__file__).parents[1] / "data" / "shade_features.json"
METRIC_CRS = "EPSG:32614"
CIRCLE_SEGMENTS = 16
MAX_TREE_SHADOW_LENGTH_M = 100.0
TREE_SHADOW_CACHE_SIZE = 8


@dataclass(frozen=True)
class ShadeTree:
    source_id: int | str
    center_m: MetricPoint
    center_wgs84: Wgs84Point
    height_m: float
    canopy_radius_m: float


@dataclass(frozen=True)
class TreeShadow:
    tree_id: int | str
    center_m: MetricPoint
    center_wgs84: Wgs84Point
    height_m: float
    canopy_radius_m: float
    shadow_length_m: float
    length_capped: bool
    polygon_m: tuple[MetricPoint, ...]


@dataclass(frozen=True)
class TreeShadowBucket:
    bucket_start: datetime
    crs: str
    eligible_tree_count: int
    excluded_tree_count: int
    solar: SolarPosition
    shadows: tuple[TreeShadow, ...]


@dataclass(frozen=True)
class TreeShadowCacheInfo:
    hits: int
    misses: int
    maxsize: int
    currsize: int


@dataclass(frozen=True)
class TreeShadowMapBucket:
    bucket_start: datetime
    daylight: bool
    shadow_azimuth_degrees: float | None
    polygons_wgs84: tuple[tuple[Wgs84Point, ...], ...]


def shade_ready_trees_from_dataset(
    dataset: Mapping[str, object],
) -> tuple[tuple[ShadeTree, ...], int]:
    """Return valid shade-ready trees and the number of excluded records."""

    raw_trees = dataset.get("trees")
    if not isinstance(raw_trees, list):
        raise ValueError("shade dataset must contain a trees list")

    trees: list[ShadeTree] = []
    for raw_tree in raw_trees:
        if not isinstance(raw_tree, Mapping) or raw_tree.get("shade_ready") is not True:
            continue
        point = raw_tree.get("point_m")
        point_wgs84 = raw_tree.get("point_wgs84")
        source_id = raw_tree.get("source_id")
        try:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or not isinstance(point_wgs84, list)
                or len(point_wgs84) != 2
                or source_id is None
            ):
                continue
            center_m = float(point[0]), float(point[1])
            center_wgs84 = float(point_wgs84[0]), float(point_wgs84[1])
            height_m = float(raw_tree["height_m"])
            canopy_radius_m = float(raw_tree["canopy_radius_m"])
        except (KeyError, TypeError, ValueError):
            continue
        if not -180 <= center_wgs84[0] <= 180 or not -90 <= center_wgs84[1] <= 90:
            continue
        if height_m <= 0 or canopy_radius_m <= 0:
            continue
        if not isinstance(source_id, (int, str)):
            continue
        trees.append(
            ShadeTree(
                source_id=source_id,
                center_m=center_m,
                center_wgs84=center_wgs84,
                height_m=height_m,
                canopy_radius_m=canopy_radius_m,
            )
        )

    return tuple(trees), len(raw_trees) - len(trees)


def _load_tree_inventory() -> tuple[tuple[ShadeTree, ...], int]:
    dataset = json.loads(SHADE_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(dataset, dict):
        raise ValueError("shade dataset must be a JSON object")
    return shade_ready_trees_from_dataset(dataset)


SHADE_READY_TREES, EXCLUDED_TREE_COUNT = _load_tree_inventory()


def tree_shadow_polygon(
    center_m: MetricPoint,
    canopy_radius_m: float,
    shadow_length_m: float,
    shadow_azimuth_degrees: float,
    *,
    circle_segments: int = CIRCLE_SEGMENTS,
) -> tuple[MetricPoint, ...]:
    """Build a closed capsule around a canopy and its projected position.

    Metric x/y values are UTM easting/northing. Azimuth is clockwise from
    north, matching the solar-position contract.
    """

    if canopy_radius_m <= 0:
        raise ValueError("canopy_radius_m must be positive")
    if shadow_length_m < 0:
        raise ValueError("shadow_length_m cannot be negative")
    if circle_segments < 8 or circle_segments % 2:
        raise ValueError("circle_segments must be an even number of at least 8")

    direction_angle = radians(90 - shadow_azimuth_degrees)
    if shadow_length_m == 0:
        points = [
            (
                center_m[0] + canopy_radius_m * cos(direction_angle + 2 * pi * index / circle_segments),
                center_m[1] + canopy_radius_m * sin(direction_angle + 2 * pi * index / circle_segments),
            )
            for index in range(circle_segments)
        ]
    else:
        end_m = (
            center_m[0] + shadow_length_m * cos(direction_angle),
            center_m[1] + shadow_length_m * sin(direction_angle),
        )
        half_segments = circle_segments // 2
        start_arc = [
            direction_angle + pi / 2 + pi * index / half_segments
            for index in range(half_segments + 1)
        ]
        end_arc = [
            direction_angle - pi / 2 + pi * index / half_segments
            for index in range(half_segments + 1)
        ]
        points = [
            (
                center_m[0] + canopy_radius_m * cos(angle),
                center_m[1] + canopy_radius_m * sin(angle),
            )
            for angle in start_arc
        ]
        points.extend(
            (
                end_m[0] + canopy_radius_m * cos(angle),
                end_m[1] + canopy_radius_m * sin(angle),
            )
            for angle in end_arc
        )

    rounded = tuple((round(x, 3), round(y, 3)) for x, y in points)
    return rounded + (rounded[0],)


@lru_cache(maxsize=TREE_SHADOW_CACHE_SIZE)
def _tree_shadow_bucket(bucket_start: datetime) -> TreeShadowBucket:
    solar = solar_position(bucket_start)
    if not solar.daylight or solar.shadow_azimuth_degrees is None:
        return TreeShadowBucket(
            bucket_start=bucket_start,
            crs=METRIC_CRS,
            eligible_tree_count=len(SHADE_READY_TREES),
            excluded_tree_count=EXCLUDED_TREE_COUNT,
            solar=solar,
            shadows=(),
        )

    altitude_radians = radians(solar.apparent_altitude_degrees)
    shadows: list[TreeShadow] = []
    for tree in SHADE_READY_TREES:
        projected_length = tree.height_m / tan(altitude_radians)
        length_capped = projected_length > MAX_TREE_SHADOW_LENGTH_M
        shadow_length = min(projected_length, MAX_TREE_SHADOW_LENGTH_M)
        shadows.append(
            TreeShadow(
                tree_id=tree.source_id,
                center_m=tree.center_m,
                center_wgs84=tree.center_wgs84,
                height_m=tree.height_m,
                canopy_radius_m=tree.canopy_radius_m,
                shadow_length_m=round(shadow_length, 3),
                length_capped=length_capped,
                polygon_m=tree_shadow_polygon(
                    tree.center_m,
                    tree.canopy_radius_m,
                    shadow_length,
                    solar.shadow_azimuth_degrees,
                ),
            )
        )

    return TreeShadowBucket(
        bucket_start=bucket_start,
        crs=METRIC_CRS,
        eligible_tree_count=len(SHADE_READY_TREES),
        excluded_tree_count=EXCLUDED_TREE_COUNT,
        solar=solar,
        shadows=tuple(shadows),
    )


def metric_polygon_to_wgs84(
    polygon_m: tuple[MetricPoint, ...],
    center_m: MetricPoint,
    center_wgs84: Wgs84Point,
) -> tuple[Wgs84Point, ...]:
    """Convert local metric offsets to WGS 84 for lightweight map display."""

    latitude_radians = radians(center_wgs84[1])
    meters_per_degree_latitude = (
        111_132.92
        - 559.82 * cos(2 * latitude_radians)
        + 1.175 * cos(4 * latitude_radians)
        - 0.0023 * cos(6 * latitude_radians)
    )
    meters_per_degree_longitude = (
        111_412.84 * cos(latitude_radians)
        - 93.5 * cos(3 * latitude_radians)
        + 0.118 * cos(5 * latitude_radians)
    )
    return tuple(
        (
            round(center_wgs84[0] + (point[0] - center_m[0]) / meters_per_degree_longitude, 7),
            round(center_wgs84[1] + (point[1] - center_m[1]) / meters_per_degree_latitude, 7),
        )
        for point in polygon_m
    )


@lru_cache(maxsize=TREE_SHADOW_CACHE_SIZE)
def _tree_shadow_map_bucket(bucket_start: datetime) -> TreeShadowMapBucket:
    bucket = _tree_shadow_bucket(bucket_start)
    if not bucket.shadows or bucket.solar.shadow_azimuth_degrees is None:
        return TreeShadowMapBucket(
            bucket_start=bucket.bucket_start,
            daylight=bucket.solar.daylight,
            shadow_azimuth_degrees=bucket.solar.shadow_azimuth_degrees,
            polygons_wgs84=(),
        )

    polygons = tuple(
        metric_polygon_to_wgs84(
            tree_shadow_polygon(
                shadow.center_m,
                shadow.canopy_radius_m,
                shadow.shadow_length_m,
                bucket.solar.shadow_azimuth_degrees,
                circle_segments=8,
            ),
            shadow.center_m,
            shadow.center_wgs84,
        )
        for shadow in bucket.shadows
    )
    return TreeShadowMapBucket(
        bucket_start=bucket.bucket_start,
        daylight=bucket.solar.daylight,
        shadow_azimuth_degrees=bucket.solar.shadow_azimuth_degrees,
        polygons_wgs84=polygons,
    )


def tree_shadows_at(observed_at: datetime) -> TreeShadowBucket:
    """Return the cached tree-shadow geometry for an instant's 15-minute bucket."""

    return _tree_shadow_bucket(time_bucket_start(observed_at))


def tree_shadow_map_at(observed_at: datetime) -> TreeShadowMapBucket:
    """Return cached, map-optimized WGS 84 polygons for an instant's bucket."""

    return _tree_shadow_map_bucket(time_bucket_start(observed_at))


def clear_tree_shadow_cache() -> None:
    _tree_shadow_bucket.cache_clear()
    _tree_shadow_map_bucket.cache_clear()


def tree_shadow_cache_info() -> TreeShadowCacheInfo:
    info = _tree_shadow_bucket.cache_info()
    return TreeShadowCacheInfo(
        hits=info.hits,
        misses=info.misses,
        maxsize=info.maxsize,
        currsize=info.currsize,
    )
