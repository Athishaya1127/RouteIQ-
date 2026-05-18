import requests
import json
from backend.config import settings
from fastapi import HTTPException

ORS_BASE_URL = "https://api.openrouteservice.org/v2"

def get_ors_matrix(locations: list[list[float]]):
    """
    Calls ORS Matrix API to get distance and duration.
    locations format: [[lng, lat], [lng, lat], ...]
    Returns (distance_matrix, duration_matrix) in km and minutes.
    """
    if not settings.ORS_API_KEY:
        raise HTTPException(status_code=500, detail="ORS_API_KEY is not configured in .env")

    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': settings.ORS_API_KEY,
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    # ORS expects [longitude, latitude]
    payload = {
        "locations": locations,
        "metrics": ["distance", "duration"],
        "units": "km"
    }
    
    response = requests.post(f"{ORS_BASE_URL}/matrix/driving-car", headers=headers, json=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"ORS API Error: {response.text}")
        
    data = response.json()
    
    # distance is in km (due to units="km"), duration is in seconds
    distances = data.get("distances", [])
    durations_seconds = data.get("durations", [])
    
    durations_minutes = [[val / 60.0 if val is not None else 0 for val in row] for row in durations_seconds]
    
    return distances, durations_minutes

def get_full_route_details(locations: list[list[float]]):
    """
    Calls ORS Directions API to get polyline for the optimized sequence
    and extracts segment-level details.
    """
    if not settings.ORS_API_KEY:
        return [], []
        
    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': settings.ORS_API_KEY,
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    payload = {
        "coordinates": locations,
        "instructions": True
    }
    
    response = requests.post(f"{ORS_BASE_URL}/directions/driving-car/geojson", headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Failed to fetch directions polyline: {response.text}")
        return [], []
        
    data = response.json()
    try:
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
        print(f"Error parsing directions: {e}")
        return [], []
