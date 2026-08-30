"""Download and normalize shade inputs from Texas A&M's public GIS service.

The source service returns ArcGIS JSON in WGS 84.  This module preserves those
coordinates for traceability and also projects every feature into UTM zone 14N
(EPSG:32614), which gives the shade engine a local metric coordinate system.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from math import cos, pi, sin, sqrt, tan
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import urlopen


TAMU_BASEMAP_URL = "https://gis.tamu.edu/arcgis/rest/services/FCOR/TAMU_BaseMap/MapServer"
TREE_LAYER_ID = 4
BUILDING_LAYER_ID = 2
DEFAULT_CAMPUS_BBOX = (-96.346, 30.609, -96.338, 30.6225)
TARGET_CRS = "EPSG:32614"
FEET_TO_METERS = 0.3048
DEFAULT_FLOOR_HEIGHT_M = 3.5

TREE_FIELDS = (
    "OBJECTID",
    "GlobalID",
    "Common_Name",
    "Species",
    "Height",
    "Canopy_Spread",
    "Health",
    "Condition",
    "Status",
    "Date_Removed",
    "last_edited_date",
)
BUILDING_FIELDS = (
    "OBJECTID",
    "BldgNum",
    "BldgAbbr",
    "BldgName",
    "NumFloors",
    "status",
    "BldgDate",
)

JsonObject = dict[str, Any]
Transport = Callable[[str], bytes]


class ArcGISError(RuntimeError):
    """Raised when the public ArcGIS service returns an invalid response."""


def _default_transport(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:  # noqa: S310 - fixed, public service URL
        return response.read()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _positive_integer(value: Any) -> int | None:
    number = _positive_number(value)
    if number is None or not number.is_integer():
        return None
    result = int(number)
    return result if result <= 200 else None


def _round_point(point: Sequence[float], digits: int) -> list[float]:
    return [round(float(point[0]), digits), round(float(point[1]), digits)]


def wgs84_to_utm14(lon: float, lat: float) -> tuple[float, float]:
    """Project a WGS 84 coordinate to UTM zone 14N without external packages."""

    if not (-180 <= lon <= 180 and -80 <= lat <= 84):
        raise ValueError("Coordinate is outside the supported UTM latitude/longitude range")

    semi_major_axis = 6_378_137.0
    eccentricity_squared = 0.00669438
    scale_factor = 0.9996
    lat_rad = lat * pi / 180
    lon_rad = lon * pi / 180
    central_meridian_rad = -99 * pi / 180

    eccentricity_prime_squared = eccentricity_squared / (1 - eccentricity_squared)
    radius = semi_major_axis / sqrt(1 - eccentricity_squared * sin(lat_rad) ** 2)
    tangent_squared = tan(lat_rad) ** 2
    cosine_term = eccentricity_prime_squared * cos(lat_rad) ** 2
    longitude_term = cos(lat_rad) * (lon_rad - central_meridian_rad)

    meridional_arc = semi_major_axis * (
        (1 - eccentricity_squared / 4 - 3 * eccentricity_squared**2 / 64 - 5 * eccentricity_squared**3 / 256)
        * lat_rad
        - (3 * eccentricity_squared / 8 + 3 * eccentricity_squared**2 / 32 + 45 * eccentricity_squared**3 / 1024)
        * sin(2 * lat_rad)
        + (15 * eccentricity_squared**2 / 256 + 45 * eccentricity_squared**3 / 1024) * sin(4 * lat_rad)
        - (35 * eccentricity_squared**3 / 3072) * sin(6 * lat_rad)
    )

    easting = scale_factor * radius * (
        longitude_term
        + (1 - tangent_squared + cosine_term) * longitude_term**3 / 6
        + (5 - 18 * tangent_squared + tangent_squared**2 + 72 * cosine_term - 58 * eccentricity_prime_squared)
        * longitude_term**5
        / 120
    ) + 500_000
    northing = scale_factor * (
        meridional_arc
        + radius
        * tan(lat_rad)
        * (
            longitude_term**2 / 2
            + (5 - tangent_squared + 9 * cosine_term + 4 * cosine_term**2) * longitude_term**4 / 24
            + (61 - 58 * tangent_squared + tangent_squared**2 + 600 * cosine_term - 330 * eccentricity_prime_squared)
            * longitude_term**6
            / 720
        )
    )
    if lat < 0:
        northing += 10_000_000
    return easting, northing


class ArcGISClient:
    """Small paginated reader for an ArcGIS MapServer feature layer."""

    def __init__(
        self,
        service_url: str = TAMU_BASEMAP_URL,
        *,
        transport: Transport = _default_transport,
        page_size: int = 2_000,
    ) -> None:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self.service_url = service_url.rstrip("/")
        self.transport = transport
        self.page_size = page_size

    def _get_json(self, path: str, parameters: Mapping[str, str]) -> JsonObject:
        url = f"{self.service_url}/{path}?{urlencode(parameters)}"
        try:
            payload = json.loads(self.transport(url).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArcGISError(f"Could not read ArcGIS response for {path}") from exc
        if not isinstance(payload, dict):
            raise ArcGISError(f"ArcGIS returned a non-object response for {path}")
        if "error" in payload:
            error = payload["error"]
            message = error.get("message", "unknown error") if isinstance(error, dict) else str(error)
            raise ArcGISError(f"ArcGIS error for {path}: {message}")
        return payload

    def fetch_features(
        self,
        layer_id: int,
        fields: Iterable[str],
        bbox: Sequence[float] = DEFAULT_CAMPUS_BBOX,
    ) -> list[JsonObject]:
        if len(bbox) != 4 or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
            raise ValueError("bbox must be (west, south, east, north)")

        features: list[JsonObject] = []
        seen_ids: set[Any] = set()
        offset = 0

        while True:
            payload = self._get_json(
                f"{layer_id}/query",
                {
                    "where": "1=1",
                    "outFields": ",".join(fields),
                    "geometry": ",".join(str(value) for value in bbox),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "orderByFields": "OBJECTID",
                    "resultOffset": str(offset),
                    "resultRecordCount": str(self.page_size),
                    "f": "json",
                },
            )
            page = payload.get("features")
            if not isinstance(page, list):
                raise ArcGISError(f"ArcGIS layer {layer_id} response omitted features")

            added = 0
            for feature in page:
                if not isinstance(feature, dict):
                    continue
                attributes = feature.get("attributes")
                object_id = attributes.get("OBJECTID") if isinstance(attributes, dict) else None
                dedupe_key = object_id if object_id is not None else (offset, added)
                if dedupe_key not in seen_ids:
                    seen_ids.add(dedupe_key)
                    features.append(feature)
                    added += 1

            more = bool(payload.get("exceededTransferLimit"))
            if not more:
                break
            if not page or added == 0:
                raise ArcGISError(f"ArcGIS pagination stalled for layer {layer_id} at offset {offset}")
            offset += len(page)

        return features


def normalize_tree(feature: Mapping[str, Any]) -> JsonObject:
    attributes = feature.get("attributes")
    geometry = feature.get("geometry")
    attributes = attributes if isinstance(attributes, Mapping) else {}
    geometry = geometry if isinstance(geometry, Mapping) else {}
    flags: list[str] = []

    try:
        lon = float(geometry["x"])
        lat = float(geometry["y"])
        easting, northing = wgs84_to_utm14(lon, lat)
        point_wgs84: list[float] | None = _round_point((lon, lat), 7)
        point_m: list[float] | None = _round_point((easting, northing), 3)
    except (KeyError, TypeError, ValueError):
        point_wgs84 = None
        point_m = None
        flags.append("invalid_geometry")

    height_ft = _positive_number(attributes.get("Height"))
    canopy_ft = _positive_number(attributes.get("Canopy_Spread"))
    if height_ft is None:
        flags.append("missing_height")
    if canopy_ft is None:
        flags.append("missing_canopy_spread")

    health = _clean_text(attributes.get("Health"))
    status = _clean_text(attributes.get("Status"))
    if health is None:
        flags.append("health_unknown")
    if status is None:
        flags.append("status_unknown")
    removed_at = attributes.get("Date_Removed")
    if status and status.casefold() == "dead":
        flags.append("dead")
    if removed_at is not None:
        flags.append("removed")

    shade_ready = (
        point_m is not None
        and height_ft is not None
        and canopy_ft is not None
        and not {"dead", "removed"}.intersection(flags)
    )
    return {
        "source_id": attributes.get("OBJECTID"),
        "global_id": _clean_text(attributes.get("GlobalID")),
        "point_wgs84": point_wgs84,
        "point_m": point_m,
        "common_name": _clean_text(attributes.get("Common_Name")),
        "species": _clean_text(attributes.get("Species")),
        "height_m": round(height_ft * FEET_TO_METERS, 3) if height_ft is not None else None,
        "canopy_diameter_m": round(canopy_ft * FEET_TO_METERS, 3) if canopy_ft is not None else None,
        "canopy_radius_m": round(canopy_ft * FEET_TO_METERS / 2, 3) if canopy_ft is not None else None,
        "health": health,
        "condition": _clean_text(attributes.get("Condition")),
        "status": status,
        "source_last_edited_at": attributes.get("last_edited_date"),
        "shade_ready": shade_ready,
        "quality_flags": flags,
    }


def _normalize_rings(rings: Any) -> tuple[list[list[list[float]]] | None, list[list[list[float]]] | None]:
    if not isinstance(rings, list) or not rings:
        return None, None
    wgs84_rings: list[list[list[float]]] = []
    metric_rings: list[list[list[float]]] = []
    try:
        for ring in rings:
            if not isinstance(ring, list) or len(ring) < 4:
                return None, None
            wgs84_ring: list[list[float]] = []
            metric_ring: list[list[float]] = []
            for coordinate in ring:
                lon, lat = float(coordinate[0]), float(coordinate[1])
                easting, northing = wgs84_to_utm14(lon, lat)
                wgs84_ring.append(_round_point((lon, lat), 7))
                metric_ring.append(_round_point((easting, northing), 3))
            wgs84_rings.append(wgs84_ring)
            metric_rings.append(metric_ring)
    except (IndexError, TypeError, ValueError):
        return None, None
    return wgs84_rings, metric_rings


def normalize_building(feature: Mapping[str, Any], floor_height_m: float = DEFAULT_FLOOR_HEIGHT_M) -> JsonObject:
    if floor_height_m <= 0:
        raise ValueError("floor_height_m must be positive")
    attributes = feature.get("attributes")
    geometry = feature.get("geometry")
    attributes = attributes if isinstance(attributes, Mapping) else {}
    geometry = geometry if isinstance(geometry, Mapping) else {}
    flags: list[str] = []

    footprint_wgs84, footprint_m = _normalize_rings(geometry.get("rings"))
    if footprint_m is None:
        flags.append("invalid_geometry")

    floors = _positive_integer(attributes.get("NumFloors"))
    if floors is None:
        flags.append("missing_floor_count")
        estimated_height_m = None
    else:
        estimated_height_m = round(floors * floor_height_m, 3)
        flags.append("height_estimated_from_floors")

    return {
        "source_id": attributes.get("OBJECTID"),
        "building_number": _clean_text(attributes.get("BldgNum")),
        "abbreviation": _clean_text(attributes.get("BldgAbbr")),
        "name": _clean_text(attributes.get("BldgName")),
        "status": _clean_text(attributes.get("status")),
        "floor_count": floors,
        "estimated_height_m": estimated_height_m,
        "height_source": "floor_count" if floors is not None else None,
        "footprint_wgs84": footprint_wgs84,
        "footprint_m": footprint_m,
        "shade_ready": footprint_m is not None and estimated_height_m is not None,
        "quality_flags": flags,
    }


def _quality_summary(features: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for feature in features:
        counts.update(feature.get("quality_flags", []))
    return dict(sorted(counts.items()))


def build_shade_dataset(
    tree_features: Iterable[Mapping[str, Any]],
    building_features: Iterable[Mapping[str, Any]],
    *,
    bbox: Sequence[float] = DEFAULT_CAMPUS_BBOX,
    generated_at: datetime | None = None,
    floor_height_m: float = DEFAULT_FLOOR_HEIGHT_M,
) -> JsonObject:
    trees = [normalize_tree(feature) for feature in tree_features]
    buildings = [normalize_building(feature, floor_height_m) for feature in building_features]
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return {
        "schema_version": 1,
        "generated_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "name": "Texas A&M University FCOR TAMU BaseMap",
            "service_url": TAMU_BASEMAP_URL,
            "layers": {
                "trees": {"id": TREE_LAYER_ID, "name": "Trees"},
                "buildings": {"id": BUILDING_LAYER_ID, "name": "University Building"},
            },
            "query_bbox_wgs84": list(bbox),
            "source_crs": "EPSG:4326",
            "target_metric_crs": TARGET_CRS,
        },
        "assumptions": {
            "tree_dimension_source_unit": "feet",
            "tree_dimension_unit_status": "assumed; source metadata does not declare units",
            "feet_to_meters": FEET_TO_METERS,
            "building_floor_height_m": floor_height_m,
        },
        "summary": {
            "tree_count": len(trees),
            "shade_ready_tree_count": sum(bool(tree["shade_ready"]) for tree in trees),
            "building_count": len(buildings),
            "shade_ready_building_count": sum(bool(building["shade_ready"]) for building in buildings),
            "tree_quality_flags": _quality_summary(trees),
            "building_quality_flags": _quality_summary(buildings),
        },
        "trees": trees,
        "buildings": buildings,
    }


def download_shade_dataset(
    *,
    client: ArcGISClient | None = None,
    bbox: Sequence[float] = DEFAULT_CAMPUS_BBOX,
    generated_at: datetime | None = None,
) -> JsonObject:
    reader = client or ArcGISClient()
    trees = reader.fetch_features(TREE_LAYER_ID, TREE_FIELDS, bbox)
    buildings = reader.fetch_features(BUILDING_LAYER_ID, BUILDING_FIELDS, bbox)
    return build_shade_dataset(trees, buildings, bbox=bbox, generated_at=generated_at)
