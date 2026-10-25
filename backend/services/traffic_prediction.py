from datetime import datetime, timedelta
import math

import backend.services.global_state as global_state
from backend.ml.road_predictor import road_predictor


ZONE_COORDS = {
    "T Nagar": (13.0418, 80.2341),
    "OMR": (12.9229, 80.2234),
    "Velachery": (12.9815, 80.2180),
    "Anna Nagar": (13.0850, 80.2101),
    "Tambaram": (12.9249, 80.1000),
    "Adyar": (13.0012, 80.2565),
}


def _nearest_zone(latitude: float, longitude: float) -> str:
    return min(
        ZONE_COORDS,
        key=lambda name: math.hypot(
            ZONE_COORDS[name][0] - latitude,
            ZONE_COORDS[name][1] - longitude,
        ),
    )


def predict_trip_matrices(
    locations: list,
    baseline_duration_matrix: list[list[float]],
    departure_time: datetime,
) -> tuple[list[list[float]], list[list[float]]]:
    """Predict trip-level congestion and duration from the available zone forecast."""
    size = len(locations)
    predicted_durations = [[0.0] * size for _ in range(size)]
    congestion_matrix = [[0.0] * size for _ in range(size)]

    for origin in range(size):
        for destination in range(size):
            baseline = baseline_duration_matrix[origin][destination]
            if origin == destination:
                continue
            if not math.isfinite(baseline):
                predicted_durations[origin][destination] = float("inf")
                continue

            start = locations[origin]
            end = locations[destination]
            zone = _nearest_zone(
                (start.lat + end.lat) / 2.0,
                (start.lng + end.lng) / 2.0,
            )
            state = global_state.latest_simulation_state.get(zone, {})
            historical = float(state.get("current_congestion", 0.3))
            density = float(state.get("vehicle_density", 0.3))
            speed = float(state.get("avg_speed", 30.0))
            forecast_time = departure_time + timedelta(minutes=baseline)

            congestion = road_predictor.predict_congestion(
                hour=forecast_time.hour,
                day=forecast_time.weekday(),
                hist=historical,
                speed=speed,
                neighbor=max(0.1, min(historical + 0.05, 0.95)),
                upstream=max(0.1, min(historical - 0.05, 0.95)),
                zone=zone,
                density=density,
            )
            congestion = max(0.0, min(float(congestion), 0.95))
            congestion_matrix[origin][destination] = congestion
            predicted_durations[origin][destination] = baseline / max(0.1, 1.0 - congestion)

    return predicted_durations, congestion_matrix
