from pydantic import BaseModel

from .campus import BUILDING_NODES, NODES, Building, Route


class PointResponse(BaseModel):
    latitude: float
    longitude: float


class BuildingResponse(BaseModel):
    id: str
    name: str
    short_name: str
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


def building_response(building: Building) -> BuildingResponse:
    route_point = NODES[BUILDING_NODES[building.id]]
    return BuildingResponse(
        id=building.id,
        name=building.name,
        short_name=building.short_name,
        point=PointResponse(latitude=building.point[0], longitude=building.point[1]),
        route_point=PointResponse(latitude=route_point[0], longitude=route_point[1]),
    )
