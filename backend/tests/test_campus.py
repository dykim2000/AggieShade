import unittest

from app.campus import BUILDINGS, route_between


class CampusRoutingTests(unittest.TestCase):
    def test_all_listed_buildings_are_connected(self) -> None:
        building_ids = list(BUILDINGS)
        for origin_id in building_ids:
            for destination_id in building_ids:
                if origin_id != destination_id:
                    self.assertGreater(route_between(origin_id, destination_id).distance_m, 0)

    def test_route_contains_metrics_and_geometry(self) -> None:
        route = route_between("zachry", "msc")
        self.assertGreater(route.distance_m, 0)
        self.assertGreater(route.duration_seconds, 0)
        self.assertEqual(route.geometry[0], BUILDINGS["zachry"].point)
        self.assertEqual(route.geometry[-1], BUILDINGS["msc"].point)

    def test_same_building_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            route_between("zachry", "zachry")

    def test_unknown_building_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            route_between("not-a-building", "zachry")


if __name__ == "__main__":
    unittest.main()
