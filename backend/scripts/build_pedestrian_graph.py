"""Build the bundled pedestrian graph from an OpenStreetMap XML extract.

Usage:
    python scripts/build_pedestrian_graph.py campus.osm app/data/pedestrian_graph.json
"""

from __future__ import annotations

import argparse
import json
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
import xml.etree.ElementTree as ET


WALKABLE_HIGHWAYS = {"footway", "path", "pedestrian", "steps"}
BLOCKED_ACCESS = {"no", "private"}


def distance_m(first: tuple[float, float], second: tuple[float, float]) -> float:
    earth_radius_m = 6_371_000
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    haversine = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return earth_radius_m * 2 * atan2(sqrt(haversine), sqrt(1 - haversine))


def is_walkable(tags: dict[str, str]) -> bool:
    highway = tags.get("highway")
    if tags.get("access") in BLOCKED_ACCESS or tags.get("foot") in BLOCKED_ACCESS:
        return False
    if highway in WALKABLE_HIGHWAYS:
        return True
    return highway == "cycleway" and tags.get("foot") in {"yes", "designated", "permissive"}


def build_graph(source: Path) -> dict[str, object]:
    root = ET.parse(source).getroot()
    all_nodes = {
        int(node.attrib["id"]): (float(node.attrib["lat"]), float(node.attrib["lon"]))
        for node in root.findall("node")
    }

    used_nodes: set[int] = set()
    edges: dict[tuple[int, int], tuple[float, str]] = {}
    way_count = 0

    for way in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag")}
        if not is_walkable(tags):
            continue

        node_ids = [int(node.attrib["ref"]) for node in way.findall("nd")]
        highway = tags["highway"]
        way_count += 1
        for left, right in zip(node_ids, node_ids[1:]):
            if left not in all_nodes or right not in all_nodes or left == right:
                continue
            used_nodes.update((left, right))
            key = (min(left, right), max(left, right))
            candidate = (distance_m(all_nodes[left], all_nodes[right]), highway)
            if key not in edges or candidate[0] < edges[key][0]:
                edges[key] = candidate

    return {
        "source": {
            "name": "OpenStreetMap",
            "url": "https://www.openstreetmap.org/",
            "license": "Open Data Commons Open Database License (ODbL) 1.0",
            "extract_bbox": [-96.346, 30.609, -96.338, 30.6225],
        },
        "nodes": [
            [node_id, round(all_nodes[node_id][0], 7), round(all_nodes[node_id][1], 7)]
            for node_id in sorted(used_nodes)
        ],
        "edges": [
            [left, right, round(distance, 2), highway]
            for (left, right), (distance, highway) in sorted(edges.items())
        ],
        "way_count": way_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    graph = build_graph(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(graph['nodes'])} nodes and {len(graph['edges'])} edges "
        f"from {graph['way_count']} pedestrian ways to {args.output}"
    )


if __name__ == "__main__":
    main()
