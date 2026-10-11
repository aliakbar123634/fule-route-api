from unittest.mock import patch

from django.test import SimpleTestCase

from routing.services.fuel_stop_service import (
    calculate_distance_miles,
    calculate_fuel_needed,
    filter_stations_near_route,
    select_fuel_stops,
)
from routing.services.route_station_service import (
    find_stations_along_route,
)


class FuelStopServiceTests(SimpleTestCase):

    def test_distance_between_same_coordinates_is_zero(self):
        distance = calculate_distance_miles(
            32.7767, -96.7970,
            32.7767, -96.7970,
        )

        self.assertEqual(distance, 0)

    def test_calculate_fuel_needed(self):
        self.assertEqual(calculate_fuel_needed(100), 10)

    def test_filter_stations_orders_them_along_route(self):
        route = [
            [-97.0, 32.0],
            [-96.9, 32.0],
            [-96.8, 32.0],
        ]

        stations = [
            {
                "name": "Station B",
                "latitude": 32.0,
                "longitude": -96.81,
            },
            {
                "name": "Station A",
                "latitude": 32.0,
                "longitude": -96.99,
            },
        ]

        result = filter_stations_near_route(
            stations,
            route,
            corridor_miles=5,
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Station A")
        self.assertLess(
            result[0]["route_position_miles"],
            result[1]["route_position_miles"],
        )

    def test_selects_cheapest_reachable_station(self):
        stations = [
            {
                "name": "Expensive",
                "route_position_miles": 400,
                "retail_price": 4.00,
            },
            {
                "name": "Cheapest",
                "route_position_miles": 300,
                "retail_price": 3.00,
            },
        ]

        result = select_fuel_stops(
            route_distance_miles=700,
            candidate_stations=stations,
        )

        self.assertEqual(len(result["stops"]), 1)
        self.assertEqual(
            result["stops"][0]["name"],
            "Cheapest",
        )


class RouteStationServiceTests(SimpleTestCase):

    @patch(
        "routing.services.route_station_service."
        "get_fuel_stations_nearby"
    )
    def test_finds_and_deduplicates_stations(self, mock_nearby):
        mock_nearby.return_value = [
            {
                "osm_type": "node",
                "osm_id": 101,
                "name": "Fuel Station A",
                "brand": "Example",
                "latitude": 32.0,
                "longitude": -96.99,
            },
            {
                "osm_type": "node",
                "osm_id": 101,
                "name": "Fuel Station A",
                "brand": "Example",
                "latitude": 32.0,
                "longitude": -96.99,
            },
        ]

        route = [
            [-97.0, 32.0],
            [-96.99, 32.0],
            [-96.98, 32.0],
        ]

        result = find_stations_along_route(
            route_coordinates=route,
            corridor_miles=5,
            sample_spacing_miles=100,
            search_radius_miles=5,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["osm_id"], 101)
        self.assertEqual(mock_nearby.call_count, 2)

    def test_route_with_no_intermediate_stop_returns_no_stops(self):
        result = select_fuel_stops(
            route_distance_miles=300,
            candidate_stations=[],
        )

        self.assertEqual(result["stops"], [])
        self.assertEqual(result["estimated_fuel_cost"], 0.0)

    def test_long_route_without_stations_is_reported_as_infeasible(self):
        with self.assertRaisesRegex(
            ValueError,
            "No feasible fuel-stop route found",
        ):
            select_fuel_stops(
                route_distance_miles=1200,
                candidate_stations=[],
            )

    def test_station_beyond_destination_does_not_make_route_feasible(self):
        stations = [
            {
                "name": "Beyond Destination",
                "route_position_miles": 800,
                "retail_price": 3.00,
            },
        ]

        with self.assertRaisesRegex(
            ValueError,
            "No feasible fuel-stop route found",
        ):
            select_fuel_stops(
                route_distance_miles=700,
                candidate_stations=stations,
            )
