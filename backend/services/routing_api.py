import requests
import json
from backend.config import settings
from fastapi import HTTPException

ORS_BASE_URL = "https://api.openrouteservice.org/v2"

def get_osrm_matrix(locations: list[list[float]]):
    """
    Calls free OSRM Table API as a premium fallback when ORS is not available.
    locations format: [[lng, lat], [lng, lat], ...]
    Returns (distance_matrix, duration_matrix) in km and minutes.
    """
    coords_str = ";".join(f"{lng},{lat}" for lng, lat in locations)
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}?annotations=distance,duration"
    
    headers = {'User-Agent': 'RouteIQ AI Route Optimization App'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok":
                distances_m = data.get("distances", [])
                durations_s = data.get("durations", [])
                
                # convert meters to km, and seconds to minutes
                distances_km = [[val / 1000.0 if val is not None else 0.0 for val in row] for row in distances_m]
                durations_mins = [[val / 60.0 if val is not None else 0.0 for val in row] for row in durations_s]
                return distances_km, durations_mins
    except Exception as e:
        print(f"[OSRM Matrix Fallback Error] {e}")
    return None, None

def get_osrm_route_details(locations: list[list[float]]):
    """
    Calls free OSRM Route API as a premium fallback to get high-fidelity street routing.
    locations format: [[lng, lat], [lng, lat], ...]
    Returns (leaflet_coords, segments_info).
    """
    coords_str = ";".join(f"{lng},{lat}" for lng, lat in locations)
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
    
    headers = {'User-Agent': 'RouteIQ AI Route Optimization App'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                coordinates = route["geometry"]["coordinates"]
                leaflet_coords = [[lat, lng] for lng, lat in coordinates]
                
                raw_legs = route.get("legs", [])
                segments_info = []
                num_legs = len(raw_legs)
                
                if num_legs > 0:
                    coords_per_leg = len(leaflet_coords) // num_legs
                    for i, leg in enumerate(raw_legs):
                        start_idx = i * coords_per_leg
                        end_idx = (i + 1) * coords_per_leg if i < num_legs - 1 else len(leaflet_coords)
                        
                        seg_geom = leaflet_coords[start_idx:end_idx]
                        if not seg_geom:
                            seg_geom = leaflet_coords[-2:]
                            
                        segments_info.append({
                            "distance": leg["distance"] / 1000.0,
                            "duration": leg["duration"] / 60.0,
                            "geometry": seg_geom
                        })
                return leaflet_coords, segments_info
    except Exception as e:
        print(f"[OSRM Route Fallback Error] {e}")
    return [], []

def get_ors_matrix(locations: list[list[float]]):
    """
    Calls ORS Matrix API to get distance and duration, with robust OSRM fallback.
    locations format: [[lng, lat], [lng, lat], ...]
    Returns (distance_matrix, duration_matrix) in km and minutes.
    """
    is_dummy_key = not settings.ORS_API_KEY or settings.ORS_API_KEY.startswith("your_")
    if is_dummy_key:
        print("[RouteIQ] ORS key is placeholder. Using OSRM for dynamic street distance matrix...")
        dist, dur = get_osrm_matrix(locations)
        if dist and dur:
            return dist, dur

    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': settings.ORS_API_KEY,
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    payload = {
        "locations": locations,
        "metrics": ["distance", "duration"],
        "units": "km"
    }
    
    try:
        response = requests.post(f"{ORS_BASE_URL}/matrix/driving-car", headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            distances = data.get("distances", [])
            durations_seconds = data.get("durations", [])
            durations_minutes = [[val / 60.0 if val is not None else 0 for val in row] for row in durations_seconds]
            return distances, durations_minutes
    except Exception as e:
        print(f"[ORS Matrix Error] {e}. Falling back to OSRM...")
        
    dist, dur = get_osrm_matrix(locations)
    if dist and dur:
        return dist, dur
        
    raise HTTPException(status_code=500, detail="Failed to fetch route matrix from both ORS and OSRM.")

def get_full_route_details(locations: list[list[float]]):
    """
    Calls ORS Directions API to get polyline for the optimized sequence, with robust OSRM fallback.
    """
    is_dummy_key = not settings.ORS_API_KEY or settings.ORS_API_KEY.startswith("your_")
    if is_dummy_key:
        print("[RouteIQ] ORS key is placeholder. Using OSRM for high-fidelity street routing geometries...")
        return get_osrm_route_details(locations)

    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': settings.ORS_API_KEY,
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    payload = {
        "coordinates": locations,
        "instructions": True
    }
    
    try:
        response = requests.post(f"{ORS_BASE_URL}/directions/driving-car/geojson", headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            feature = data["features"][0]
            coordinates = feature["geometry"]["coordinates"]
            leaflet_coords = [[lat, lng] for lng, lat in coordinates]
            
            properties = feature["properties"]
            raw_segments = properties.get("segments", [])
            way_points = properties.get("way_points", [])
            
            segments_info = []
            for i, seg in enumerate(raw_segments):
                start_idx = way_points[i]
                end_idx = way_points[i+1]
                seg_geometry = leaflet_coords[start_idx:end_idx+1]
                distance_km = seg["distance"] / 1000.0
                duration_mins = seg["duration"] / 60.0
                
                segments_info.append({
                    "distance": distance_km,
                    "duration": duration_mins,
                    "geometry": seg_geometry
                })
                
            return leaflet_coords, segments_info
    except Exception as e:
        print(f"[ORS Route Details Error] {e}. Falling back to OSRM...")
        
    return get_osrm_route_details(locations)
