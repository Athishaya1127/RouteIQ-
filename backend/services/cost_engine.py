import math

from backend.services.fuel_model import calculate_ideal_duration, calculate_congestion_ratio, estimate_fuel_cost


def _normalize_finite(matrix: list[list[float]]) -> list[list[float]]:
    values = [
        value
        for i, row in enumerate(matrix)
        for j, value in enumerate(row)
        if i != j and value >= 0 and math.isfinite(value)
    ]
    if not values:
        return [
            [
                0.0 if i == j else float("inf")
                for j, _ in enumerate(row)
            ]
            for i, row in enumerate(matrix)
        ]

    minimum = min(values)
    spread = max(values) - minimum
    normalized = []
    for i, row in enumerate(matrix):
        normalized_row = []
        for j, value in enumerate(row):
            if i == j:
                normalized_row.append(0.0)
            elif not math.isfinite(value) or value < 0:
                normalized_row.append(float("inf"))
            elif spread == 0:
                normalized_row.append(0.0)
            else:
                normalized_row.append((value - minimum) / spread)
        normalized.append(normalized_row)
    return normalized


def build_cost_matrix(
    distance_matrix: list[list[float]],
    duration_matrix: list[list[float]],
    coords: list[list[float]] | None = None,
    avg_speed: float = 30.0,
    predicted_duration_matrix: list[list[float]] | None = None,
    congestion_matrix: list[list[float]] | None = None,
    weights: tuple[float, float, float, float] = (0.4, 0.3, 0.2, 0.1),
    congestion_threshold: float = 0.6,
    delay_threshold: float | None = None,
    delay_penalty: float | None = None,
):
    """
    Builds normalized cost, fuel, and congestion-ratio matrices. Weights are
    ordered as predicted duration, predicted delay, road distance, congestion.
    """
    num_nodes = len(distance_matrix)
    if len(duration_matrix) != num_nodes or any(
        len(row) != num_nodes for row in distance_matrix + duration_matrix
    ):
        raise ValueError("distance_matrix and duration_matrix must be square and equal-sized")

    predicted_durations = predicted_duration_matrix or duration_matrix
    congestions = congestion_matrix or [[0.0] * num_nodes for _ in range(num_nodes)]
    if len(predicted_durations) != num_nodes or len(congestions) != num_nodes or any(
        len(row) != num_nodes for row in predicted_durations + congestions
    ):
        raise ValueError("predicted duration and congestion matrices must match the input matrix")
    for matrix in (distance_matrix, duration_matrix, predicted_durations):
        if any(
            math.isnan(value) or value < 0 or value == -math.inf
            for row in matrix
            for value in row
        ):
            raise ValueError("route matrices must contain non-negative values or positive infinity")
    if any(
        not math.isfinite(value) or not 0 <= value <= 1
        for row in congestions
        for value in row
    ):
        raise ValueError("congestion values must be finite and in the range [0, 1]")
    weight_total = sum(weights)
    if (
        len(weights) != 4
        or any(not math.isfinite(weight) or weight < 0 for weight in weights)
        or not math.isfinite(weight_total)
        or weight_total <= 0
    ):
        raise ValueError("four non-negative cost weights with a positive sum are required")
    if not math.isfinite(congestion_threshold) or not 0 <= congestion_threshold < 1:
        raise ValueError("congestion_threshold must be in the range [0, 1)")

    fuel_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    congestion_ratios = [[1.0 for _ in range(num_nodes)] for _ in range(num_nodes)]

    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j:
                continue
            if not all(
                math.isfinite(matrix[i][j]) and matrix[i][j] >= 0
                for matrix in (distance_matrix, duration_matrix, predicted_durations)
            ):
                fuel_matrix[i][j] = float("inf")
                continue

            ideal_duration = calculate_ideal_duration(distance_matrix[i][j], avg_speed)
            ratio = calculate_congestion_ratio(predicted_durations[i][j], ideal_duration)
            congestion_ratios[i][j] = ratio
            fuel_matrix[i][j] = estimate_fuel_cost(distance_matrix[i][j], ratio)

    norm_duration = _normalize_finite(predicted_durations)
    norm_distance = _normalize_finite(distance_matrix)
    delays = [
        [
            max(0.0, predicted_durations[i][j] - duration_matrix[i][j])
            if (
                i != j
                and math.isfinite(predicted_durations[i][j])
                and math.isfinite(duration_matrix[i][j])
            )
            else 0.0 if i == j
            else float("inf")
            for j in range(num_nodes)
        ]
        for i in range(num_nodes)
    ]
    norm_delay = _normalize_finite(delays)
    normalized_weights = tuple(weight / weight_total for weight in weights)

    final_cost_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                congestion = congestions[i][j]
                congestion_penalty = max(
                    0.0,
                    min(1.0, (congestion - congestion_threshold) / max(1e-9, 1.0 - congestion_threshold)),
                )
                components = (
                    norm_duration[i][j],
                    norm_delay[i][j],
                    norm_distance[i][j],
                    congestion_penalty,
                )
                final_cost_matrix[i][j] = (
                    float("inf")
                    if any(component == float("inf") for component in components)
                    else sum(weight * component for weight, component in zip(normalized_weights, components))
                )

    return final_cost_matrix, fuel_matrix, congestion_ratios
