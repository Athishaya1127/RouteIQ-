from backend.utils.helpers import min_max_normalize
from backend.services.fuel_model import calculate_ideal_duration, calculate_congestion_ratio, estimate_fuel_cost
import backend.services.global_state as global_state
import math

def build_cost_matrix(distance_matrix: list[list[float]], duration_matrix: list[list[float]], coords: list[list[float]], avg_speed: float):
    """
    Builds the normalized multi-objective cost matrix and the auxiliary matrices
    (fuel). Delay penalty is handled natively in OR-Tools via Time Dimension.
    """
    num_nodes = len(distance_matrix)
    
    # 1. Build Fuel Matrix
    fuel_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    congestion_ratios = [[1.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    predicted_congestion_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    
    ZONES_COORDS = {
        "T Nagar": [80.2341, 13.0418],
        "OMR": [80.2234, 12.9229],
        "Velachery": [80.2180, 12.9815],
        "Anna Nagar": [80.2101, 13.0850],
        "Tambaram": [80.1000, 12.9249],
        "Adyar": [80.2565, 13.0012]
    }
    
    def get_zone_congestion(lng, lat):
        if not global_state.latest_simulation_state:
            return 0.1 # default low
        closest_zone = min(ZONES_COORDS.keys(), key=lambda z: math.hypot(ZONES_COORDS[z][0]-lng, ZONES_COORDS[z][1]-lat))
        return global_state.latest_simulation_state.get(closest_zone, {}).get("predicted_congestion", 0.1)

    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                ideal_dur = calculate_ideal_duration(distance_matrix[i][j], avg_speed)
                c_ratio = calculate_congestion_ratio(duration_matrix[i][j], ideal_dur)
                congestion_ratios[i][j] = c_ratio
                fuel_matrix[i][j] = estimate_fuel_cost(distance_matrix[i][j], c_ratio)
                
                # Determine predicted congestion for the destination node
                dest_lng, dest_lat = coords[j]
                predicted_congestion_matrix[i][j] = get_zone_congestion(dest_lng, dest_lat)
                
    # 2. Normalize all components
    norm_duration = min_max_normalize(duration_matrix)
    norm_distance = min_max_normalize(distance_matrix)
    norm_pred_congestion = min_max_normalize(predicted_congestion_matrix)
    
    # 3. Construct Final AI-Aware Route Score Graph
    final_cost_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                # route_score = distance_weight + current_congestion_weight + predicted_congestion_weight + predicted_eta_weight
                # Duration effectively encapsulates current congestion and ETA.
                # We heavily penalize predicted_congestion
                cost = (
                    0.2 * norm_distance[i][j] +
                    0.3 * norm_duration[i][j] +
                    0.5 * norm_pred_congestion[i][j]
                )
                final_cost_matrix[i][j] = cost
                
    return final_cost_matrix, fuel_matrix, congestion_ratios

