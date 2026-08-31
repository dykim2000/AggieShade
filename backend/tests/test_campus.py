import unittest

from app.campus import (
    BUILDINGS,
    BUILDING_NODES,
    BUILDING_SNAP_DISTANCE_M,
    EDGE_KEYS,
    NODES,
    ROUTABLE_NODE_IDS,
    route_between,
)


class CampusRoutingTests(unittest.TestCase):
    def test_all_listed_buildings_are_connected(self) -> None:
        self.assertEqual(set(BUILDING_NODES.values()) - ROUTABLE_NODE_IDS, set())

    def test_all_named_tamu_buildings_are_searchable(self) -> None:
        self.assertEqual(len(BUILDINGS), 114)
        self.assertEqual(len({building.name for building in BUILDINGS.values()}), 113)
        self.assertEqual(BUILDINGS["zachry"].building_number, "0518")
        self.assertEqual(BUILDINGS["msc"].abbreviation, "MSC")
        self.assertIn("tamu-1530", BUILDINGS)

    def test_route_contains_metrics_and_geometry(self) -> None:
        route = route_between("zachry", "msc")
        self.assertGreater(route.distance_m, 0)
        self.assertGreater(route.duration_seconds, 0)
        self.assertEqual(route.geometry[0], NODES[BUILDING_NODES["zachry"]])
        self.assertEqual(route.geometry[-1], NODES[BUILDING_NODES["msc"]])
        self.assertGreater(len(route.geometry), 10)

    def test_route_only_uses_pedestrian_graph_edges(self) -> None:
        node_ids_by_point = {point: node_id for node_id, point in NODES.items()}
        route = route_between("sbisa", "kyle")
        for left, right in zip(route.geometry, route.geometry[1:]):
            edge = frozenset((node_ids_by_point[left], node_ids_by_point[right]))
            self.assertIn(edge, EDGE_KEYS)

    def test_buildings_snap_to_nearby_pedestrian_paths(self) -> None:
        for building_id, distance in BUILDING_SNAP_DISTANCE_M.items():
            with self.subTest(building=building_id):
                self.assertLess(distance, 140)

    def test_same_building_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            route_between("zachry", "zachry")

    def test_distinct_buildings_at_same_access_point_are_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            route_between("tamu-1427", "tamu-0426")

    def test_unknown_building_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            route_between("not-a-building", "zachry")


if __name__ == "__main__":
    unittest.main()
