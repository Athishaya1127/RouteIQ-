def calculate_ideal_duration(distance_km: float, average_speed_kmph: float) -> float:
    """Calculate ideal duration in minutes"""
    if average_speed_kmph <= 0:
        return 0
    return (distance_km / average_speed_kmph) * 60

def calculate_congestion_ratio(actual_duration_mins: float, ideal_duration_mins: float) -> float:
    if ideal_duration_mins <= 0:
        return 1.0
    return max(1.0, actual_duration_mins / ideal_duration_mins)

def estimate_fuel_cost(distance_km: float, congestion_ratio: float) -> float:
    """
    Fuel estimate logic:
    fuel = distance * (1 + congestion_ratio)
    """
    return distance_km * (1 + congestion_ratio)
