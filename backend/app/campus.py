from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import atan2, cos, radians, sin, sqrt


Point = tuple[float, float]


@dataclass(frozen=True)
class Building:
    id: str
    name: str
    short_name: str
    point: Point


@dataclass(frozen=True)
class Route:
    origin_id: str
    destination_id: str
    distance_m: int
    duration_seconds: int
    geometry: tuple[Point, ...]


BUILDINGS: dict[str, Building] = {
    "zachry": Building(
        id="zachry",
        name="Zachry Engineering Education Complex",
        short_name="Zachry",
        point=(30.62142, -96.34079),
    ),
    "evans": Building(
        id="evans",
        name="Sterling C. Evans Library",
        short_name="Evans Library",
        point=(30.61691, -96.33982),
    ),
    "academic": Building(
        id="academic",
        name="Academic Building",
        short_name="Academic",
        point=(30.61559, -96.34086),
    ),
    "msc": Building(
        id="msc",
        name="Memorial Student Center",
        short_name="MSC",
        point=(30.61234, -96.34142),
    ),
    "kyle": Building(
        id="kyle",
        name="Kyle Field",
        short_name="Kyle Field",
        point=(30.61018, -96.34015),
    ),
    "sbisa": Building(
        id="sbisa",
        name="Sbisa Dining Hall",
        short_name="Sbisa",
        point=(30.61793, -96.34424),
    ),
}

# A deliberately small walkway graph for the milestone-one vertical slice.
NODES: dict[str, Point] = {
    **{building.id: building.point for building in BUILDINGS.values()},
    "north_quad": (30.61930, -96.34135),
    "library_walk": (30.61675, -96.34115),
    "military_walk": (30.61420, -96.34125),
    "rudder_walk": (30.61315, -96.34118),
}

EDGE_PAIRS = (
    ("zachry", "north_quad"),
    ("north_quad", "evans"),
    ("north_quad", "sbisa"),
    ("sbisa", "library_walk"),
    ("evans", "library_walk"),
    ("library_walk", "academic"),
    ("library_walk", "military_walk"),
    ("academic", "military_walk"),
    ("military_walk", "rudder_walk"),
    ("rudder_walk", "msc"),
    ("msc", "kyle"),
)


def _distance_m(first: Point, second: Point) -> float:
    earth_radius_m = 6_371_000
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    haversine = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return earth_radius_m * 2 * atan2(sqrt(haversine), sqrt(1 - haversine))


GRAPH: dict[str, list[tuple[str, float]]] = {node_id: [] for node_id in NODES}
for left, right in EDGE_PAIRS:
    distance = _distance_m(NODES[left], NODES[right])
    GRAPH[left].append((right, distance))
    GRAPH[right].append((left, distance))


def _shortest_path(origin_id: str, destination_id: str) -> tuple[list[str], float]:
    queue: list[tuple[float, str]] = [(0.0, origin_id)]
    distances = {origin_id: 0.0}
    previous: dict[str, str] = {}

    while queue:
        distance, node_id = heappop(queue)
        if node_id == destination_id:
            break
        if distance != distances[node_id]:
            continue
        for neighbor, edge_distance in GRAPH[node_id]:
            candidate = distance + edge_distance
            if candidate < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate
                previous[neighbor] = node_id
                heappush(queue, (candidate, neighbor))

    if destination_id not in distances:
        raise RuntimeError("No walking route connects these buildings")

    path = [destination_id]
    while path[-1] != origin_id:
        path.append(previous[path[-1]])
    path.reverse()
    return path, distances[destination_id]


def route_between(origin_id: str, destination_id: str) -> Route:
    if origin_id not in BUILDINGS or destination_id not in BUILDINGS:
        raise KeyError("Unknown TAMU building")
    if origin_id == destination_id:
        raise ValueError("Choose two different TAMU buildings")

    path, distance = _shortest_path(origin_id, destination_id)
    rounded_distance = round(distance)
    return Route(
        origin_id=origin_id,
        destination_id=destination_id,
        distance_m=rounded_distance,
        duration_seconds=round(distance / 1.4),
        geometry=tuple(NODES[node_id] for node_id in path),
    )
