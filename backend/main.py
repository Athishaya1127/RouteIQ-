from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
from backend.models.schemas import OptimizeRequest, OptimizationResult, RouteSegment
from backend.config import settings
from backend.services.routing_api import get_ors_matrix, get_full_route_details
from backend.services.cost_engine import build_cost_matrix
from backend.services.optimizer import solve_vrp
from backend.database import engine, Base
from backend.services.websocket import manager
from backend.services.simulation import run_simulation
from fastapi import WebSocket, WebSocketDisconnect
import asyncio

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RouteIQ AI Route Optimization API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Start the predictive simulation loop in the background
    asyncio.create_task(run_simulation())

# In-memory storage for the latest route summary
latest_summary = {}

@app.post("/optimize-route")
async def optimize_route(request: OptimizeRequest):
    # 1. Filter locations
    partner = next((loc for loc in request.locations if loc.id == request.selected_partner_id and loc.type == "partner"), None)
    if not partner:
        raise HTTPException(status_code=400, detail="Selected delivery partner not found.")
        
    shop = next((loc for loc in request.locations if loc.id == request.selected_shop_id and loc.type == "shop"), None)
    if not shop:
        raise HTTPException(status_code=400, detail="Selected shop not found.")
        
    customers = [loc for loc in request.locations if loc.type == "customer" and loc.shop_id == request.selected_shop_id]
    if not customers:
        raise HTTPException(status_code=400, detail="No customers found for the selected shop.")
        
    filtered_locations = [partner, shop] + customers

    if len(filtered_locations) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 locations allowed due to OpenRouteService rate limits.")

    # 2. Setup base departure time
    from datetime import datetime, timedelta
    departure_time = datetime.now()
    if request.departure_hour is not None:
        departure_time = departure_time.replace(hour=request.departure_hour, minute=0, second=0, microsecond=0)

    # 3. Snap locations to graph nodes and build time-dependent matrices
    from backend.services.road_graph import snap_location_to_graph, time_dependent_dijkstra
    import math

    snapped_nodes = [snap_location_to_graph(loc.lat, loc.lng) for loc in filtered_locations]
    num_nodes = len(filtered_locations)

    print(f"[RouteIQ] Received optimization request for {num_nodes} nodes Snapped to Road Intersections.")
    
    cost_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    dur_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    dist_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    fuel_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    paths_cache = {}

    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j:
                continue
            
            node_i = snapped_nodes[i]
            node_j = snapped_nodes[j]
            
            cost, dur_mins, geom, segments_info, rejected = time_dependent_dijkstra(node_i, node_j, departure_time)
            
            dist_km = sum(s["length"] for s in segments_info) if segments_info else 0.0
            if dist_km == 0.0:
                # Snap distance fallback (same road node snap)
                lat1, lng1 = filtered_locations[i].lat, filtered_locations[i].lng
                lat2, lng2 = filtered_locations[j].lat, filtered_locations[j].lng
                dist_km = math.hypot(lng1 - lng2, lat1 - lat2) * 111.0 # roughly km
                dur_mins = dist_km / (settings.AVERAGE_SPEED_KMPH / 60.0)
                cost = dist_km
                geom = [[lat1, lng1], [lat2, lng2]]
                rejected = []
                segments_info = [{
                    "edge_id": f"connector_{i}_{j}",
                    "road_name": "Connector Link",
                    "length": dist_km,
                    "avg_speed": settings.AVERAGE_SPEED_KMPH,
                    "predicted_congestion": 0.1,
                    "travel_time": dur_mins,
                    "estimated_arrival_time": departure_time.strftime("%I:%M %p"),
                    "adjusted_edge_cost": cost,
                    "geometry": geom
                }]

            cost_matrix[i][j] = cost
            dur_matrix[i][j] = dur_mins
            dist_matrix[i][j] = dist_km
            fuel_matrix[i][j] = dist_km * 0.12 # approx fuel rate
            paths_cache[(i, j)] = {
                "geometry": geom,
                "segments": segments_info,
                "rejected_edges": rejected
            }

    # 4. Solve VRP
    routes = solve_vrp(
        cost_matrix, 
        dur_matrix, 
        settings.DELAY_THRESHOLD_MINS, 
        settings.DELAY_PENALTY_COST, 
        num_vehicles=1,
        starts=[0],
        ends=[0]
    )
    
    if not routes or not routes[0]:
        print("[RouteIQ ERROR] Optimization failed. Returning empty arrays.")
        raise HTTPException(status_code=500, detail="OR-Tools failed to find a time-dependent VRP solution.")

    raw_route = routes[0]
    print("[RouteIQ] Final optimized route generated.")
    
    # 5. Process results and dynamically chronologize edges
    segments = []
    full_route_geometry = []
    current_time_tracker = departure_time
    total_dist = 0.0
    total_dur = 0.0
    r_cost = 0.0
    r_fuel = 0.0

    all_rejected_edges = {}
    
    ordered_locations = [filtered_locations[idx] for idx in raw_route]
    ors_coords = [[loc.lng, loc.lat] for loc in ordered_locations]
    
    # Query OpenRouteService Directions API for actual street geometries
    leaflet_coords, ors_segments = get_full_route_details(ors_coords)
    use_ors = bool(leaflet_coords and ors_segments and len(ors_segments) == len(raw_route) - 1)
    
    if use_ors:
        full_route_geometry = leaflet_coords

    for i in range(len(raw_route) - 1):
        from_idx = raw_route[i]
        to_idx = raw_route[i+1]
        
        r_cost += cost_matrix[from_idx][to_idx]
        r_fuel += fuel_matrix[from_idx][to_idx]

        path_data = paths_cache.get((from_idx, to_idx), None)
        rejected = path_data.get("rejected_edges", []) if path_data else []
        for r_edge in rejected:
            all_rejected_edges[r_edge["edge_id"]] = r_edge

        if use_ors:
            ors_seg = ors_segments[i]
            
            # Extract dynamic traffic metrics from our predictive model
            if path_data and path_data.get("segments"):
                avg_congestion = sum(s["predicted_congestion"] for s in path_data["segments"]) / len(path_data["segments"])
                dur = sum(s["travel_time"] for s in path_data["segments"])
            else:
                avg_congestion = 0.1
                dur = ors_seg["duration"]

            s_arrival = current_time_tracker.strftime("%I:%M %p")
            
            segments.append({
                "from_id": filtered_locations[from_idx].id,
                "to_id": filtered_locations[to_idx].id,
                "edge_id": f"leg_{from_idx}_{to_idx}",
                "road_name": f"Street Route ({filtered_locations[from_idx].id} → {filtered_locations[to_idx].id})",
                "distance": round(ors_seg["distance"], 2),
                "duration": round(dur, 2),
                "geometry": ors_seg["geometry"],
                "congestion": round(avg_congestion, 2),
                "estimated_arrival_time": s_arrival,
                "adjusted_edge_cost": round(cost_matrix[from_idx][to_idx], 2)
            })
            
            current_time_tracker += timedelta(minutes=dur)
            total_dist += ors_seg["distance"]
            total_dur += dur
        else:
            # Robust Fallback to snapped road-graph/straight-line geometries
            if path_data:
                geom = path_data["geometry"]
                segs = path_data["segments"]
                
                if not full_route_geometry:
                    full_route_geometry.extend(geom)
                else:
                    full_route_geometry.extend(geom[1:])
                    
                for s in segs:
                    s_arrival = current_time_tracker.strftime("%I:%M %p")
                    
                    segments.append({
                        "from_id": filtered_locations[from_idx].id,
                        "to_id": filtered_locations[to_idx].id,
                        "edge_id": s["edge_id"],
                        "road_name": s["road_name"],
                        "distance": s["length"],
                        "duration": s["travel_time"],
                        "geometry": s["geometry"],
                        "congestion": s["predicted_congestion"],
                        "estimated_arrival_time": s_arrival,
                        "adjusted_edge_cost": s["adjusted_edge_cost"]
                    })
                    
                    current_time_tracker += timedelta(minutes=s["travel_time"])
                    total_dist += s["length"]
                    total_dur += s["travel_time"]

    avg_congestion = sum(s["congestion"] for s in segments) / len(segments) if segments else 0.1
    if avg_congestion < 0.4:
        traffic_level = "Low"
    elif avg_congestion < 0.7:
        traffic_level = "Moderate"
    else:
        traffic_level = "Heavy"


    # Filter rejected edges to only keep those NOT traversed anywhere in the final optimal VRP route
    optimal_edge_ids = {s["edge_id"] for s in segments}
    rejected_list = [
        val for edge_id, val in all_rejected_edges.items()
        if edge_id not in optimal_edge_ids
    ]

    # Determine optimization reason
    opt_reason = f"Optimized using Time-Dependent Segment Routing (Departing at {departure_time.strftime('%I:%M %p')})."
    if traffic_level == "Heavy" or traffic_level == "Moderate":
        opt_reason += " AI routed around predicted future street bottlenecks."

    result_payload = {
        "route_version": f"v-{str(uuid.uuid4())[:8]}",
        "timestamp": datetime.now().isoformat(),
        "optimization_reason": opt_reason,
        "route_score": round(r_cost, 2),
        "partner_id": partner.id,
        "shop_id": shop.id,
        "customers": [c.id for c in customers],
        "sequence": [loc.id for loc in ordered_locations],
        "segments": segments,
        "rejected_edges": rejected_list,
        "total_distance": round(total_dist, 2),
        "total_duration": round(total_dur, 2),
        "cost": round(r_cost, 2),
        "fuel": round(r_fuel, 2),
        "traffic_level": traffic_level,
        "full_route_geometry": full_route_geometry
    }

    import backend.services.global_state as global_state
    global_state.active_request = request
    global_state.active_route = result_payload

    # Dynamically sync driver statuses with currently placed partners in request
    active_partners = [loc.id for loc in request.locations if loc.type == "partner"]
    new_driver_status = {}
    for p_id in active_partners:
        if p_id in global_state.driver_status:
            new_driver_status[p_id] = global_state.driver_status[p_id]
        else:
            new_driver_status[p_id] = "idle"
            
    if request.selected_partner_id in new_driver_status:
        new_driver_status[request.selected_partner_id] = "active"
        
    global_state.driver_status = new_driver_status

    return result_payload

@app.get("/route-summary")
async def get_route_summary():
    if not latest_summary:
        return {"message": "No optimization runs yet."}
    return latest_summary

@app.get("/")
async def root():
    return {"message": "RouteIQ API is running."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
