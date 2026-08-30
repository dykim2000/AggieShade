from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
import json
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path


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


def _distance_m(first: Point, second: Point) -> float:
    earth_radius_m = 6_371_000
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    haversine = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return earth_radius_m * 2 * atan2(sqrt(haversine), sqrt(1 - haversine))


def _load_pedestrian_graph() -> tuple[
    dict[str, Point],
    dict[str, list[tuple[str, float]]],
    frozenset[frozenset[str]],
]:
    data_path = Path(__file__).with_name("data") / "pedestrian_graph.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    nodes = {str(node_id): (latitude, longitude) for node_id, latitude, longitude in data["nodes"]}
    graph: dict[str, list[tuple[str, float]]] = {node_id: [] for node_id in nodes}
    edge_keys: set[frozenset[str]] = set()

    for left_id, right_id, distance, _highway in data["edges"]:
        left = str(left_id)
        right = str(right_id)
        graph[left].append((right, distance))
        graph[right].append((left, distance))
        edge_keys.add(frozenset((left, right)))

    return nodes, graph, frozenset(edge_keys)


def _largest_component(graph: dict[str, list[tuple[str, float]]]) -> frozenset[str]:
    unvisited = set(graph)
    largest: set[str] = set()

    while unvisited:
        start = unvisited.pop()
        component = {start}
        stack = [start]
        while stack:
            node_id = stack.pop()
            for neighbor, _distance in graph[node_id]:
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        if len(component) > len(largest):
            largest = component

    return frozenset(largest)


NODES, GRAPH, EDGE_KEYS = _load_pedestrian_graph()
ROUTABLE_NODE_IDS = _largest_component(GRAPH)
BUILDING_NODES = {
    building_id: min(
        ROUTABLE_NODE_IDS,
        key=lambda node_id: _distance_m(building.point, NODES[node_id]),
    )
    for building_id, building in BUILDINGS.items()
}
BUILDING_SNAP_DISTANCE_M = {
    building_id: _distance_m(BUILDINGS[building_id].point, NODES[node_id])
    for building_id, node_id in BUILDING_NODES.items()
}


def _shortest_path(origin_node: str, destination_node: str) -> tuple[list[str], float]:
    queue: list[tuple[float, str]] = [(0.0, origin_node)]
    distances = {origin_node: 0.0}
    previous: dict[str, str] = {}

    while queue:
        distance, node_id = heappop(queue)
        if node_id == destination_node:
            break
        if distance != distances[node_id]:
            continue
        for neighbor, edge_distance in GRAPH[node_id]:
            candidate = distance + edge_distance
            if candidate < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate
                previous[neighbor] = node_id
                heappush(queue, (candidate, neighbor))

    if destination_node not in distances:
        raise RuntimeError("No pedestrian route connects these buildings")

    path = [destination_node]
    while path[-1] != origin_node:
        path.append(previous[path[-1]])
    path.reverse()
    return path, distances[destination_node]


def route_between(origin_id: str, destination_id: str) -> Route:
    if origin_id not in BUILDINGS or destination_id not in BUILDINGS:
        raise KeyError("Unknown TAMU building")
    if origin_id == destination_id:
        raise ValueError("Choose two different TAMU buildings")

    path, distance = _shortest_path(BUILDING_NODES[origin_id], BUILDING_NODES[destination_id])
    rounded_distance = round(distance)
    return Route(
        origin_id=origin_id,
        destination_id=destination_id,
        distance_m=rounded_distance,
        duration_seconds=round(distance / 1.4),
        geometry=tuple(NODES[node_id] for node_id in path),
    )
