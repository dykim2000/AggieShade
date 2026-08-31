"""Metric building-footprint shadow geometry for the TAMU campus snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import json
from math import cos, isfinite, radians, sin, tan
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from shapely import affinity, make_valid, set_precision
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .solar import SolarPosition, solar_position, time_bucket_start
from .trees import MetricPoint, Wgs84Point, metric_polygon_to_wgs84


MetricRing = tuple[MetricPoint, ...]
MetricPolygon = tuple[MetricRing, ...]
MetricMultiPolygon = tuple[MetricPolygon, ...]
Wgs84Ring = tuple[Wgs84Point, ...]
Wgs84Polygon = tuple[Wgs84Ring, ...]
Wgs84MultiPolygon = tuple[Wgs84Polygon, ...]
PolygonalGeometry = Polygon | MultiPolygon

SHADE_DATA_PATH = Path(__file__).parents[1] / "data" / "shade_features.json"
METRIC_CRS = "EPSG:32614"
MAX_BUILDING_SHADOW_LENGTH_M = 100.0
BUILDING_SHADOW_CACHE_SIZE = 8
BUILDING_MAP_SIMPLIFY_TOLERANCE_M = 0.25


@dataclass(frozen=True)
class ShadeBuilding:
    source_id: int | str
    name: str | None
    building_number: str | None
    abbreviation: str | None
    height_m: float
    height_source: str
    quality_flags: tuple[str, ...]
    footprint: PolygonalGeometry
    reference_m: MetricPoint
    reference_wgs84: Wgs84Point


@dataclass(frozen=True)
class BuildingShadow:
    building_id: int | str
    name: str | None
    building_number: str | None
    abbreviation: str | None
    height_m: float
    height_source: str
    quality_flags: tuple[str, ...]
    shadow_length_m: float
    length_capped: bool
    footprint_bounds: tuple[float, float, float, float]
    geometry: PolygonalGeometry
    reference_m: MetricPoint
    reference_wgs84: Wgs84Point

    @property
    def polygons_m(self) -> MetricMultiPolygon:
        return geometry_to_metric_polygons(self.geometry)


@dataclass(frozen=True)
class BuildingShadowBucket:
    bucket_start: datetime
    crs: str
    eligible_building_count: int
    excluded_building_count: int
    solar: SolarPosition
    shadows: tuple[BuildingShadow, ...]


@dataclass(frozen=True)
class BuildingShadowMapFeature:
    building_id: int | str
    name: str | None
    height_m: float
    height_source: str
    quality_flags: tuple[str, ...]
    polygons_wgs84: Wgs84MultiPolygon


@dataclass(frozen=True)
class BuildingShadowMapBucket:
    bucket_start: datetime
    daylight: bool
    shadow_azimuth_degrees: float | None
    eligible_building_count: int
    excluded_building_count: int
    features: tuple[BuildingShadowMapFeature, ...]


@dataclass(frozen=True)
class BuildingShadowCacheInfo:
    hits: int
    misses: int
    maxsize: int
    currsize: int


@dataclass(frozen=True)
class _RingRecord:
    coordinates: MetricRing
    polygon: Polygon
    area: float
    representative_point: Point
    depth: int


def _closed_metric_ring(raw_ring: object) -> MetricRing:
    if not isinstance(raw_ring, list) or len(raw_ring) < 4:
        raise ValueError("building footprint rings require at least four points")

    points: list[MetricPoint] = []
    for raw_point in raw_ring:
        if not isinstance(raw_point, list) or len(raw_point) != 2:
            raise ValueError("building footprint points must be x/y pairs")
        try:
            point = float(raw_point[0]), float(raw_point[1])
        except (TypeError, ValueError) as exc:
            raise ValueError("building footprint coordinates must be numeric") from exc
        if not all(isfinite(value) for value in point):
            raise ValueError("building footprint coordinates must be finite")
        if not points or point != points[-1]:
            points.append(point)

    if len(points) < 4 or points[0] != points[-1]:
        raise ValueError("building footprint rings must be closed")
    if len(set(points[:-1])) < 3:
        raise ValueError("building footprint rings require three distinct vertices")

    polygon = Polygon(points)
    if polygon.area <= 0 or not polygon.exterior.is_simple:
        raise ValueError("building footprint ring is degenerate or self-intersecting")
    return tuple(points)


def _polygonal_geometry(geometry: BaseGeometry) -> PolygonalGeometry:
    """Return only valid nonempty polygonal members from a geometry result."""

    if geometry.is_empty:
        raise ValueError("building geometry is empty")
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    geometry = set_precision(geometry, grid_size=0.001, mode="valid_output")

    polygons: list[Polygon] = []

    def collect(candidate: BaseGeometry) -> None:
        if isinstance(candidate, Polygon):
            if not candidate.is_empty and candidate.area > 0:
                polygons.append(candidate)
        elif isinstance(candidate, (MultiPolygon, GeometryCollection)):
            for member in candidate.geoms:
                collect(member)

    collect(geometry)
    if not polygons:
        raise ValueError("building geometry has no polygonal area")

    merged = unary_union(polygons)
    if isinstance(merged, Polygon):
        return merged
    if isinstance(merged, MultiPolygon):
        return merged
    return _polygonal_geometry(merged)


def arcgis_rings_to_geometry(raw_rings: object) -> PolygonalGeometry:
    """Convert ArcGIS rings to valid Polygon/MultiPolygon topology.

    Ring nesting is used instead of assuming every ring after the first is a
    hole. This preserves detached building wings and interior courtyards.
    """

    if not isinstance(raw_rings, list) or not raw_rings:
        raise ValueError("building footprint must contain rings")

    ring_data: list[tuple[MetricRing, Polygon, float, Point]] = []
    for raw_ring in raw_rings:
        coordinates = _closed_metric_ring(raw_ring)
        polygon = Polygon(coordinates)
        ring_data.append((coordinates, polygon, polygon.area, polygon.representative_point()))

    records: list[_RingRecord] = []
    for coordinates, polygon, area, representative_point in ring_data:
        depth = sum(
            candidate_area > area and candidate_polygon.covers(representative_point)
            for _, candidate_polygon, candidate_area, _ in ring_data
        )
        records.append(
            _RingRecord(
                coordinates=coordinates,
                polygon=polygon,
                area=area,
                representative_point=representative_point,
                depth=depth,
            )
        )

    shells = [record for record in records if record.depth % 2 == 0]
    holes = [record for record in records if record.depth % 2 == 1]
    if not shells:
        raise ValueError("building footprint has no exterior ring")

    polygons: list[Polygon] = []
    for shell in shells:
        shell_holes: list[MetricRing] = []
        for hole in holes:
            containing_shells = [
                candidate
                for candidate in shells
                if candidate.area > hole.area and candidate.polygon.covers(hole.representative_point)
            ]
            if containing_shells and min(containing_shells, key=lambda candidate: candidate.area) is shell:
                shell_holes.append(hole.coordinates)
        polygon = Polygon(shell.coordinates, shell_holes)
        if polygon.is_empty or polygon.area <= 0 or not polygon.is_valid:
            raise ValueError("building footprint topology is invalid")
        polygons.append(polygon)

    return _polygonal_geometry(MultiPolygon(polygons) if len(polygons) > 1 else polygons[0])


def _reference_points(raw_building: Mapping[str, object]) -> tuple[MetricPoint, Wgs84Point]:
    metric_rings = raw_building.get("footprint_m")
    wgs84_rings = raw_building.get("footprint_wgs84")
    try:
        raw_metric = metric_rings[0][0]  # type: ignore[index]
        raw_wgs84 = wgs84_rings[0][0]  # type: ignore[index]
        reference_m = float(raw_metric[0]), float(raw_metric[1])
        reference_wgs84 = float(raw_wgs84[0]), float(raw_wgs84[1])
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("building footprint reference coordinates are missing") from exc
    if not all(isfinite(value) for value in (*reference_m, *reference_wgs84)):
        raise ValueError("building footprint reference coordinates must be finite")
    if not -180 <= reference_wgs84[0] <= 180 or not -90 <= reference_wgs84[1] <= 90:
        raise ValueError("building WGS 84 reference coordinate is invalid")
    return reference_m, reference_wgs84


def shade_ready_buildings_from_dataset(
    dataset: Mapping[str, object],
) -> tuple[tuple[ShadeBuilding, ...], int]:
    """Return valid shade-ready buildings and the number of excluded records."""

    raw_buildings = dataset.get("buildings")
    if not isinstance(raw_buildings, list):
        raise ValueError("shade dataset must contain a buildings list")

    buildings: list[ShadeBuilding] = []
    seen_ids: set[int | str] = set()
    for raw_building in raw_buildings:
        if not isinstance(raw_building, Mapping) or raw_building.get("shade_ready") is not True:
            continue
        source_id = raw_building.get("source_id")
        if not isinstance(source_id, (int, str)) or source_id in seen_ids:
            continue
        try:
            height_m = float(raw_building["estimated_height_m"])
            height_source = str(raw_building["height_source"]).strip()
            footprint = arcgis_rings_to_geometry(raw_building.get("footprint_m"))
            reference_m, reference_wgs84 = _reference_points(raw_building)
        except (KeyError, TypeError, ValueError):
            continue
        if not isfinite(height_m) or height_m <= 0 or not height_source:
            continue

        raw_flags = raw_building.get("quality_flags")
        quality_flags = (
            tuple(str(flag) for flag in raw_flags if isinstance(flag, str))
            if isinstance(raw_flags, list)
            else ()
        )
        buildings.append(
            ShadeBuilding(
                source_id=source_id,
                name=str(raw_building["name"]) if raw_building.get("name") is not None else None,
                building_number=(
                    str(raw_building["building_number"])
                    if raw_building.get("building_number") is not None
                    else None
                ),
                abbreviation=(
                    str(raw_building["abbreviation"])
                    if raw_building.get("abbreviation") is not None
                    else None
                ),
                height_m=height_m,
                height_source=height_source,
                quality_flags=quality_flags,
                footprint=footprint,
                reference_m=reference_m,
                reference_wgs84=reference_wgs84,
            )
        )
        seen_ids.add(source_id)

    return tuple(buildings), len(raw_buildings) - len(buildings)


def _load_building_inventory() -> tuple[tuple[ShadeBuilding, ...], int]:
    dataset = json.loads(SHADE_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(dataset, dict):
        raise ValueError("shade dataset must be a JSON object")
    return shade_ready_buildings_from_dataset(dataset)


def _polygons(geometry: PolygonalGeometry) -> Iterable[Polygon]:
    return (geometry,) if isinstance(geometry, Polygon) else geometry.geoms


def _boundary_rings(polygon: Polygon) -> Iterable[Sequence[MetricPoint]]:
    yield tuple((float(x), float(y)) for x, y in polygon.exterior.coords)
    for interior in polygon.interiors:
        yield tuple((float(x), float(y)) for x, y in interior.coords)


def swept_footprint(
    footprint: PolygonalGeometry,
    shadow_length_m: float,
    shadow_azimuth_degrees: float,
) -> PolygonalGeometry:
    """Sweep a footprint along its shadow vector without convex-hulling it."""

    if footprint.is_empty or not footprint.is_valid or footprint.area <= 0:
        raise ValueError("footprint must be a valid nonempty polygon")
    if not isfinite(shadow_length_m) or shadow_length_m < 0:
        raise ValueError("shadow_length_m must be finite and nonnegative")
    if not isfinite(shadow_azimuth_degrees):
        raise ValueError("shadow_azimuth_degrees must be finite")
    if shadow_length_m == 0:
        return footprint

    azimuth_radians = radians(shadow_azimuth_degrees)
    x_offset = shadow_length_m * sin(azimuth_radians)
    y_offset = shadow_length_m * cos(azimuth_radians)
    if abs(x_offset) < 1e-12:
        x_offset = 0.0
    if abs(y_offset) < 1e-12:
        y_offset = 0.0
    pieces: list[BaseGeometry] = [
        footprint,
        affinity.translate(footprint, xoff=x_offset, yoff=y_offset),
    ]

    for polygon in _polygons(footprint):
        for ring in _boundary_rings(polygon):
            for start, end in zip(ring, ring[1:]):
                quad = Polygon(
                    (
                        start,
                        end,
                        (end[0] + x_offset, end[1] + y_offset),
                        (start[0] + x_offset, start[1] + y_offset),
                        start,
                    )
                )
                if not quad.is_empty and quad.area > 1e-9:
                    pieces.append(quad)

    return _polygonal_geometry(unary_union(pieces))


def geometry_to_metric_polygons(geometry: PolygonalGeometry) -> MetricMultiPolygon:
    polygons: list[MetricPolygon] = []
    for polygon in _polygons(geometry):
        rings: list[MetricRing] = []
        for ring in _boundary_rings(polygon):
            rounded = tuple((round(point[0], 3), round(point[1], 3)) for point in ring)
            if rounded[0] != rounded[-1]:
                rounded += (rounded[0],)
            rings.append(rounded)
        polygons.append(tuple(rings))
    return tuple(polygons)


SHADE_READY_BUILDINGS, EXCLUDED_BUILDING_COUNT = _load_building_inventory()


@lru_cache(maxsize=BUILDING_SHADOW_CACHE_SIZE)
def _building_shadow_bucket(bucket_start: datetime) -> BuildingShadowBucket:
    solar = solar_position(bucket_start)
    if not solar.daylight or solar.shadow_azimuth_degrees is None:
        return BuildingShadowBucket(
            bucket_start=bucket_start,
            crs=METRIC_CRS,
            eligible_building_count=len(SHADE_READY_BUILDINGS),
            excluded_building_count=EXCLUDED_BUILDING_COUNT,
            solar=solar,
            shadows=(),
        )

    altitude_radians = radians(solar.apparent_altitude_degrees)
    shadows: list[BuildingShadow] = []
    for building in SHADE_READY_BUILDINGS:
        projected_length = building.height_m / tan(altitude_radians)
        length_capped = projected_length > MAX_BUILDING_SHADOW_LENGTH_M
        shadow_length = min(projected_length, MAX_BUILDING_SHADOW_LENGTH_M)
        shadows.append(
            BuildingShadow(
                building_id=building.source_id,
                name=building.name,
                building_number=building.building_number,
                abbreviation=building.abbreviation,
                height_m=building.height_m,
                height_source=building.height_source,
                quality_flags=building.quality_flags,
                shadow_length_m=round(shadow_length, 3),
                length_capped=length_capped,
                footprint_bounds=building.footprint.bounds,
                geometry=swept_footprint(
                    building.footprint,
                    shadow_length,
                    solar.shadow_azimuth_degrees,
                ),
                reference_m=building.reference_m,
                reference_wgs84=building.reference_wgs84,
            )
        )

    return BuildingShadowBucket(
        bucket_start=bucket_start,
        crs=METRIC_CRS,
        eligible_building_count=len(SHADE_READY_BUILDINGS),
        excluded_building_count=EXCLUDED_BUILDING_COUNT,
        solar=solar,
        shadows=tuple(shadows),
    )


@lru_cache(maxsize=BUILDING_SHADOW_CACHE_SIZE)
def _building_shadow_map_bucket(bucket_start: datetime) -> BuildingShadowMapBucket:
    bucket = _building_shadow_bucket(bucket_start)
    features: list[BuildingShadowMapFeature] = []
    for shadow in bucket.shadows:
        simplified = _polygonal_geometry(
            shadow.geometry.simplify(
                BUILDING_MAP_SIMPLIFY_TOLERANCE_M,
                preserve_topology=True,
            )
        )
        polygons_wgs84 = tuple(
            tuple(
                metric_polygon_to_wgs84(ring, shadow.reference_m, shadow.reference_wgs84)
                for ring in polygon
            )
            for polygon in geometry_to_metric_polygons(simplified)
        )
        features.append(
            BuildingShadowMapFeature(
                building_id=shadow.building_id,
                name=shadow.name,
                height_m=shadow.height_m,
                height_source=shadow.height_source,
                quality_flags=shadow.quality_flags,
                polygons_wgs84=polygons_wgs84,
            )
        )

    return BuildingShadowMapBucket(
        bucket_start=bucket.bucket_start,
        daylight=bucket.solar.daylight,
        shadow_azimuth_degrees=bucket.solar.shadow_azimuth_degrees,
        eligible_building_count=bucket.eligible_building_count,
        excluded_building_count=bucket.excluded_building_count,
        features=tuple(features),
    )


def building_shadows_at(observed_at: datetime) -> BuildingShadowBucket:
    """Return cached building-shadow geometry for an instant's 15-minute bucket."""

    return _building_shadow_bucket(time_bucket_start(observed_at))


def building_shadow_map_at(observed_at: datetime) -> BuildingShadowMapBucket:
    """Return cached, map-optimized WGS 84 building shadows for an instant."""

    return _building_shadow_map_bucket(time_bucket_start(observed_at))


def clear_building_shadow_cache() -> None:
    _building_shadow_bucket.cache_clear()
    _building_shadow_map_bucket.cache_clear()


def building_shadow_cache_info() -> BuildingShadowCacheInfo:
    info = _building_shadow_bucket.cache_info()
    return BuildingShadowCacheInfo(
        hits=info.hits,
        misses=info.misses,
        maxsize=info.maxsize,
        currsize=info.currsize,
    )
