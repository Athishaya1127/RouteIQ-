import math

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


def solve_vrp(
    cost_matrix: list[list[float]],
    duration_matrix: list[list[float]],
    delay_threshold: float,
    delay_penalty_cost: float,
    num_vehicles: int,
    starts: list[int],
    ends: list[int],
    vehicle_allowed_customers: list[list[int]] = None,
    demands: list[int] | None = None,
    vehicle_capacities: list[int] | None = None,
    service_minutes: list[int] | None = None,
    customer_windows: dict[int, tuple[int, int]] | None = None,
    max_route_duration: int = 720,
    time_limit_seconds: int = 5,
):
    """
    Solve a multi-vehicle VRP with duplicated shop nodes, partner-specific customer permissions,
    and a soft upper bound on route time. The function intentionally keeps the production route
    representation and start/end conventions stable while making the solver search more robust.
    """
    if num_vehicles <= 0:
        return []
    matrix_size = len(cost_matrix)
    if (
        matrix_size == 0
        or len(duration_matrix) != matrix_size
        or any(len(row) != matrix_size for row in cost_matrix + duration_matrix)
    ):
        raise ValueError("cost_matrix and duration_matrix must be square and non-empty")
    if len(starts) != num_vehicles or len(ends) != num_vehicles:
        raise ValueError("starts and ends must contain one node per vehicle")
    if any(node < 0 or node >= matrix_size for node in starts + ends):
        raise ValueError("start and end nodes must be valid matrix indices")
    if demands is not None and len(demands) != matrix_size:
        raise ValueError("demands must contain one value per matrix node")
    if service_minutes is not None and len(service_minutes) != matrix_size:
        raise ValueError("service_minutes must contain one value per matrix node")
    if vehicle_capacities is not None and len(vehicle_capacities) != num_vehicles:
        raise ValueError("vehicle_capacities must contain one value per vehicle")
    if (
        max_route_duration <= 0
        or time_limit_seconds <= 0
        or not math.isfinite(delay_threshold)
        or delay_threshold < 0
        or not math.isfinite(delay_penalty_cost)
        or delay_penalty_cost < 0
    ):
        raise ValueError("route duration, solver time, and delay settings must be valid positive values")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (demands or [])
    ) or any(
        not isinstance(capacity, int)
        or isinstance(capacity, bool)
        or capacity < 0
        for capacity in (vehicle_capacities or [])
    ):
        raise ValueError("demands and vehicle capacities must be non-negative integers")
    if any(value < 0 for value in (service_minutes or [])):
        raise ValueError("service times must be non-negative")
    if any(
        math.isnan(value) or value < 0 or value == -math.inf
        for row in duration_matrix
        for value in row
    ):
        raise ValueError("durations must be non-negative or positive infinity")
    scale_factor = 10_000
    shop_start_idx = len(starts)
    customer_start_idx = 2 * len(starts)
    if customer_windows is not None:
        if not isinstance(customer_windows, dict):
            raise ValueError("customer_windows must map customer nodes to time-window pairs")
        for node, window in customer_windows.items():
            if (
                not isinstance(node, int)
                or isinstance(node, bool)
                or node < customer_start_idx
                or node >= matrix_size
                or not isinstance(window, (tuple, list))
                or len(window) != 2
            ):
                raise ValueError(f"Invalid delivery window for node {node}")
            ready_after, due_by = window
            if any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < 0
                or value > max_route_duration
                or not math.isfinite(value)
                for value in (ready_after, due_by)
            ) or ready_after > due_by:
                raise ValueError(f"Invalid delivery window for node {node}")

    if vehicle_allowed_customers is not None:
        if (
            not isinstance(vehicle_allowed_customers, list)
            or len(vehicle_allowed_customers) != num_vehicles
            or any(not isinstance(allowed, list) for allowed in vehicle_allowed_customers)
        ):
            raise ValueError("vehicle_allowed_customers must contain one list per vehicle")
        for vehicle_id, allowed_customers in enumerate(vehicle_allowed_customers):
            if any(
                not isinstance(node, int)
                or isinstance(node, bool)
                or node < customer_start_idx
                or node >= matrix_size
                for node in allowed_customers
            ):
                raise ValueError(
                    f"vehicle_allowed_customers[{vehicle_id}] contains an invalid customer node"
                )

    prohibited = 2_000_000_000
    maximum_arc_cost = prohibited // (matrix_size + 1)
    int_cost_matrix = []
    for row in cost_matrix:
        scaled_row = []
        for cost in row:
            if math.isnan(cost) or cost < 0 or cost == -math.inf:
                raise ValueError("cost matrix entries must be non-negative or positive infinity")
            if not math.isfinite(cost):
                scaled_row.append(prohibited)
                continue
            scaled_cost = int(cost * scale_factor)
            if scaled_cost >= maximum_arc_cost:
                raise ValueError("scaled route cost exceeds the safe OR-Tools integer range")
            scaled_row.append(scaled_cost)
        int_cost_matrix.append(scaled_row)

    for s in starts:
        target_shop_copy = shop_start_idx + s
        if target_shop_copy >= len(int_cost_matrix):
            continue
        for i in range(len(int_cost_matrix[s])):
            if i != target_shop_copy and i != s:
                int_cost_matrix[s][i] = prohibited

    manager = pywrapcp.RoutingIndexManager(len(int_cost_matrix), num_vehicles, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    for vehicle_id in range(num_vehicles):
        shop_node = shop_start_idx + vehicle_id
        if shop_node >= matrix_size:
            raise ValueError("the matrix must contain one duplicated shop node per vehicle")
        shop_index = manager.NodeToIndex(shop_node)
        routing.VehicleVar(shop_index).SetValue(vehicle_id)
        routing.NextVar(routing.Start(vehicle_id)).SetValue(shop_index)

    if vehicle_allowed_customers is not None:
        for customer_node in range(customer_start_idx, matrix_size):
            allowed_vehicles = [
                vehicle_id
                for vehicle_id, allowed_customers in enumerate(vehicle_allowed_customers)
                if customer_node in allowed_customers
            ]
            routing.VehicleVar(manager.NodeToIndex(customer_node)).SetValues(
                allowed_vehicles
            )

    for from_index in range(routing.Size()):
        from_node = manager.IndexToNode(from_index)
        for to_index in range(routing.Size()):
            to_node = manager.IndexToNode(to_index)
            if from_node == to_node:
                continue
            if (
                not math.isfinite(cost_matrix[from_node][to_node])
                or not math.isfinite(duration_matrix[from_node][to_node])
            ):
                routing.solver().Add(routing.NextVar(from_index) != to_index)

    for vehicle_id in range(num_vehicles):
        allowed_custs = vehicle_allowed_customers[vehicle_id] if vehicle_allowed_customers else None

        def make_distance_callback(v_id, allowed_customers):
            def cb(from_index, to_index):
                if routing.IsEnd(to_index):
                    return 0
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)

                if shop_start_idx <= to_node < shop_start_idx + len(starts):
                    if to_node != shop_start_idx + v_id:
                        return prohibited
                if shop_start_idx <= from_node < shop_start_idx + len(starts):
                    if from_node != shop_start_idx + v_id:
                        return prohibited

                if allowed_customers is not None:
                    if to_node >= customer_start_idx and to_node not in allowed_customers:
                        return prohibited
                    if from_node >= customer_start_idx and from_node not in allowed_customers:
                        return prohibited

                return int_cost_matrix[from_node][to_node]

            return cb

        cb_index = routing.RegisterTransitCallback(make_distance_callback(vehicle_id, allowed_custs))
        routing.SetArcCostEvaluatorOfVehicle(cb_index, vehicle_id)

    services = service_minutes or [0] * matrix_size

    def time_callback(from_index, to_index):
        if routing.IsEnd(to_index):
            return int(services[manager.IndexToNode(from_index)] * 100)
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        duration = duration_matrix[from_node][to_node]
        if math.isnan(duration) or duration < 0 or duration == -math.inf:
            return (max_route_duration + 1) * 100
        if not math.isfinite(duration):
            return (max_route_duration + 1) * 100
        return int((duration + services[from_node]) * 100)

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(
        time_callback_index,
        24 * 60 * 100,
        max_route_duration * 100,
        True,
        "Time",
    )

    time_dimension = routing.GetDimensionOrDie("Time")
    int_threshold = int(delay_threshold * 100)
    scaled_penalty = delay_penalty_cost * scale_factor / 100
    if scaled_penalty >= maximum_arc_cost:
        raise ValueError("scaled delay penalty exceeds the safe OR-Tools integer range")
    int_penalty = int(scaled_penalty)

    for node in range(customer_start_idx, matrix_size):
        time_dimension.SetCumulVarSoftUpperBound(
            manager.NodeToIndex(node), int_threshold, int_penalty
        )

    for node, (ready_after, due_by) in (customer_windows or {}).items():
        time_dimension.CumulVar(manager.NodeToIndex(node)).SetRange(
            int(ready_after * 100), int(due_by * 100)
        )

    if demands is not None and vehicle_capacities is not None:
        def demand_callback(from_index):
            return demands[manager.IndexToNode(from_index)]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            vehicle_capacities,
            True,
            "Capacity",
        )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = max(1, time_limit_seconds)

    solution = routing.SolveWithParameters(search_parameters)
    if not solution:
        return None

    routes = []
    for vehicle_id in range(num_vehicles):
        route = []
        index = routing.Start(vehicle_id)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        routes.append(route)

    return routes
