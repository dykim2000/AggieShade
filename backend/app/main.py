from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .campus import BUILDINGS, route_between
from .models import BuildingResponse, RouteRequest, RouteResponse, building_response


app = FastAPI(
    title="AggieShade API",
    version="0.1.0",
    description="The first AggieShade campus-routing vertical slice.",
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
