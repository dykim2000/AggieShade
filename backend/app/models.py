from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .campus import BUILDING_NODES, NODES, Building, Route
from .shade.solar import SOLAR_REFERENCE_URL, TIME_BUCKET_MINUTES, SolarPosition
from .shade.trees import (
    MAX_TREE_SHADOW_LENGTH_M,
    TreeShadow,
    TreeShadowBucket,
    TreeShadowMapBucket,
)


class PointResponse(BaseModel):
    latitude: float
    longitude: float


class MetricPointResponse(BaseModel):
    easting: float
    northing: float


class BuildingResponse(BaseModel):
    id: str
    name: str
    short_name: str
    building_number: str | None
    abbreviation: str | None
    point: PointResponse
    route_point: PointResponse


class RouteRequest(BaseModel):
    origin_id: str
    destination_id: str


class RouteResponse(BaseModel):
    origin_id: str
    destination_id: str
    distance_m: int
    duration_seconds: int
    geometry: list[PointResponse]

    @classmethod
    def from_route(cls, route: Route) -> "RouteResponse":
        return cls(
            origin_id=route.origin_id,
            destination_id=route.destination_id,
            distance_m=route.distance_m,
            duration_seconds=route.duration_seconds,
            geometry=[PointResponse(latitude=point[0], longitude=point[1]) for point in route.geometry],
        )


class SolarPositionResponse(BaseModel):
    observed_at: datetime
    bucket_start: datetime
    latitude: float
    longitude: float
    geometric_altitude_degrees: float
    apparent_altitude_degrees: float
    azimuth_degrees: float
    shadow_azimuth_degrees: float | None
    daylight: bool
    method: str
    reference_url: str

    @classmethod
    def from_solar_position(cls, position: SolarPosition) -> "SolarPositionResponse":
        return cls(
            observed_at=position.observed_at,
            bucket_start=position.bucket_start,
            latitude=position.latitude,
            longitude=position.longitude,
            geometric_altitude_degrees=position.geometric_altitude_degrees,
            apparent_altitude_degrees=position.apparent_altitude_degrees,
            azimuth_degrees=position.azimuth_degrees,
            shadow_azimuth_degrees=position.shadow_azimuth_degrees,
            daylight=position.daylight,
            method=position.method,
            reference_url=SOLAR_REFERENCE_URL,
        )


class TreeShadowResponse(BaseModel):
    tree_id: int | str
    center_m: MetricPointResponse
    height_m: float
    canopy_radius_m: float
    shadow_length_m: float
    length_capped: bool
    polygon_m: list[MetricPointResponse]

    @classmethod
    def from_tree_shadow(cls, shadow: TreeShadow) -> "TreeShadowResponse":
        return cls(
            tree_id=shadow.tree_id,
            center_m=MetricPointResponse(
                easting=shadow.center_m[0],
                northing=shadow.center_m[1],
            ),
            height_m=shadow.height_m,
            canopy_radius_m=shadow.canopy_radius_m,
            shadow_length_m=shadow.shadow_length_m,
            length_capped=shadow.length_capped,
            polygon_m=[
                MetricPointResponse(easting=point[0], northing=point[1])
                for point in shadow.polygon_m
            ],
        )


class TreeShadowCollectionResponse(BaseModel):
    bucket_start: datetime
    bucket_minutes: int
    crs: str
    daylight: bool
    solar_altitude_degrees: float
    shadow_azimuth_degrees: float | None
    eligible_tree_count: int
    excluded_tree_count: int
    shadow_count: int
    shadow_length_cap_m: float
    maximum_generated_shadow_length_m: float
    shadows: list[TreeShadowResponse]

    @classmethod
    def from_tree_shadow_bucket(
        cls,
        bucket: TreeShadowBucket,
    ) -> "TreeShadowCollectionResponse":
        return cls(
            bucket_start=bucket.bucket_start,
            bucket_minutes=TIME_BUCKET_MINUTES,
            crs=bucket.crs,
            daylight=bucket.solar.daylight,
            solar_altitude_degrees=bucket.solar.apparent_altitude_degrees,
            shadow_azimuth_degrees=bucket.solar.shadow_azimuth_degrees,
            eligible_tree_count=bucket.eligible_tree_count,
            excluded_tree_count=bucket.excluded_tree_count,
            shadow_count=len(bucket.shadows),
            shadow_length_cap_m=MAX_TREE_SHADOW_LENGTH_M,
            maximum_generated_shadow_length_m=max(
                (shadow.shadow_length_m for shadow in bucket.shadows),
                default=0,
            ),
            shadows=[TreeShadowResponse.from_tree_shadow(shadow) for shadow in bucket.shadows],
        )


class GeoJsonMultiPolygonGeometry(BaseModel):
    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: list[list[list[tuple[float, float]]]]


class GeoJsonFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: dict[str, str] = Field(default_factory=dict)
    geometry: GeoJsonMultiPolygonGeometry


class GeoJsonFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJsonFeature]


class TreeShadowMapResponse(BaseModel):
    bucket_start: datetime
    bucket_minutes: int
    daylight: bool
    shadow_azimuth_degrees: float | None
    shadow_count: int
    geojson: GeoJsonFeatureCollection

    @classmethod
    def from_tree_shadow_map_bucket(
        cls,
        bucket: TreeShadowMapBucket,
    ) -> "TreeShadowMapResponse":
        geometry = GeoJsonMultiPolygonGeometry(
            coordinates=[[list(polygon)] for polygon in bucket.polygons_wgs84]
        )
        return cls(
            bucket_start=bucket.bucket_start,
            bucket_minutes=TIME_BUCKET_MINUTES,
            daylight=bucket.daylight,
            shadow_azimuth_degrees=bucket.shadow_azimuth_degrees,
            shadow_count=len(bucket.polygons_wgs84),
            geojson=GeoJsonFeatureCollection(
                features=[GeoJsonFeature(geometry=geometry)],
            ),
        )


def building_response(building: Building) -> BuildingResponse:
    route_point = NODES[BUILDING_NODES[building.id]]
    return BuildingResponse(
        id=building.id,
        name=building.name,
        short_name=building.short_name,
        building_number=building.building_number,
        abbreviation=building.abbreviation,
        point=PointResponse(latitude=building.point[0], longitude=building.point[1]),
        route_point=PointResponse(latitude=route_point[0], longitude=route_point[1]),
    )
