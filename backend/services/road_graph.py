import math
from datetime import datetime, timedelta
import heapq
import backend.services.global_state as global_state
from backend.ml.road_predictor import road_predictor

# Real coordinates for Chennai main junctions (longitude, latitude)
CHENNAI_NODES = {
    "tnagar": {"name": "T Nagar Junction", "coords": [80.2341, 13.0418]},
    "adyar": {"name": "Adyar Circle", "coords": [80.2565, 13.0012]},
    "omr_toll": {"name": "OMR Toll Plaza", "coords": [80.2234, 12.9229]},
    "velachery": {"name": "Velachery Bypass", "coords": [80.2180, 12.9815]},
    "annanagar": {"name": "Anna Nagar Roundtana", "coords": [80.2101, 13.0850]},
    "tambaram": {"name": "Tambaram Bus Terminus", "coords": [80.1000, 12.9249]},
    "guindy": {"name": "Guindy Interchange", "coords": [80.2160, 13.0067]},
    "madhya_kailash": {"name": "Madhya Kailash Junction", "coords": [80.2435, 13.0076]},
    "sholinganallur": {"name": "Sholinganallur Junction", "coords": [80.2245, 12.9012]},
    "koyambedu": {"name": "Koyambedu Roundabout", "coords": [80.2010, 13.0694]}
}

# Pre-defined roads connecting these junctions with geometry interpolation
ROAD_EDGES = [
    # OMR Road
    {"edge_id": "omr_1", "start": "madhya_kailash", "end": "omr_toll", "road_name": "OMR Main Road", "length": 4.5, "avg_speed": 55.0, "zone": "OMR"},
    {"edge_id": "omr_2", "start": "omr_toll", "end": "sholinganallur", "road_name": "OMR Main Road", "length": 6.2, "avg_speed": 60.0, "zone": "OMR"},
    
    # Mount Road / Anna Salai
    {"edge_id": "mount_1", "start": "tnagar", "end": "guindy", "road_name": "Anna Salai (Mount Road)", "length": 5.1, "avg_speed": 50.0, "zone": "T Nagar"},
    {"edge_id": "mount_2", "start": "guindy", "end": "tambaram", "road_name": "GST Road (Mount Ext)", "length": 11.5, "avg_speed": 70.0, "zone": "Tambaram"},
    
    # Velachery / Ring Roads
    {"edge_id": "ring_1", "start": "guindy", "end": "velachery", "road_name": "Velachery Bypass Road", "length": 3.2, "avg_speed": 45.0, "zone": "Velachery"},
    {"edge_id": "ring_2", "start": "velachery", "end": "madhya_kailash", "road_name": "Velachery Main Link", "length": 2.8, "avg_speed": 40.0, "zone": "Velachery"},
    
    # Adyar Link
    {"edge_id": "adyar_link", "start": "madhya_kailash", "end": "adyar", "road_name": "Adyar Link Road", "length": 2.0, "avg_speed": 40.0, "zone": "Adyar"},
    {"edge_id": "adyar_ring", "start": "tnagar", "end": "adyar", "road_name": "Sardar Patel Road", "length": 5.8, "avg_speed": 45.0, "zone": "Adyar"},
    
    # North / Anna Nagar links
    {"edge_id": "north_1", "start": "annanagar", "end": "tnagar", "road_name": "Anna Nagar Link Road", "length": 6.5, "avg_speed": 45.0, "zone": "Anna Nagar"},
    {"edge_id": "north_2", "start": "koyambedu", "end": "annanagar", "road_name": "Poonamallee High Road Link", "length": 2.5, "avg_speed": 50.0, "zone": "Anna Nagar"},
    {"edge_id": "ring_3", "start": "koyambedu", "end": "guindy", "road_name": "Inner Ring Road", "length": 8.0, "avg_speed": 55.0, "zone": "Anna Nagar"},
    
    # Sholinganallur links
    {"edge_id": "ecr_link", "start": "sholinganallur", "end": "adyar", "road_name": "ECR Bypass Road", "length": 9.8, "avg_speed": 65.0, "zone": "OMR"},
    {"edge_id": "tambaram_link", "start": "sholinganallur", "end": "tambaram", "road_name": "Tambaram-Velachery Main Road", "length": 12.0, "avg_speed": 55.0, "zone": "Tambaram"}
]

# Dual directional edges generator
ALL_EDGES = []
for edge in ROAD_EDGES:
    # Forward direction
    ALL_EDGES.append(edge)
    # Reverse direction
    rev_edge = edge.copy()
    rev_edge["edge_id"] = edge["edge_id"] + "_rev"
    rev_edge["start"] = edge["end"]
    rev_edge["end"] = edge["start"]
    ALL_EDGES.append(rev_edge)

def get_node_coords(node_id: str) -> list[float]:
    return CHENNAI_NODES.get(node_id, {"coords": [80.2707, 13.0827]})["coords"]

REAL_ROAD_GEOMETRIES = {}

def get_interpolated_geometry(start_node: str, end_node: str) -> list[list[float]]:
    c1 = get_node_coords(start_node)
    c2 = get_node_coords(end_node)
    mid = [(c1[0] + c2[0])/2, (c1[1] + c2[1])/2]
    mid[0] += 0.002
    mid[1] += 0.002
    return [[c1[1], c1[0]], [mid[1], mid[0]], [c2[1], c2[0]]]


def snap_location_to_graph(lat: float, lng: float) -> str:
    """
    GIS Snap logic: Finds the closest intersection node in Chennai graph.
    """
    closest_node = min(
        CHENNAI_NODES.keys(),
        key=lambda n: math.hypot(
            CHENNAI_NODES[n]["coords"][0] - lng,
            CHENNAI_NODES[n]["coords"][1] - lat
        )
    )
    return closest_node

def predict_edge_traffic(edge: dict, arrival_time: datetime) -> float:
    """
    Calls the RoadPredictor using macro congestion zone states as a scaling baseline.
    """
    # Fetch macro simulation baseline
    macro_state = global_state.latest_simulation_state.get(edge["zone"], {}) if global_state.latest_simulation_state else {}
    hist_congestion = macro_state.get("predicted_congestion", 0.3)
    
    # Model inputs
    hour = arrival_time.hour
    day = arrival_time.weekday()
    speed = edge["avg_speed"]
    neighbor = max(0.1, min(hist_congestion + 0.05, 0.95))
    upstream = max(0.1, min(hist_congestion - 0.05, 0.95))
    
    return road_predictor.predict_congestion(
        hour=hour,
        day=day,
        hist=hist_congestion,
        speed=speed,
        neighbor=neighbor,
        upstream=upstream
    )

def compute_edge_metrics(edge: dict, departure_time: datetime):
    """
    Calculates dynamic travel time and dynamic upgraded routing cost.
    """
    predicted_congestion = predict_edge_traffic(edge, departure_time)
    
    # Free-flow time in minutes
    free_flow_time = (edge["length"] / edge["avg_speed"]) * 60.0
    
    # Travel time scales with predicted future congestion
    travel_time = free_flow_time / max(0.1, 1.0 - predicted_congestion)
    future_eta_delay = travel_time - free_flow_time
    
    # Upgraded Cost Function:
    # cost = distance + predicted_future_congestion + future_eta_delay + dynamic_traffic_penalty
    dynamic_traffic_penalty = 15.0 if predicted_congestion > 0.75 else 0.0
    
    cost = (
        edge["length"] +
        (predicted_congestion * 6.0) +
        future_eta_delay +
        dynamic_traffic_penalty
    )
    
    return travel_time, predicted_congestion, cost

def time_dependent_dijkstra(start_node: str, end_node: str, departure_time: datetime):
    """
    Time-Dependent Shortest Path (TDSP) Dijkstra algorithm.
    Finds the optimal road path between start and end node considering dynamic future traffic.
    """
    if start_node == end_node:
        return 0.0, 0.0, [], [], []

    # Priority queue: (cost, travel_time_mins, node, path_edges)
    queue = [(0.0, 0.0, start_node, [])]
    visited = {}
    evaluated_congested_edges = {}

    while queue:
        cost, elapsed_time, current_node, path = heapq.heappop(queue)
        
        if current_node == end_node:
            # Reconstruct complete geometry and traversal details
            geometry = []
            segment_details = []
            current_eta = departure_time
            
            for edge in path:
                geom = get_interpolated_geometry(edge["start"], edge["end"])
                # Avoid repeating duplicate transition nodes
                if not geometry:
                    geometry.extend(geom)
                else:
                    geometry.extend(geom[1:])
                
                e_travel, e_congestion, e_cost = compute_edge_metrics(edge, current_eta)
                
                segment_details.append({
                    "edge_id": edge["edge_id"],
                    "road_name": edge["road_name"],
                    "length": edge["length"],
                    "avg_speed": edge["avg_speed"],
                    "predicted_congestion": e_congestion,
                    "travel_time": e_travel,
                    "estimated_arrival_time": current_eta.strftime("%I:%M %p"),
                    "adjusted_edge_cost": round(e_cost, 2),
                    "geometry": geom
                })
                
                current_eta += timedelta(minutes=e_travel)
            
            # Filter out any edges that are part of the final selected optimal path
            optimal_edge_ids = {edge["edge_id"] for edge in path}
            rejected_edges = [
                val for edge_id, val in evaluated_congested_edges.items()
                if edge_id not in optimal_edge_ids
            ]
            
            return cost, elapsed_time, geometry, segment_details, rejected_edges

        if current_node in visited and visited[current_node] <= cost:
            continue
        visited[current_node] = cost

        # Find outgoing edges
        for edge in ALL_EDGES:
            if edge["start"] == current_node:
                next_node = edge["end"]
                
                # Estimate future arrival time at this edge
                edge_departure = departure_time + timedelta(minutes=elapsed_time)
                e_travel, e_congestion, e_cost = compute_edge_metrics(edge, edge_departure)
                
                # Smart Rejection threshold check
                free_flow_time = (edge["length"] / edge["avg_speed"]) * 60.0
                eta_delay = e_travel - free_flow_time
                
                if e_congestion > 0.40 or eta_delay > 4.0 or e_congestion > 0.75:
                    geom = get_interpolated_geometry(edge["start"], edge["end"])
                    
                    if e_congestion > 0.75:
                        reason = f"Severe traffic bottleneck ({int(e_congestion*100)}%) with +15.0 score penalty applied."
                    elif eta_delay > 4.0:
                        reason = f"Severe travel delay predicted (+{round(eta_delay, 1)} mins over free-flow)."
                    else:
                        reason = f"Moderate predicted congestion ({int(e_congestion*100)}%)."
                        
                    evaluated_congested_edges[edge["edge_id"]] = {
                        "edge_id": edge["edge_id"],
                        "road_name": edge["road_name"],
                        "geometry": geom,
                        "predicted_congestion": round(e_congestion, 2),
                        "travel_time": round(e_travel, 2),
                        "estimated_arrival_time": edge_departure.strftime("%I:%M %p"),
                        "rejection_reason": reason
                    }
                
                new_cost = cost + e_cost
                new_elapsed = elapsed_time + e_travel
                
                heapq.heappush(queue, (new_cost, new_elapsed, next_node, path + [edge]))

    # Fallback to direct VRP sequence if graph fails
    return 999.0, 999.0, [], [], []
