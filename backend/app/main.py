from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .campus import BUILDINGS, route_between
from .models import (
    BuildingShadowCollectionResponse,
    BuildingShadowMapResponse,
    BuildingResponse,
    RouteRequest,
    RouteResponse,
    SolarPositionResponse,
    TreeShadowCollectionResponse,
    TreeShadowMapResponse,
    building_response,
)
from .shade.buildings import building_shadow_map_at, building_shadows_at
from .shade.solar import solar_position
from .shade.trees import tree_shadow_map_at, tree_shadows_at


app = FastAPI(
    title="AggieShade API",
    version="0.4.0",
    description="Campus routing and shade-modeling services for AggieShade.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/buildings", response_model=list[BuildingResponse])
def list_buildings() -> list[BuildingResponse]:
    return [building_response(building) for building in BUILDINGS.values()]


@app.get("/shade/solar-position", response_model=SolarPositionResponse)
def get_solar_position(at: datetime) -> SolarPositionResponse:
    """Return TAMU solar geometry for a timezone-aware ISO 8601 timestamp."""

    try:
        position = solar_position(at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SolarPositionResponse.from_solar_position(position)


@app.get("/shade/tree-shadows", response_model=TreeShadowCollectionResponse)
def get_tree_shadows(at: datetime) -> TreeShadowCollectionResponse:
    """Return metric tree-shadow polygons for the instant's 15-minute bucket."""

    try:
        bucket = tree_shadows_at(at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TreeShadowCollectionResponse.from_tree_shadow_bucket(bucket)


@app.get("/shade/tree-shadows/map", response_model=TreeShadowMapResponse)
def get_tree_shadow_map(at: datetime) -> TreeShadowMapResponse:
    """Return map-optimized WGS 84 tree shadows for Expo."""

    try:
        bucket = tree_shadow_map_at(at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TreeShadowMapResponse.from_tree_shadow_map_bucket(bucket)


@app.get("/shade/building-shadows", response_model=BuildingShadowCollectionResponse)
def get_building_shadows(at: datetime) -> BuildingShadowCollectionResponse:
    """Return metric building-shadow polygons for the instant's 15-minute bucket."""

    try:
        bucket = building_shadows_at(at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BuildingShadowCollectionResponse.from_building_shadow_bucket(bucket)


@app.get("/shade/building-shadows/map", response_model=BuildingShadowMapResponse)
def get_building_shadow_map(at: datetime) -> BuildingShadowMapResponse:
    """Return map-optimized WGS 84 building shadows for Expo."""

    try:
        bucket = building_shadow_map_at(at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BuildingShadowMapResponse.from_building_shadow_map_bucket(bucket)


@app.post("/routes", response_model=RouteResponse)
def create_route(request: RouteRequest) -> RouteResponse:
    try:
        route = route_between(request.origin_id, request.destination_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown TAMU building") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RouteResponse.from_route(route)
