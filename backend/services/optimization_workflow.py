import asyncio
import logging
import math
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException

from backend.config import settings
from backend.ml.road_predictor import road_predictor
from backend.models.schemas import OptimizeRequest
from backend.services.cost_engine import build_cost_matrix
from backend.services.optimizer import solve_vrp
from backend.services.route_validator import validate_routes
from backend.services.routing_api import get_full_route_details, get_ors_matrix
from backend.services.traffic_prediction import predict_trip_matrices

logger = logging.getLogger(__name__)


async def optimize_deliveries(request: OptimizeRequest) -> dict:
    locations_by_id = {}
    for location in request.locations:
        if location.id in locations_by_id:
            raise HTTPException(status_code=422, detail=f"Duplicate location id: {location.id}")
        locations_by_id[location.id] = location

    partners = [
        location
        for location in request.locations
        if location.type == "partner"
        and location.available
        and (not location.shop_id or location.shop_id == request.selected_shop_id)
    ]
    if not partners:
        raise HTTPException(status_code=400, detail="No delivery partners found for the selected shop.")

    shop = locations_by_id.get(request.selected_shop_id)
    if shop is None or shop.type != "shop":
        raise HTTPException(status_code=400, detail="Selected shop not found.")

    customers = [
        location
        for location in request.locations
        if location.type == "customer" and location.shop_id == request.selected_shop_id
    ]
    if not customers:
        raise HTTPException(status_code=400, detail="No customers found for the selected shop.")

    nodes = partners + [shop] * len(partners) + customers
    if len(nodes) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 matrix locations are supported per request.",
        )

    departure_time = datetime.now()
    if request.departure_hour is not None:
        departure_time = departure_time.replace(
            hour=request.departure_hour, minute=0, second=0, microsecond=0
        )

    customer_start = 2 * len(partners)
    customer_nodes = set(range(customer_start, len(nodes)))
    demands = [0] * len(nodes)
    services = [0] * len(nodes)
    customer_windows = {}
    for index, customer in enumerate(customers, start=customer_start):
        if (customer.ready_after_minutes is None) != (customer.due_by_minutes is None):
            raise HTTPException(
                status_code=422,
                detail=f"Customer {customer.id} must provide both delivery-window offsets.",
            )
        if (
            customer.ready_after_minutes is not None
            and (
                customer.due_by_minutes < customer.ready_after_minutes
                or customer.due_by_minutes > settings.MAX_ROUTE_DURATION_MINS
            )
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Customer {customer.id} has an invalid delivery window.",
            )
        demands[index] = customer.demand
        services[index] = customer.service_minutes
        if customer.ready_after_minutes is not None:
            customer_windows[index] = (
                customer.ready_after_minutes,
                customer.due_by_minutes,
            )

    total_demand = sum(demands)
    capacities = [
        partner.capacity if partner.capacity is not None else total_demand
        for partner in partners
    ]

    coordinates = [[location.lng, location.lat] for location in nodes]
    distance_matrix, baseline_duration_matrix = await asyncio.to_thread(
        get_ors_matrix, coordinates
    )
    predicted_duration_matrix, congestion_matrix = predict_trip_matrices(
        nodes, baseline_duration_matrix, departure_time
    )

    cost_weights = (
        settings.COST_WEIGHT_DURATION,
        settings.COST_WEIGHT_DELAY,
        settings.COST_WEIGHT_DISTANCE,
        settings.COST_WEIGHT_CONGESTION,
    )
    weight_total = sum(cost_weights)
    if not math.isfinite(weight_total) or weight_total <= 0:
        raise HTTPException(
            status_code=500,
            detail="Configured route-cost weights must be finite, non-negative, and have a positive sum.",
        )
    effective_cost_weights = tuple(weight / weight_total for weight in cost_weights)
    try:
        cost_matrix, _, _ = build_cost_matrix(
            distance_matrix,
            baseline_duration_matrix,
            coordinates,
            settings.AVERAGE_SPEED_KMPH,
            predicted_duration_matrix=predicted_duration_matrix,
            congestion_matrix=congestion_matrix,
            weights=effective_cost_weights,
            congestion_threshold=settings.CONGESTION_PENALTY_THRESHOLD,
        )
    except ValueError as error:
        raise HTTPException(status_code=500, detail=f"Unable to construct route costs: {error}") from error

    starts = list(range(len(partners)))
    routes = await asyncio.to_thread(
        solve_vrp,
        cost_matrix,
        predicted_duration_matrix,
        settings.DELAY_THRESHOLD_MINS,
        settings.DELAY_PENALTY_COST,
        len(partners),
        starts,
        starts,
        None,
        demands,
        capacities,
        services,
        customer_windows,
        settings.MAX_ROUTE_DURATION_MINS,
        settings.OPTIMIZER_TIME_LIMIT_SECONDS,
    )
    if routes is None:
        raise HTTPException(
            status_code=422,
            detail="No feasible delivery plan satisfies reachability, capacity, time-window, and route-duration constraints.",
        )

    validation_errors = validate_routes(
        routes,
        customer_nodes,
        cost_matrix,
        predicted_duration_matrix,
        services,
        demands,
        capacities,
        customer_windows,
        settings.MAX_ROUTE_DURATION_MINS,
        starts,
        starts,
    )
    if validation_errors:
        if any("unreachable" in error for error in validation_errors):
            raise HTTPException(
                status_code=422,
                detail="No feasible delivery plan exists because at least one required road leg is unreachable.",
            )
        raise HTTPException(
            status_code=500,
            detail={"message": "The optimizer returned an invalid route plan.", "errors": validation_errors},
        )

    route_payloads = {}
    all_segments = []
    total_distance = 0.0
    total_duration = 0.0
    total_cost = 0.0
    total_fuel = 0.0
    route_warnings = []

    for vehicle_index, raw_route in enumerate(routes):
        if not any(node in customer_nodes for node in raw_route):
            continue

        displayed_route = raw_route[:-1] if raw_route[-1] == raw_route[0] else raw_route
        route_segments = []
        route_geometry = []
        route_arrivals = {}
        route_distance = 0.0
        route_duration = 0.0
        route_cost = 0.0
        route_fuel = 0.0
        elapsed_minutes = 0.0

        direction_geometry, direction_legs = await asyncio.to_thread(
            get_full_route_details,
            [coordinates[node] for node in displayed_route],
        )
        expected_leg_count = len(displayed_route) - 1
        if not direction_geometry or len(direction_legs) != expected_leg_count:
            raise HTTPException(
                status_code=502,
                detail="Road geometry and metrics could not be retrieved for the selected route.",
            )
        route_geometry = direction_geometry

        for leg_index, (origin, destination) in enumerate(
            zip(displayed_route, displayed_route[1:])
        ):
            matrix_duration = predicted_duration_matrix[origin][destination]
            matrix_baseline_duration = baseline_duration_matrix[origin][destination]
            matrix_distance = distance_matrix[origin][destination]
            cost = cost_matrix[origin][destination]
            if not all(math.isfinite(value) for value in (matrix_duration, matrix_distance, cost)):
                raise HTTPException(status_code=500, detail="The selected route contains an unreachable leg.")

            leg_details = direction_legs[leg_index]
            leg_geometry = leg_details.get("geometry")
            if not leg_geometry:
                raise HTTPException(
                    status_code=502,
                    detail="Road geometry could not be retrieved for a selected route leg.",
                )

            try:
                routed_distance = float(leg_details["distance"])
                routed_baseline_duration = float(leg_details["duration"])
            except (KeyError, TypeError, ValueError) as error:
                raise HTTPException(
                    status_code=502,
                    detail="The routing provider returned incomplete route metrics.",
                ) from error
            if (
                not math.isfinite(routed_distance)
                or not math.isfinite(routed_baseline_duration)
                or routed_distance < 0
                or routed_baseline_duration < 0
            ):
                raise HTTPException(status_code=502, detail="The routing provider returned invalid route metrics.")

            congestion = congestion_matrix[origin][destination]
            duration = routed_baseline_duration / max(0.1, 1.0 - congestion)
            if (
                (abs(routed_distance - matrix_distance) > max(0.5, matrix_distance * 0.2))
                or (
                    abs(routed_baseline_duration - matrix_baseline_duration)
                    > max(2.0, matrix_baseline_duration * 0.2)
                )
            ):
                route_warnings.append(
                    f"Directions metrics differed from the optimization matrix for "
                    f"{nodes[origin].id} to {nodes[destination].id}; final ETAs use directions metrics."
                )
                logger.warning(route_warnings[-1])

            elapsed_minutes += services[origin] + duration
            destination_location = nodes[destination]
            waiting_minutes = 0.0
            window = customer_windows.get(destination)
            if window and elapsed_minutes < window[0]:
                waiting_minutes = window[0] - elapsed_minutes
                elapsed_minutes += waiting_minutes
            arrival = departure_time + timedelta(minutes=elapsed_minutes)
            segment = {
                "from_id": nodes[origin].id,
                "to_id": destination_location.id,
                "edge_id": f"leg_{nodes[origin].id}_{destination_location.id}",
                "road_name": f"Road route ({nodes[origin].id} to {destination_location.id})",
                "distance": round(routed_distance, 2),
                "duration": round(duration, 2),
                "geometry": leg_geometry,
                "congestion": round(congestion, 3),
                "estimated_arrival_time": arrival.strftime("%I:%M %p"),
                "waiting_minutes": round(waiting_minutes, 2),
                "adjusted_edge_cost": round(cost, 4),
            }
            route_segments.append(segment)
            all_segments.append(segment)

            if destination in customer_nodes:
                if window and not window[0] <= elapsed_minutes <= window[1]:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Final directions estimates put customer {destination_location.id} outside its delivery window; re-optimize before dispatch.",
                    )
                route_arrivals[destination_location.id] = arrival.strftime("%I:%M %p")
            route_distance += routed_distance
            route_duration += duration + services[origin] + waiting_minutes
            route_cost += cost
            ideal_duration = (
                routed_distance / settings.AVERAGE_SPEED_KMPH * 60.0
                if settings.AVERAGE_SPEED_KMPH > 0
                else duration
            )
            congestion_ratio = max(1.0, duration / ideal_duration) if ideal_duration > 0 else 1.0
            route_fuel += routed_distance * (1.0 + congestion_ratio)

        if displayed_route and displayed_route[-1] in customer_nodes:
            route_duration += services[displayed_route[-1]]
            elapsed_minutes += services[displayed_route[-1]]
        if route_duration > settings.MAX_ROUTE_DURATION_MINS:
            raise HTTPException(
                status_code=422,
                detail=f"Final directions estimates exceed the maximum route duration for {partners[vehicle_index].id}; re-optimize before dispatch.",
            )

        partner_id = partners[vehicle_index].id
        route_payloads[partner_id] = {
            "partner_id": partner_id,
            "vehicle_index": vehicle_index,
            "sequence": [nodes[node].id for node in displayed_route],
            "arrival_times": route_arrivals,
            "segments": route_segments,
            "total_distance": round(route_distance, 2),
            "total_duration": round(route_duration, 2),
            "cost": round(route_cost, 4),
            "fuel": round(route_fuel, 2),
            "full_route_geometry": route_geometry,
        }
        total_distance += route_distance
        total_duration = max(total_duration, route_duration)
        total_cost += route_cost
        total_fuel += route_fuel

    served_customer_ids = [
        customer_id
        for route in route_payloads.values()
        for customer_id in route["arrival_times"]
    ]
    expected_customer_ids = {customer.id for customer in customers}
    if set(served_customer_ids) != expected_customer_ids or len(served_customer_ids) != len(expected_customer_ids):
        raise HTTPException(status_code=500, detail="Route validation failed: orders were omitted or duplicated.")

    mean_congestion = (
        sum(segment["congestion"] for segment in all_segments) / len(all_segments)
        if all_segments
        else 0.0
    )
    traffic_level = "Low" if mean_congestion < 0.4 else "Moderate" if mean_congestion < 0.7 else "Heavy"
    first_route = next(iter(route_payloads.values()), None)
    first_partner_id = next(iter(route_payloads), None)
    reason = (
        f"Joint vehicle assignment and route sequencing optimized from road-network matrices "
        f"departing at {departure_time.strftime('%I:%M %p')}."
    )

    result = {
        "route_version": f"v-{str(uuid.uuid4())[:8]}",
        "timestamp": datetime.now().isoformat(),
        "optimization_reason": reason,
        "traffic_prediction_source": (
            f"Zone-level Random Forest trained on {road_predictor.training_source}; "
            "live inputs currently come from synthetic simulation"
        ),
        "routes": route_payloads,
        "segments": all_segments,
        "rejected_edges": [],
        "route_warnings": route_warnings,
        "total_distance": round(total_distance, 2),
        "total_duration": round(total_duration, 2),
        "cost": round(total_cost, 4),
        "fuel": round(total_fuel, 2),
        "traffic_level": traffic_level,
        "active_routes_count": len(route_payloads),
        "cost_weights": {
            "predicted_duration": effective_cost_weights[0],
            "predicted_delay": effective_cost_weights[1],
            "road_distance": effective_cost_weights[2],
            "congestion_penalty": effective_cost_weights[3],
        },
        "validation": {"is_valid": True, "orders_served": len(served_customer_ids)},
        "partner_id": first_partner_id or request.selected_partner_id,
        "shop_id": request.selected_shop_id,
        "customers": [customer.id for customer in customers],
        "sequence": first_route["sequence"] if first_route else [],
        "segments_legacy": first_route["segments"] if first_route else [],
        "total_distance_legacy": first_route["total_distance"] if first_route else 0.0,
        "total_duration_legacy": first_route["total_duration"] if first_route else 0.0,
        "cost_legacy": first_route["cost"] if first_route else 0.0,
        "fuel_legacy": first_route["fuel"] if first_route else 0.0,
    }

    import backend.services.global_state as global_state
    global_state.active_request = request
    global_state.active_route = result
    driver_status = {
        partner.id: global_state.driver_status.get(partner.id, "idle")
        for partner in request.locations
        if partner.type == "partner"
    }
    for partner_id in route_payloads:
        driver_status[partner_id] = "active"
    global_state.driver_status = driver_status

    return result
