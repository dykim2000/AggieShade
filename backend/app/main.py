from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .campus import BUILDINGS, route_between
from .models import BuildingResponse, RouteRequest, RouteResponse, SolarPositionResponse, building_response
from .shade.solar import solar_position


app = FastAPI(
    title="AggieShade API",
    version="0.2.0",
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
