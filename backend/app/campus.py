from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
import json
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Mapping


Point = tuple[float, float]


@dataclass(frozen=True)
class Building:
    id: str
    name: str
    short_name: str
    building_number: str | None
    abbreviation: str | None
    point: Point


@dataclass(frozen=True)
class Route:
    origin_id: str
    destination_id: str
    distance_m: int
    duration_seconds: int
    geometry: tuple[Point, ...]


COMMON_BUILDING_IDS = {
    "0518": "zachry",
    "0468": "evans",
    "0462": "academic",
    "0454": "msc",
    "0367": "kyle",
    "0495": "sbisa",
}
COMMON_SHORT_NAMES = {
    "zachry": "Zachry",
    "evans": "Evans Library",
    "academic": "Academic",
    "msc": "MSC",
    "kyle": "Kyle Field",
    "sbisa": "Sbisa",
}
COMMON_BUILDING_ORDER = tuple(COMMON_SHORT_NAMES)


def _ring_area_twice(ring: list[list[float]]) -> float:
    return sum(
        point[0] * ring[(index + 1) % len(ring)][1]
        - ring[(index + 1) % len(ring)][0] * point[1]
        for index, point in enumerate(ring)
    )


def _ring_centroid(ring: list[list[float]]) -> Point:
    area_twice = _ring_area_twice(ring)
    if abs(area_twice) < 1e-15:
        return (
            sum(point[1] for point in ring) / len(ring),
            sum(point[0] for point in ring) / len(ring),
        )

    longitude_sum = 0.0
    latitude_sum = 0.0
    for index, point in enumerate(ring):
        next_point = ring[(index + 1) % len(ring)]
        cross = point[0] * next_point[1] - next_point[0] * point[1]
        longitude_sum += (point[0] + next_point[0]) * cross
        latitude_sum += (point[1] + next_point[1]) * cross
    return latitude_sum / (3 * area_twice), longitude_sum / (3 * area_twice)


def _footprint_center(raw_rings: object) -> Point | None:
    if not isinstance(raw_rings, list):
        return None

    rings: list[list[list[float]]] = []
    for raw_ring in raw_rings:
        if not isinstance(raw_ring, list) or len(raw_ring) < 4:
            continue
        try:
            ring = [[float(point[0]), float(point[1])] for point in raw_ring]
        except (IndexError, TypeError, ValueError):
            continue
        rings.append(ring)

    if not rings:
        return None
    outer_ring = max(rings, key=lambda ring: abs(_ring_area_twice(ring)))
    return _ring_centroid(outer_ring)


def _slug(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() else " "
        for character in value.casefold()
    )
    return "-".join(normalized.split())


def _load_buildings() -> dict[str, Building]:
    data_path = Path(__file__).with_name("data") / "shade_features.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    buildings: list[Building] = []
    used_ids: set[str] = set()

    for feature in data["buildings"]:
        name = str(feature.get("name") or "").strip()
        building_number = str(feature.get("building_number") or "").strip() or None
        abbreviation = str(feature.get("abbreviation") or "").strip() or None
        point = _footprint_center(feature.get("footprint_wgs84"))
        if not name or point is None:
            continue

        source_id = str(feature.get("source_id") or "unknown")
        building_id = COMMON_BUILDING_IDS.get(building_number or "")
        if building_id is None:
            building_id = f"tamu-{_slug(building_number or source_id)}"
        if building_id in used_ids:
            building_id = f"{building_id}-{_slug(source_id)}"
        used_ids.add(building_id)

        short_name = COMMON_SHORT_NAMES.get(building_id)
        if short_name is None:
            short_name = (
                abbreviation
                if abbreviation and not abbreviation.replace(".", "").isdigit()
                else name
            )
        buildings.append(
            Building(
                id=building_id,
                name=name,
                short_name=short_name,
                building_number=building_number,
                abbreviation=abbreviation,
                point=point,
            )
        )

    common_order = {
        building_id: index
        for index, building_id in enumerate(COMMON_BUILDING_ORDER)
    }
    buildings.sort(
        key=lambda building: (
            common_order.get(building.id, len(common_order)),
            building.name.casefold(),
            building.building_number or "",
        )
    )
    return {building.id: building for building in buildings}


BUILDINGS = _load_buildings()


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
EDGE_DISTANCES_M = {
    frozenset((node_id, neighbor)): distance
    for node_id, neighbors in GRAPH.items()
    for neighbor, distance in neighbors
}
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


def _shortest_path(
    origin_node: str,
    destination_node: str,
    edge_costs: Mapping[frozenset[str], float] | None = None,
) -> tuple[list[str], float]:
    queue: list[tuple[float, str]] = [(0.0, origin_node)]
    costs = {origin_node: 0.0}
    previous: dict[str, str] = {}

    while queue:
        cost, node_id = heappop(queue)
        if node_id == destination_node:
            break
        if cost != costs[node_id]:
            continue
        for neighbor, edge_distance in GRAPH[node_id]:
            edge_key = frozenset((node_id, neighbor))
            traversal_cost = edge_costs[edge_key] if edge_costs is not None else edge_distance
            candidate = cost + traversal_cost
            if candidate < costs.get(neighbor, float("inf")):
                costs[neighbor] = candidate
                previous[neighbor] = node_id
                heappush(queue, (candidate, neighbor))

    if destination_node not in costs:
        raise RuntimeError("No pedestrian route connects these buildings")

    path = [destination_node]
    while path[-1] != origin_node:
        path.append(previous[path[-1]])
    path.reverse()
    distance = sum(
        EDGE_DISTANCES_M[frozenset((left, right))]
        for left, right in zip(path, path[1:])
    )
    return path, distance


def route_between(origin_id: str, destination_id: str) -> Route:
    if origin_id not in BUILDINGS or destination_id not in BUILDINGS:
        raise KeyError("Unknown TAMU building")
    if origin_id == destination_id:
        raise ValueError("Choose two different TAMU buildings")
    if BUILDING_NODES[origin_id] == BUILDING_NODES[destination_id]:
        raise RuntimeError(
            "These buildings share the same pedestrian access point; no distinct route can be drawn"
        )

    path, distance = _shortest_path(BUILDING_NODES[origin_id], BUILDING_NODES[destination_id])
    rounded_distance = round(distance)
    return Route(
        origin_id=origin_id,
        destination_id=destination_id,
        distance_m=rounded_distance,
        duration_seconds=round(distance / 1.4),
        geometry=tuple(NODES[node_id] for node_id in path),
    )
