"""Time-aware shade scoring for TAMU pedestrian routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from types import MappingProxyType
from typing import Iterable, Literal, Mapping

from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..campus import (
    BUILDINGS,
    BUILDING_NODES,
    EDGE_DISTANCES_M,
    NODES,
    _shortest_path,
)
from ..gis.tamu import wgs84_to_utm14
from .buildings import building_shadows_at
from .solar import time_bucket_start
from .trees import tree_shadows_at


RoutePreference = Literal["fastest", "shadiest"]
SHADE_DISCOUNT = 0.70
SHADE_EDGE_CACHE_SIZE = 8


@dataclass(frozen=True)
class ShadeRoute:
    origin_id: str
    destination_id: str
    preference: RoutePreference
    distance_m: int
    duration_seconds: int
    shaded_distance_m: int
    shade_percentage: float
    shade_bucket_start: datetime
    daylight: bool
    geometry: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class EdgeShadeBucket:
    bucket_start: datetime
    daylight: bool
    edge_fractions: Mapping[frozenset[str], float]


@dataclass(frozen=True)
class ShadeEdgeCacheInfo:
    hits: int
    misses: int
    maxsize: int
    currsize: int


def _metric_edge_lines() -> dict[frozenset[str], LineString]:
    lines: dict[frozenset[str], LineString] = {}
    for edge_key in EDGE_DISTANCES_M:
        left_id, right_id = tuple(edge_key)
        left_latitude, left_longitude = NODES[left_id]
        right_latitude, right_longitude = NODES[right_id]
        lines[edge_key] = LineString(
            (
                wgs84_to_utm14(left_longitude, left_latitude),
                wgs84_to_utm14(right_longitude, right_latitude),
            )
        )
    return lines


EDGE_LINES_M = _metric_edge_lines()


def _polygon_parts(geometry: BaseGeometry) -> tuple[Polygon, ...]:
    if isinstance(geometry, Polygon):
        return (geometry,)
    if isinstance(geometry, MultiPolygon):
        return tuple(geometry.geoms)
    return tuple(
        member
        for member in getattr(geometry, "geoms", ())
        if isinstance(member, Polygon) and not member.is_empty
    )


def shade_fraction_for_line(
    line: LineString,
    shadow_geometries: Iterable[BaseGeometry],
) -> float:
    """Return the unique fraction of a metric line covered by shade polygons."""

    if line.is_empty or line.length <= 0:
        raise ValueError("line must have positive length")
    geometries = tuple(
        geometry
        for geometry in shadow_geometries
        if not geometry.is_empty and geometry.area > 0
    )
    if not geometries:
        return 0.0
    covered_length = line.intersection(unary_union(geometries)).length
    return max(0.0, min(1.0, covered_length / line.length))


@lru_cache(maxsize=SHADE_EDGE_CACHE_SIZE)
def _edge_shade_bucket(bucket_start: datetime) -> EdgeShadeBucket:
    tree_bucket = tree_shadows_at(bucket_start)
    building_bucket = building_shadows_at(bucket_start)
    daylight = tree_bucket.solar.daylight or building_bucket.solar.daylight

    shadow_geometries: list[BaseGeometry] = [
        Polygon(shadow.polygon_m) for shadow in tree_bucket.shadows
    ]
    shadow_geometries.extend(shadow.geometry for shadow in building_bucket.shadows)
    if not shadow_geometries:
        return EdgeShadeBucket(
            bucket_start=bucket_start,
            daylight=daylight,
            edge_fractions=MappingProxyType(
                {edge_key: 0.0 for edge_key in EDGE_DISTANCES_M}
            ),
        )

    dissolved_parts = _polygon_parts(unary_union(shadow_geometries))
    spatial_index = STRtree(dissolved_parts)
    fractions: dict[frozenset[str], float] = {}

    for edge_key, line in EDGE_LINES_M.items():
        candidate_indices = spatial_index.query(line, predicate="intersects")
        covered_length = sum(
            line.intersection(dissolved_parts[int(index)]).length
            for index in candidate_indices
        )
        fractions[edge_key] = max(0.0, min(1.0, covered_length / line.length))

    return EdgeShadeBucket(
        bucket_start=bucket_start,
        daylight=daylight,
        edge_fractions=MappingProxyType(fractions),
    )


def edge_shade_at(observed_at: datetime) -> EdgeShadeBucket:
    """Return cached shade fractions for every edge in the instant's time bucket."""

    return _edge_shade_bucket(time_bucket_start(observed_at))


def shade_route_between(
    origin_id: str,
    destination_id: str,
    *,
    preference: RoutePreference,
    observed_at: datetime,
) -> ShadeRoute:
    """Find a physical shortest or shade-weighted route between two buildings."""

    if origin_id not in BUILDINGS or destination_id not in BUILDINGS:
        raise KeyError("Unknown TAMU building")
    if origin_id == destination_id:
        raise ValueError("Choose two different TAMU buildings")
    if BUILDING_NODES[origin_id] == BUILDING_NODES[destination_id]:
        raise RuntimeError(
            "These buildings share the same pedestrian access point; no distinct route can be drawn"
        )
    if preference not in ("fastest", "shadiest"):
        raise ValueError("preference must be fastest or shadiest")

    shade_bucket = edge_shade_at(observed_at)
    edge_costs = None
    if preference == "shadiest":
        edge_costs = {
            edge_key: distance
            * (1 - SHADE_DISCOUNT * shade_bucket.edge_fractions[edge_key])
            for edge_key, distance in EDGE_DISTANCES_M.items()
        }

    path, distance = _shortest_path(
        BUILDING_NODES[origin_id],
        BUILDING_NODES[destination_id],
        edge_costs,
    )
    shaded_distance = sum(
        EDGE_DISTANCES_M[edge_key] * shade_bucket.edge_fractions[edge_key]
        for left_id, right_id in zip(path, path[1:])
        for edge_key in (frozenset((left_id, right_id)),)
    )
    shade_percentage = 100 * shaded_distance / distance if distance else 0.0

    return ShadeRoute(
        origin_id=origin_id,
        destination_id=destination_id,
        preference=preference,
        distance_m=round(distance),
        duration_seconds=round(distance / 1.4),
        shaded_distance_m=round(shaded_distance),
        shade_percentage=round(shade_percentage, 1),
        shade_bucket_start=shade_bucket.bucket_start,
        daylight=shade_bucket.daylight,
        geometry=tuple(NODES[node_id] for node_id in path),
    )


def clear_shade_edge_cache() -> None:
    _edge_shade_bucket.cache_clear()


def shade_edge_cache_info() -> ShadeEdgeCacheInfo:
    info = _edge_shade_bucket.cache_info()
    return ShadeEdgeCacheInfo(
        hits=info.hits,
        misses=info.misses,
        maxsize=info.maxsize,
        currsize=info.currsize,
    )
