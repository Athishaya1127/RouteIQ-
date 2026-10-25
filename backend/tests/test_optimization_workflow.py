import unittest
import csv
from datetime import datetime, timedelta
import math
from pathlib import Path
import tempfile
from unittest.mock import patch
from unittest.mock import Mock

from fastapi import HTTPException

from backend.config import settings
from backend.ml.road_predictor import RoadPredictor, road_predictor
from backend.ml.train_road_predictor import train_from_csv
from backend.models.schemas import OptimizeRequest
from backend.services.cost_engine import build_cost_matrix
from backend.services.optimization_workflow import optimize_deliveries
from backend.services.optimizer import solve_vrp
from backend.services.routing_api import _as_matrix, get_osrm_route_details
from backend.services.route_validator import validate_routes
from backend.services.traffic_prediction import predict_trip_matrices


class CostMatrixTests(unittest.TestCase):
    def test_legacy_predictor_remains_compatible(self):
        prediction = road_predictor.predict_congestion(
            hour=9,
            day=0,
            hist=0.5,
            speed=20,
            neighbor=0.5,
            upstream=0.5,
            zone="T Nagar",
            density=0.5,
        )

        self.assertTrue(0.1 <= prediction <= 0.95)

    def test_historical_trainer_uses_chronological_evaluation(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            csv_path = Path(temp_directory) / "traffic.csv"
            model_path = Path(temp_directory) / "model.pkl"
            with csv_path.open("w", newline="", encoding="utf-8") as traffic_file:
                writer = csv.DictWriter(
                    traffic_file,
                    fieldnames=[
                        "timestamp",
                        "zone",
                        "congestion",
                        "vehicle_density",
                        "avg_speed",
                    ],
                )
                writer.writeheader()
                start = datetime(2026, 1, 1)
                for index in range(30):
                    writer.writerow(
                        {
                            "timestamp": (start + timedelta(minutes=10 * index)).isoformat(),
                            "zone": "T Nagar",
                            "congestion": round(0.2 + (index % 6) * 0.1, 2),
                            "vehicle_density": round(0.2 + (index % 5) * 0.1, 2),
                            "avg_speed": 35 - index % 10,
                        }
                    )

            metadata = train_from_csv(csv_path, model_path)

            self.assertTrue(model_path.exists())
            self.assertEqual(metadata["training_source"], "historical_csv")
            self.assertGreater(metadata["rows"]["train"], 0)
            self.assertGreater(metadata["rows"]["validation"], 0)
            self.assertGreater(metadata["rows"]["test"], 0)
            self.assertIn("mae", metadata["metrics"]["test"])
            predictor = RoadPredictor.__new__(RoadPredictor)
            predictor.model = metadata["model"]
            predictor.model_uses_zone = True
            prediction = predictor.predict_congestion(
                hour=9,
                day=0,
                hist=0.5,
                speed=20,
                neighbor=0.5,
                upstream=0.5,
                zone="T Nagar",
                density=0.5,
            )
            self.assertTrue(0.1 <= prediction <= 0.95)

    def test_unreachable_matrix_entries_remain_unreachable(self):
        self.assertTrue(math.isinf(_as_matrix([[0.0, None]], 1.0)[0][1]))

    def test_congestion_penalty_is_a_distinct_fourth_cost_term(self):
        distance = [[0.0, 1.0], [1.0, 0.0]]
        duration = [[0.0, 10.0], [10.0, 0.0]]
        congestion = [[0.0, 0.8], [0.6, 0.0]]

        costs, _, _ = build_cost_matrix(
            distance,
            duration,
            predicted_duration_matrix=duration,
            congestion_matrix=congestion,
            weights=(0.0, 0.0, 0.0, 1.0),
            congestion_threshold=0.6,
        )

        self.assertAlmostEqual(costs[0][1], 0.5)
        self.assertAlmostEqual(costs[1][0], 0.0)

    def test_duration_objective_uses_predicted_duration_matrix(self):
        distances = [[0.0, 1.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0]]
        baseline = [[0.0, 20.0, 5.0], [20.0, 0.0, 5.0], [20.0, 5.0, 0.0]]
        predicted = [[0.0, 5.0, 20.0], [5.0, 0.0, 20.0], [5.0, 20.0, 0.0]]

        costs, _, _ = build_cost_matrix(
            distances,
            baseline,
            predicted_duration_matrix=predicted,
            weights=(1.0, 0.0, 0.0, 0.0),
        )

        self.assertLess(costs[0][1], costs[0][2])
        self.assertAlmostEqual(costs[0][1], 0.0)
        self.assertAlmostEqual(costs[0][2], 1.0)

    def test_cost_weights_apply_delay_before_distance(self):
        distances = [
            [0.0, 1.0, 3.0],
            [1.0, 0.0, 2.0],
            [3.0, 2.0, 0.0],
        ]
        baseline = [[0.0, 10.0, 10.0], [10.0, 0.0, 10.0], [10.0, 10.0, 0.0]]
        predicted = [[0.0, 20.0, 10.0], [10.0, 0.0, 15.0], [10.0, 15.0, 0.0]]
        congestion = [
            [0.0, 0.8, 0.6],
            [0.6, 0.0, 0.7],
            [0.6, 0.7, 0.0],
        ]

        costs, _, _ = build_cost_matrix(
            distances,
            baseline,
            predicted_duration_matrix=predicted,
            congestion_matrix=congestion,
            weights=(0.4, 0.3, 0.2, 0.1),
            congestion_threshold=0.6,
        )

        # Arc 0->1 is worst for duration and delay, best for distance, and
        # receives half the maximum congestion premium: .4 + .3 + 0 + .05.
        self.assertAlmostEqual(costs[0][1], 0.75)
        # Arc 0->2 is best for duration and delay, worst for distance.
        self.assertAlmostEqual(costs[0][2], 0.2)

    def test_solver_requires_shop_customer_coverage_and_correct_depot_end(self):
        size = 7
        matrix = [
            [0.0 if origin == destination else 1.0 for destination in range(size)]
            for origin in range(size)
        ]
        routes = solve_vrp(
            matrix,
            matrix,
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=2,
            starts=[0, 1],
            ends=[0, 1],
            demands=[0, 0, 0, 0, 1, 1, 1],
            vehicle_capacities=[2, 2],
            max_route_duration=60,
        )

        self.assertIsNotNone(routes)
        self.assertEqual(routes[0][0], 0)
        self.assertEqual(routes[0][1], 2)
        self.assertEqual(routes[0][-1], 0)
        self.assertEqual(routes[1][0], 1)
        self.assertEqual(routes[1][1], 3)
        self.assertEqual(routes[1][-1], 1)
        self.assertCountEqual(
            [node for route in routes for node in route if node >= 4],
            [4, 5, 6],
        )
        self.assertEqual(
            validate_routes(
                routes,
                {4, 5, 6},
                matrix,
                matrix,
                [0] * size,
                [0, 0, 0, 0, 1, 1, 1],
                [2, 2],
                {},
                60,
                [0, 1],
                [0, 1],
            ),
            [],
        )

    def test_unreachable_required_shop_leg_is_infeasible(self):
        size = 3
        costs = [[0.0 if i == j else 1.0 for j in range(size)] for i in range(size)]
        durations = [row[:] for row in costs]
        costs[0][1] = math.inf
        durations[0][1] = math.inf

        routes = solve_vrp(
            costs,
            durations,
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=1,
            starts=[0],
            ends=[0],
            max_route_duration=60,
            time_limit_seconds=1,
        )

        self.assertIsNone(routes)

    def test_unreachable_customer_is_not_given_a_zero_time_arc(self):
        size = 4
        costs = [[0.0 if i == j else 1.0 for j in range(size)] for i in range(size)]
        durations = [row[:] for row in costs]
        for origin in range(size):
            if origin != 2:
                costs[origin][2] = math.inf
                durations[origin][2] = math.inf

        routes = solve_vrp(
            costs,
            durations,
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=1,
            starts=[0],
            ends=[0],
            max_route_duration=60,
            time_limit_seconds=1,
        )

        self.assertIsNone(routes)

    @patch("backend.services.routing_api.requests.get")
    def test_osrm_geometry_uses_actual_step_boundaries(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "Ok",
            "routes": [{
                "geometry": {"coordinates": [[0, 0], [0.5, 0], [1, 0], [1, 1]]},
                "legs": [
                    {
                        "distance": 1000,
                        "duration": 60,
                        "steps": [{
                            "geometry": {"coordinates": [[0, 0], [0.5, 0], [1, 0]]}
                        }],
                    },
                    {
                        "distance": 1000,
                        "duration": 90,
                        "steps": [{
                            "geometry": {"coordinates": [[1, 0], [1, 1]]}
                        }],
                    },
                ],
            }],
        }
        mock_get.return_value = mock_response

        geometry, legs = get_osrm_route_details([[0, 0], [1, 0], [1, 1]])

        self.assertEqual(
            legs[0]["geometry"],
            [[0, 0], [0, 0.5], [0, 1]],
        )
        self.assertEqual(legs[1]["geometry"], [[0, 1], [1, 1]])
        self.assertEqual(geometry, [[0, 0], [0, 0.5], [0, 1], [1, 1]])
        self.assertIn("steps=true", mock_get.call_args.args[0])

    def test_traffic_prediction_changes_trip_duration(self):
        class Point:
            lat = 13.0
            lng = 80.0

        with patch(
            "backend.services.traffic_prediction.road_predictor.predict_congestion",
            return_value=0.5,
        ):
            predicted, congestion = predict_trip_matrices(
                [Point(), Point()],
                [[0.0, 10.0], [10.0, 0.0]],
                datetime(2026, 10, 25, 9, 0),
            )

        self.assertAlmostEqual(predicted[0][1], 20.0)
        self.assertEqual(congestion[0][1], 0.5)


class OptimizationWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_delivery_window_beyond_route_horizon_returns_422(self):
        request = OptimizeRequest(
            selected_partner_id="partner",
            selected_shop_id="shop",
            locations=[
                {"id": "shop", "type": "shop", "lat": 13.0, "lng": 80.0},
                {"id": "partner", "type": "partner", "lat": 13.1, "lng": 80.1},
                {
                    "id": "customer",
                    "type": "customer",
                    "lat": 13.2,
                    "lng": 80.2,
                    "shop_id": "shop",
                    "ready_after_minutes": 0,
                    "due_by_minutes": settings.MAX_ROUTE_DURATION_MINS + 1,
                },
            ],
        )
        matrix = [
            [0.0 if origin == destination else 1.0 for destination in range(3)]
            for origin in range(3)
        ]

        with (
            patch(
                "backend.services.optimization_workflow.get_ors_matrix",
                return_value=(matrix, matrix),
            ),
            patch(
                "backend.services.optimization_workflow.predict_trip_matrices",
                return_value=(matrix, [[0.0] * 3 for _ in range(3)]),
            ),
            self.assertRaises(HTTPException) as error,
        ):
            await optimize_deliveries(request)

        self.assertEqual(error.exception.status_code, 422)

    async def test_jointly_assigns_customers_under_vehicle_capacities(self):
        request = OptimizeRequest(
            selected_partner_id="partner-1",
            selected_shop_id="shop",
            departure_hour=9,
            locations=[
                {"id": "shop", "type": "shop", "lat": 13.08, "lng": 80.27},
                {
                    "id": "partner-1",
                    "type": "partner",
                    "lat": 13.07,
                    "lng": 80.26,
                    "capacity": 1,
                },
                {
                    "id": "partner-2",
                    "type": "partner",
                    "lat": 13.06,
                    "lng": 80.25,
                    "capacity": 1,
                },
                {
                    "id": "customer-1",
                    "type": "customer",
                    "lat": 13.05,
                    "lng": 80.24,
                    "shop_id": "shop",
                    "ready_after_minutes": 5,
                    "due_by_minutes": 120,
                    "service_minutes": 5,
                },
                {
                    "id": "customer-2",
                    "type": "customer",
                    "lat": 13.04,
                    "lng": 80.23,
                    "shop_id": "shop",
                    "ready_after_minutes": 0,
                    "due_by_minutes": 120,
                },
            ],
        )
        matrix_size = 6
        distances = [
            [0.0 if i == j else 1.0 for j in range(matrix_size)]
            for i in range(matrix_size)
        ]
        durations = [
            [0.0 if i == j else 1.0 for j in range(matrix_size)]
            for i in range(matrix_size)
        ]
        predicted_durations = [
            [0.0 if i == j else 1.25 for j in range(matrix_size)]
            for i in range(matrix_size)
        ]
        congestion = [
            [0.0 if i == j else 0.2 for j in range(matrix_size)]
            for i in range(matrix_size)
        ]

        def fake_directions(locations):
            geometry = [[location[1], location[0]] for location in locations]
            legs = [
                {
                    "distance": 1.0,
                    "duration": 1.0,
                    "geometry": geometry[index:index + 2],
                }
                for index in range(len(locations) - 1)
            ]
            return geometry, legs

        with (
            patch(
                "backend.services.optimization_workflow.get_ors_matrix",
                return_value=(distances, durations),
            ),
            patch(
                "backend.services.optimization_workflow.predict_trip_matrices",
                return_value=(predicted_durations, congestion),
            ),
            patch(
                "backend.services.optimization_workflow.get_full_route_details",
                side_effect=fake_directions,
            ),
        ):
            result = await optimize_deliveries(request)

        self.assertTrue(result["validation"]["is_valid"])
        self.assertEqual(result["validation"]["orders_served"], 2)
        self.assertEqual(result["active_routes_count"], 2)
        self.assertTrue(
            {
                "routes",
                "total_distance",
                "total_duration",
                "fuel",
                "cost",
                "traffic_level",
                "route_warnings",
            }.issubset(result)
        )
        assigned = [
            customer_id
            for route in result["routes"].values()
            for customer_id in route["arrival_times"]
        ]
        self.assertCountEqual(assigned, ["customer-1", "customer-2"])
        self.assertEqual(
            result["routes"]["partner-1"]["arrival_times"].get("customer-1")
            or result["routes"]["partner-2"]["arrival_times"].get("customer-1"),
            "09:05 AM",
        )
        self.assertEqual(
            result["cost_weights"],
            {
                "predicted_duration": 0.4,
                "predicted_delay": 0.3,
                "road_distance": 0.2,
                "congestion_penalty": 0.1,
            },
        )

        location_by_id = {location.id: location for location in request.locations}
        services_by_id = {
            location.id: location.service_minutes
            for location in request.locations
        }
        for route in result["routes"].values():
            self.assertTrue(
                {
                    "partner_id",
                    "sequence",
                    "arrival_times",
                    "segments",
                    "total_distance",
                    "total_duration",
                    "full_route_geometry",
                }.issubset(route)
            )
            self.assertEqual(len(route["segments"]), len(route["sequence"]) - 1)
            expected_geometry = [
                [location_by_id[location_id].lat, location_by_id[location_id].lng]
                for location_id in route["sequence"]
            ]
            self.assertEqual(route["full_route_geometry"], expected_geometry)

            elapsed = 0.0
            for (origin, destination), segment in zip(
                zip(route["sequence"], route["sequence"][1:]),
                route["segments"],
            ):
                self.assertTrue(
                    {
                        "from_id",
                        "to_id",
                        "distance",
                        "duration",
                        "geometry",
                        "congestion",
                        "estimated_arrival_time",
                        "waiting_minutes",
                    }.issubset(segment)
                )
                self.assertEqual(segment["from_id"], origin)
                self.assertEqual(segment["to_id"], destination)
                self.assertEqual(
                    segment["geometry"],
                    [
                        expected_geometry[route["sequence"].index(origin)],
                        expected_geometry[route["sequence"].index(destination)],
                    ],
                )
                self.assertAlmostEqual(segment["duration"], 1.25)

                elapsed += (
                    services_by_id[origin]
                    + segment["duration"]
                    + segment["waiting_minutes"]
                )
                expected_arrival = (
                    datetime(2026, 1, 1, 9)
                    + timedelta(minutes=elapsed)
                ).strftime("%I:%M %p")
                self.assertEqual(segment["estimated_arrival_time"], expected_arrival)
                if destination.startswith("customer"):
                    self.assertEqual(
                        route["arrival_times"][destination],
                        segment["estimated_arrival_time"],
                    )
                    customer = location_by_id[destination]
                    elapsed_offset = elapsed
                    if customer.ready_after_minutes is not None:
                        self.assertLessEqual(customer.ready_after_minutes, elapsed_offset)
                        self.assertLessEqual(elapsed_offset, customer.due_by_minutes)

            if route["sequence"][-1].startswith("customer"):
                elapsed += services_by_id[route["sequence"][-1]]
            self.assertAlmostEqual(route["total_duration"], elapsed)

        self.assertEqual(
            set(result["routes"]),
            {route["partner_id"] for route in result["routes"].values()},
        )


if __name__ == "__main__":
    unittest.main()
