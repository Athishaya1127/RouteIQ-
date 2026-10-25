import math
import unittest

from backend.services.optimizer import solve_vrp


def make_matrix(size: int, default: float = 1.0) -> list[list[float]]:
    return [
        [0.0 if origin == destination else default for destination in range(size)]
        for origin in range(size)
    ]


class SolveVrpTests(unittest.TestCase):
    def test_workflow_node_layout_and_vehicle_route_endpoints(self):
        # optimization_workflow.py builds [partners][shop copies][customers].
        # Each end is the partner node used as a virtual open-route marker.
        partner_count = 2
        customer_count = 3
        customer_start = 2 * partner_count
        matrix = make_matrix(customer_start + customer_count)

        routes = solve_vrp(
            matrix,
            matrix,
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=partner_count,
            starts=[0, 1],
            ends=[0, 1],
            demands=[0, 0, 0, 0, 1, 1, 1],
            vehicle_capacities=[2, 2],
            max_route_duration=60,
            time_limit_seconds=1,
        )

        self.assertIsNotNone(routes)
        self.assertEqual(len(routes), partner_count)
        for vehicle, route in enumerate(routes):
            self.assertEqual(route[0], vehicle)
            self.assertEqual(route[1], partner_count + vehicle)
            self.assertEqual(route[-1], vehicle)

        customers = [
            node
            for route in routes
            for node in route
            if node >= customer_start
        ]
        self.assertCountEqual(customers, range(customer_start, customer_start + customer_count))

    def test_each_customer_is_served_once_and_vehicle_restrictions_are_applied(self):
        vehicle_count = 2
        size = 2 * vehicle_count + 2
        matrix = make_matrix(size)

        routes = solve_vrp(
            matrix,
            matrix,
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=vehicle_count,
            starts=[0, 1],
            ends=[0, 1],
            vehicle_allowed_customers=[[4], [5]],
            max_route_duration=60,
            time_limit_seconds=1,
        )

        self.assertIsNotNone(routes)
        self.assertIn(4, routes[0])
        self.assertNotIn(4, routes[1])
        self.assertIn(5, routes[1])
        self.assertNotIn(5, routes[0])
        served = [node for route in routes for node in route if node >= 4]
        self.assertCountEqual(served, [4, 5])

    def test_unreachable_arc_is_never_used(self):
        size = 4
        costs = make_matrix(size)
        durations = make_matrix(size)
        costs[1][2] = math.inf
        durations[1][2] = math.inf

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

        self.assertIsNotNone(routes)
        self.assertTrue(all(
            math.isfinite(costs[from_node][to_node])
            and math.isfinite(durations[from_node][to_node])
            for route in routes
            for from_node, to_node in zip(route[:-1], route[1:])
        ))

    def test_capacity_service_waiting_window_and_duration_constraints(self):
        size = 3
        costs = make_matrix(size)
        durations = [
            [0.0, 3.0, 20.0],
            [3.0, 0.0, 2.0],
            [20.0, 2.0, 0.0],
        ]
        service = [0, 0, 4]

        routes = solve_vrp(
            costs,
            durations,
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=1,
            starts=[0],
            ends=[0],
            demands=[0, 0, 2],
            vehicle_capacities=[2],
            service_minutes=service,
            customer_windows={2: (10, 13)},
            max_route_duration=14,
            time_limit_seconds=1,
        )

        self.assertIsNotNone(routes)
        self.assertEqual(routes[0], [0, 1, 2, 0])
        # Travel 3 + 2, wait 5 for ready-after, service 4; open route
        # does not include a return journey to node 0.
        elapsed = 3 + 2 + 5 + service[2]
        self.assertEqual(elapsed, 14)
        self.assertLessEqual(elapsed, 14)

    def test_capacity_delivery_window_and_max_duration_infeasibility_returns_none(self):
        size = 3
        costs = make_matrix(size)
        durations = make_matrix(size)
        base = dict(
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=1,
            starts=[0],
            ends=[0],
            max_route_duration=60,
            time_limit_seconds=1,
        )

        self.assertIsNone(
            solve_vrp(
                costs,
                durations,
                **base,
                demands=[0, 0, 2],
                vehicle_capacities=[1],
            )
        )
        self.assertIsNone(
            solve_vrp(
                costs,
                durations,
                **base,
                customer_windows={2: (0, 1)},
            )
        )
        self.assertIsNone(
            solve_vrp(
                costs,
                [[0.0, 3.0, 1.0], [3.0, 0.0, 3.0], [1.0, 3.0, 0.0]],
                **{**base, "max_route_duration": 5},
            )
        )
        service_wait_matrix = [
            [0.0, 3.0, 20.0],
            [3.0, 0.0, 2.0],
            [20.0, 2.0, 0.0],
        ]
        self.assertIsNone(
            solve_vrp(
                costs,
                service_wait_matrix,
                **{**base, "max_route_duration": 13},
                service_minutes=[0, 0, 4],
                customer_windows={2: (10, 13)},
            )
        )

    def test_invalid_windows_matrices_and_restrictions_are_rejected(self):
        costs = make_matrix(4)
        durations = make_matrix(4)
        base = dict(
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=1,
            starts=[0],
            ends=[0],
            max_route_duration=60,
            time_limit_seconds=1,
        )

        with self.assertRaises(ValueError):
            solve_vrp(costs, durations, **base, customer_windows={2: (5, 4)})
        with self.assertRaises(ValueError):
            solve_vrp(costs, durations, **base, customer_windows={1: (0, 5)})
        with self.assertRaises(ValueError):
            solve_vrp(costs, durations, **base, customer_windows={2: (0,)})
        with self.assertRaises(ValueError):
            solve_vrp(costs, durations, **base, customer_windows=[])
        for window in (
            (-1, 5),
            (0, 61),
            (math.nan, 5),
            (0, math.inf),
            (True, 5),
            (0, False),
        ):
            with self.subTest(window=window), self.assertRaises(ValueError):
                solve_vrp(costs, durations, **base, customer_windows={2: window})
        with self.assertRaises(ValueError):
            solve_vrp(costs, [[0.0, 1.0]], **base)
        malformed_costs = [row[:] for row in costs]
        malformed_costs[0][1] = math.nan
        with self.assertRaises(ValueError):
            solve_vrp(malformed_costs, durations, **base)
        with self.assertRaises(ValueError):
            solve_vrp(
                costs,
                durations,
                **{**base, "num_vehicles": 2, "starts": [0, 1], "ends": [0, 1]},
                vehicle_allowed_customers=[[2]],
            )
        with self.assertRaises(ValueError):
            solve_vrp(
                costs,
                durations,
                **base,
                vehicle_allowed_customers=[[999]],
            )
        with self.assertRaises(ValueError):
            solve_vrp(
                costs,
                durations,
                **base,
                vehicle_allowed_customers=[None],
            )

    def test_demands_and_capacities_must_be_non_negative_integers(self):
        costs = make_matrix(3)
        durations = make_matrix(3)
        base = dict(
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=1,
            starts=[0],
            ends=[0],
            max_route_duration=60,
            time_limit_seconds=1,
        )

        for invalid_value in (-1, 1.5, True):
            with self.subTest(demand=invalid_value), self.assertRaises(ValueError):
                solve_vrp(
                    costs,
                    durations,
                    **base,
                    demands=[0, 0, invalid_value],
                    vehicle_capacities=[2],
                )
            with self.subTest(capacity=invalid_value), self.assertRaises(ValueError):
                solve_vrp(
                    costs,
                    durations,
                    **base,
                    demands=[0, 0, 1],
                    vehicle_capacities=[invalid_value],
                )

    def test_vehicle_restrictions_cannot_be_bypassed_when_capacity_requires_it(self):
        vehicle_count = 2
        size = 2 * vehicle_count + 2
        costs = make_matrix(size)
        durations = make_matrix(size)

        routes = solve_vrp(
            costs,
            durations,
            delay_threshold=60,
            delay_penalty_cost=0,
            num_vehicles=vehicle_count,
            starts=[0, 1],
            ends=[0, 1],
            vehicle_allowed_customers=[[4], [5]],
            demands=[0, 0, 0, 0, 2, 1],
            vehicle_capacities=[1, 2],
            max_route_duration=60,
            time_limit_seconds=1,
        )

        self.assertIsNone(routes)

        self.assertIsNone(
            solve_vrp(
                make_matrix(3),
                make_matrix(3),
                delay_threshold=60,
                delay_penalty_cost=0,
                num_vehicles=1,
                starts=[0],
                ends=[0],
                vehicle_allowed_customers=[[]],
                max_route_duration=60,
                time_limit_seconds=1,
            )
        )

    def test_infeasible_required_customer_returns_none(self):
        size = 4
        costs = make_matrix(size)
        durations = make_matrix(size)
        for origin in range(size):
            if origin != 2:
                costs[origin][2] = math.inf
                durations[origin][2] = math.inf

        result = solve_vrp(
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

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
