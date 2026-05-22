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
    # Only select partners assigned to this shop, or unassigned partners (backward compatibility)
    partners = [
        loc for loc in request.locations 
        if loc.type == "partner" and (not loc.shop_id or loc.shop_id == request.selected_shop_id)
    ]
    if not partners:
        raise HTTPException(status_code=400, detail="No delivery partners found for the selected shop.")
        
    shop = next((loc for loc in request.locations if loc.id == request.selected_shop_id and loc.type == "shop"), None)
    if not shop:
        raise HTTPException(status_code=400, detail="Selected shop not found.")
        
    customers = [loc for loc in request.locations if loc.type == "customer" and loc.shop_id == request.selected_shop_id]
    if not customers:
        raise HTTPException(status_code=400, detail="No customers found for the selected shop.")
        
    filtered_locations = partners + [shop] * len(partners) + customers

    if len(filtered_locations) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 locations allowed due to OpenRouteService rate limits.")

    # 2. Setup base departure time
    from datetime import datetime, timedelta
    departure_time = datetime.now()
    if request.departure_hour is not None:
        departure_time = departure_time.replace(hour=request.departure_hour, minute=0, second=0, microsecond=0)

    # Calculate distances from customers to all partners and assign each customer to their nearest partner
    import math

    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371.0 # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    customer_to_partner = {}
    print("\n--- RouteIQ Geodesic Distance Matrix calculations ---")
    for cust in customers:
        closest_partner_idx = 0
        min_dist = float('inf')
        for idx, partner in enumerate(partners):
            dist_km = haversine_distance(partner.lat, partner.lng, cust.lat, cust.lng)
            print(f"[Distance Calculation] Customer {cust.id} to Partner {partner.id}: {dist_km:.2f} km")
            if dist_km < min_dist:
                min_dist = dist_km
                closest_partner_idx = idx
        customer_to_partner[cust.id] = closest_partner_idx
        closest_partner = partners[closest_partner_idx]
        print(f"[Assignment Decision] Customer {cust.id} assigned to closest Partner {closest_partner.id} ({min_dist:.2f} km)\n")

    # Map each customer to their allowed node index (customer_indices start at 2 * len(partners))
    vehicle_allowed_customers = [[] for _ in range(len(partners))]
    for cust_idx, cust in enumerate(customers):
        partner_idx = customer_to_partner[cust.id]
        node_idx = 2 * len(partners) + cust_idx
        vehicle_allowed_customers[partner_idx].append(node_idx)

    # 3. Snap locations to graph nodes and build time-dependent matrices
    from backend.services.road_graph import snap_location_to_graph, time_dependent_dijkstra

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
            
            lat1, lng1 = filtered_locations[i].lat, filtered_locations[i].lng
            lat2, lng2 = filtered_locations[j].lat, filtered_locations[j].lng
            
            dist_km = sum(s["length"] for s in segments_info) if segments_info else 0.0
            if dist_km == 0.0:
                # Snap distance fallback (same road node snap)
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
            else:
                # Prepend starting coordinate and append ending coordinate to the road path
                # to connect the actual markers to the snapped road nodes seamlessly
                if geom:
                    geom = [[lat1, lng1]] + geom + [[lat2, lng2]]

            cost_matrix[i][j] = cost
            dur_matrix[i][j] = dur_mins
            dist_matrix[i][j] = dist_km
            fuel_matrix[i][j] = dist_km * 0.12 # approx fuel rate
            paths_cache[(i, j)] = {
                "geometry": geom,
                "segments": segments_info,
                "rejected_edges": rejected
            }

    starts = list(range(len(partners)))
    ends = list(range(len(partners)))

    # 4. Solve VRP
    routes = solve_vrp(
        cost_matrix, 
        dur_matrix, 
        settings.DELAY_THRESHOLD_MINS, 
        settings.DELAY_PENALTY_COST, 
        num_vehicles=len(partners),
        starts=starts,
        ends=ends,
        vehicle_allowed_customers=vehicle_allowed_customers
    )
    
    if not routes:
        print("[RouteIQ ERROR] Optimization failed. Returning empty arrays.")
        raise HTTPException(status_code=500, detail="OR-Tools failed to find a time-dependent VRP solution.")

    print(f"[RouteIQ] Final optimized VRP routes generated for {len(partners)} partners.")
    
    # 5. Process results and dynamically chronologize edges for all dispatched partners
    routes_payload = {}
    total_fleet_dist = 0.0
    total_fleet_dur = 0.0
    total_fleet_cost = 0.0
    total_fleet_fuel = 0.0
    all_segments = []
    all_rejected_edges = {}

    for vehicle_idx in range(len(partners)):
        raw_route = routes[vehicle_idx]
        
        # If the vehicle didn't do anything (just starts, goes to shop copy, and has no customer visits), skip it
        # Customer node indexes are >= 2 * len(partners)
        has_customers = any(idx >= 2 * len(partners) for idx in raw_route)
        if not has_customers:
            continue
            
        # For an open VRP delivery route, the vehicle does not need to return to the start node (Partner)
        if len(raw_route) > 2 and raw_route[-1] == raw_route[0]:
            raw_route = raw_route[:-1]
            
        segments = []
        full_route_geometry = []
        current_time_tracker = departure_time
        total_dist = 0.0
        total_dur = 0.0
        r_cost = 0.0
        r_fuel = 0.0
        
        ordered_locations = [filtered_locations[idx] for idx in raw_route]
        for i in range(len(raw_route) - 1):
            from_idx = raw_route[i]
            to_idx = raw_route[i+1]
            
            r_cost += cost_matrix[from_idx][to_idx]
            r_fuel += fuel_matrix[from_idx][to_idx]
            
            path_data = paths_cache.get((from_idx, to_idx), None)
            rejected = path_data.get("rejected_edges", []) if path_data else []
            for r_edge in rejected:
                all_rejected_edges[r_edge["edge_id"]] = r_edge
            
            # Query high-fidelity geometry for this specific leg coordinate pair
            c1 = [filtered_locations[from_idx].lng, filtered_locations[from_idx].lat]
            c2 = [filtered_locations[to_idx].lng, filtered_locations[to_idx].lat]
            
            # Fetch geometry details from OSRM
            leg_coords, leg_segs = get_full_route_details([c1, c2])
            
            # Determine traffic zone scaling based on leg geometry center point
            avg_congestion = 0.15
            ZONES_COORDS = {
                "T Nagar": (13.0418, 80.2341),
                "OMR": (12.9229, 80.2234),
                "Velachery": (12.9815, 80.2180),
                "Anna Nagar": (13.0850, 80.2101),
                "Tambaram": (12.9249, 80.1000),
                "Adyar": (13.0012, 80.2565)
            }
            if leg_coords and len(leg_coords) > 0:
                mid_pt = leg_coords[len(leg_coords) // 2]
                closest_zone = min(
                    ZONES_COORDS.keys(),
                    key=lambda z: math.hypot(ZONES_COORDS[z][0] - mid_pt[0], ZONES_COORDS[z][1] - mid_pt[1])
                )
                import backend.services.global_state as global_state
                macro_state = global_state.latest_simulation_state.get(closest_zone, {})
                avg_congestion = macro_state.get("predicted_congestion", 0.15)
                

# Apply dynamic congestion multiplier to leg duration (e.g., 20% congestion → leg takes 20% longer) 
            if leg_coords and leg_segs:
                leg_distance = sum(s["distance"] for s in leg_segs)
                leg_duration = sum(s["duration"] for s in leg_segs)
                # Dynamic travel time scales with predicted congestion
                leg_duration = leg_duration / max(0.1, 1.0 - avg_congestion)
                leg_geometry = leg_coords
            else:
                # Robust Fallback to snapped road-graph/straight-line geometries
                if path_data and path_data["geometry"]:
                    leg_geometry = path_data["geometry"]
                    leg_distance = sum(s["length"] for s in path_data["segments"])
                    leg_duration = sum(s["travel_time"] for s in path_data["segments"])
                else:
                    lat1, lng1 = filtered_locations[from_idx].lat, filtered_locations[from_idx].lng
                    lat2, lng2 = filtered_locations[to_idx].lat, filtered_locations[to_idx].lng
                    leg_geometry = [[lat1, lng1], [lat2, lng2]]
                    leg_distance = math.hypot(lng1 - lng2, lat1 - lat2) * 111.0
                    leg_duration = leg_distance / (settings.AVERAGE_SPEED_KMPH / 60.0)
                    
            s_arrival = current_time_tracker.strftime("%I:%M %p")
            # RouteIQ optimization engine initialized
            segments.append({
                "from_id": filtered_locations[from_idx].id,
                "to_id": filtered_locations[to_idx].id,
                "edge_id": f"leg_{filtered_locations[from_idx].id}_{filtered_locations[to_idx].id}",
                "road_name": f"Street Route ({filtered_locations[from_idx].id} → {filtered_locations[to_idx].id})",
                "distance": round(leg_distance, 2),
                "duration": round(leg_duration, 2),
                "geometry": leg_geometry,
                "congestion": round(avg_congestion, 2),
                "estimated_arrival_time": s_arrival,
                "adjusted_edge_cost": round(cost_matrix[from_idx][to_idx], 2)
            })
            
            if not full_route_geometry:
                full_route_geometry.extend(leg_geometry)
            else:
                full_route_geometry.extend(leg_geometry[1:])
                
            current_time_tracker += timedelta(minutes=leg_duration)
            total_dist += leg_distance
            total_dur += leg_duration

        p_id = partners[vehicle_idx].id
        routes_payload[p_id] = {
            "partner_id": p_id,
            "vehicle_index": vehicle_idx,
            "sequence": [loc.id for loc in ordered_locations],
            "segments": segments,
            "total_distance": round(total_dist, 2),
            "total_duration": round(total_dur, 2),
            "cost": round(r_cost, 2),
            "fuel": round(r_fuel, 2),
            "full_route_geometry": full_route_geometry
        }
        
        all_segments.extend(segments)
        total_fleet_dist += total_dist
        total_fleet_dur = max(total_fleet_dur, total_dur)
        total_fleet_cost += r_cost
        total_fleet_fuel += r_fuel

    avg_congestion = sum(s["congestion"] for s in all_segments) / len(all_segments) if all_segments else 0.1
    if avg_congestion < 0.4:
        traffic_level = "Low"
    elif avg_congestion < 0.7:
        traffic_level = "Moderate"
    else:
        traffic_level = "Heavy"

    # Filter rejected edges to only keep those NOT traversed anywhere in the final optimal VRP routes
    optimal_edge_ids = {s["edge_id"] for s in all_segments}
    rejected_list = [
        val for edge_id, val in all_rejected_edges.items()
        if edge_id not in optimal_edge_ids
    ]

    # Determine optimization reason
    opt_reason = f"Optimized using Time-Dependent Segment Routing (Departing at {departure_time.strftime('%I:%M %p')})."
    if traffic_level == "Heavy" or traffic_level == "Moderate":
        opt_reason += " AI routed around predicted future street bottlenecks."

    first_p_id = next(iter(routes_payload.keys())) if routes_payload else None
    first_route = routes_payload[first_p_id] if first_p_id else None

    result_payload = {
        "route_version": f"v-{str(uuid.uuid4())[:8]}",
        "timestamp": datetime.now().isoformat(),
        "optimization_reason": opt_reason,
        "routes": routes_payload,
        "segments": all_segments,  # for orchestrator segment checks
        "rejected_edges": rejected_list,
        "total_distance": round(total_fleet_dist, 2),
        "total_duration": round(total_fleet_dur, 2),
        "cost": round(total_fleet_cost, 2),
        "fuel": round(total_fleet_fuel, 2),
        "traffic_level": traffic_level,
        "active_routes_count": len(routes_payload),
        
        # Backwards-compatibility fields for Sidebar.jsx rendering:
        "partner_id": first_p_id or request.selected_partner_id,
        "shop_id": request.selected_shop_id,
        "customers": [c.id for c in customers],
        "sequence": first_route["sequence"] if first_route else [],
        "segments_legacy": first_route["segments"] if first_route else [],
        "total_distance_legacy": first_route["total_distance"] if first_route else 0.0,
        "total_duration_legacy": first_route["total_duration"] if first_route else 0.0,
        "cost_legacy": first_route["cost"] if first_route else 0.0,
        "fuel_legacy": first_route["fuel"] if first_route else 0.0
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
            
    # Mark dispatched partners as active
    for p_id in routes_payload.keys():
        new_driver_status[p_id] = "active"
        
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
