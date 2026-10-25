import math


def validate_routes(
    routes: list[list[int]],
    customer_nodes: set[int],
    cost_matrix: list[list[float]],
    duration_matrix: list[list[float]],
    service_minutes: list[int],
    demands: list[int],
    vehicle_capacities: list[int],
    customer_windows: dict[int, tuple[int, int]],
    max_route_duration: int,
    starts: list[int],
    ends: list[int],
) -> list[str]:
    """Independently check solver output for coverage, reachability, time and capacity."""
    errors = []
    visited_customers = []

    if len(routes) != len(vehicle_capacities):
        errors.append("Route count does not match the available vehicle count.")

    for vehicle_id, route in enumerate(routes):
        if vehicle_id >= len(starts) or vehicle_id >= len(ends):
            errors.append(f"Vehicle {vehicle_id + 1} has no configured start or end.")
            continue
        if not route or route[0] != starts[vehicle_id] or route[-1] != ends[vehicle_id]:
            errors.append(f"Vehicle {vehicle_id + 1} has an incorrect route start or end.")

        elapsed = 0.0
        load = 0
        displayed_route = route[:-1] if len(route) > 1 and route[-1] == route[0] else route
        expected_shop = len(starts) + vehicle_id
        if len(displayed_route) < 2 or displayed_route[1] != expected_shop:
            errors.append(f"Vehicle {vehicle_id + 1} does not visit its assigned shop after departure.")
        if displayed_route.count(expected_shop) != 1:
            errors.append(f"Vehicle {vehicle_id + 1} must visit its assigned shop exactly once.")
        if any(
            node not in customer_nodes
            and node != starts[vehicle_id]
            and node != expected_shop
            for node in displayed_route
        ):
            errors.append(f"Vehicle {vehicle_id + 1} visits an unexpected route node.")

        for from_node, to_node in zip(displayed_route, displayed_route[1:]):
            if (
                not math.isfinite(cost_matrix[from_node][to_node])
                or not math.isfinite(duration_matrix[from_node][to_node])
            ):
                errors.append(f"Vehicle {vehicle_id + 1} uses an unreachable route leg.")
                continue

            elapsed += service_minutes[from_node] + duration_matrix[from_node][to_node]
            if to_node in customer_nodes:
                visited_customers.append(to_node)
                load += demands[to_node]
                window = customer_windows.get(to_node)
                if window:
                    elapsed = max(elapsed, window[0])
                    if elapsed > window[1]:
                        errors.append(f"Customer node {to_node} is outside its delivery window.")

        if displayed_route and displayed_route[-1] in customer_nodes:
            elapsed += service_minutes[displayed_route[-1]]
        if vehicle_id < len(vehicle_capacities) and load > vehicle_capacities[vehicle_id]:
            errors.append(f"Vehicle {vehicle_id + 1} exceeds its capacity.")
        if elapsed > max_route_duration:
            errors.append(f"Vehicle {vehicle_id + 1} exceeds the maximum route duration.")

    if len(visited_customers) != len(set(visited_customers)):
        errors.append("A customer is assigned to more than one route.")
    if set(visited_customers) != customer_nodes:
        errors.append("The routes do not serve every customer exactly once.")

    return errors
