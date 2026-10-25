import logging
import math
from functools import lru_cache

import requests
from backend.config import settings
from fastapi import HTTPException

ORS_BASE_URL = "https://api.openrouteservice.org/v2"
OSRM_BASE_URL = "https://router.project-osrm.org"
logger = logging.getLogger(__name__)


def _as_matrix(values: list[list[float | None]], multiplier: float) -> list[list[float]]:
    return [
        [
            float(value) * multiplier if value is not None and math.isfinite(value) else float("inf")
            for value in row
        ]
        for row in values
    ]


def _valid_coordinates(locations: list[list[float]]) -> bool:
    if not isinstance(locations, list):
        return False
    for point in locations:
        if (
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in point)
        ):
            return False
        longitude, latitude = point
        if (
            not math.isfinite(longitude)
            or not math.isfinite(latitude)
            or not -180 <= longitude <= 180
            or not -90 <= latitude <= 90
        ):
            return False
    return True


def _route_coordinates_for_leg(leg: dict) -> list[list[float]]:
    if not isinstance(leg, dict) or not isinstance(leg.get("steps"), list):
        return []

    coordinates = []
    for step in leg["steps"]:
        if not isinstance(step, dict):
            return []
        step_geometry = step.get("geometry", {})
        step_coordinates = step_geometry.get("coordinates", [])
        if not isinstance(step_coordinates, list) or not step_coordinates:
            return []
        for coordinate in step_coordinates:
            if (
                not isinstance(coordinate, list)
                or len(coordinate) != 2
                or any(
                    not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in coordinate
                )
            ):
                return []
            leaflet_coordinate = [coordinate[1], coordinate[0]]
            if not coordinates or coordinates[-1] != leaflet_coordinate:
                coordinates.append(leaflet_coordinate)
    return coordinates

# Robust fallback mechanism for routing and matrix data using OSRM when ORS is unavailable or key is invalid.
def get_osrm_matrix(locations: list[list[float]]):
    """
    Calls free OSRM Table API as a premium fallback when ORS is not available.
    locations format: [[lng, lat], [lng, lat], ...]
    Returns (distance_matrix, duration_matrix) in km and minutes.
    """
    coords_str = ";".join(f"{lng},{lat}" for lng, lat in locations)
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coords_str}?annotations=distance,duration"
    
    headers = {'User-Agent': 'RouteIQ AI Route Optimization App'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and data.get("code") == "Ok":
                distances_m = data.get("distances")
                durations_s = data.get("durations")
                if not isinstance(distances_m, list) or not isinstance(durations_s, list):
                    logger.warning("OSRM matrix response is missing distance or duration data.")
                    return None, None
                size = len(locations)
                if (
                    len(distances_m) != size
                    or len(durations_s) != size
                    or any(
                        not isinstance(row, list) or len(row) != size
                        for row in distances_m + durations_s
                    )
                ):
                    logger.warning("OSRM matrix response has an invalid shape.")
                    return None, None
                
                # convert meters to km, and seconds to minutes
                distances_km = _as_matrix(distances_m, 1.0 / 1000.0)
                durations_mins = _as_matrix(durations_s, 1.0 / 60.0)
                return distances_km, durations_mins
        else:
            logger.warning("OSRM matrix request returned HTTP %s.", response.status_code)
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError) as e:
        logger.warning("OSRM matrix request failed: %s", e)
    return None, None

def get_osrm_route_details(locations: list[list[float]]):
    """
    Calls free OSRM Route API as a premium fallback to get high-fidelity street routing.
    locations format: [[lng, lat], [lng, lat], ...]
    Returns (leaflet_coords, segments_info).
    """
    coords_str = ";".join(f"{lng},{lat}" for lng, lat in locations)
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/{coords_str}"
        "?overview=full&geometries=geojson&steps=true"
    )
    
    headers = {'User-Agent': 'RouteIQ AI Route Optimization App'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                raw_geometry = route.get("geometry", {}).get("coordinates", [])
                raw_legs = route.get("legs", [])
                if (
                    not isinstance(raw_geometry, list)
                    or len(raw_geometry) < 2
                    or len(raw_legs) != len(locations) - 1
                ):
                    logger.warning("OSRM directions response has invalid route geometry or leg count.")
                    return [], []

                segments_info = []
                leaflet_coords = []
                for leg in raw_legs:
                    leg_geometry = _route_coordinates_for_leg(leg)
                    distance = leg.get("distance")
                    duration = leg.get("duration")
                    if (
                        len(leg_geometry) < 2
                        or not isinstance(distance, (float, int))
                        or not isinstance(duration, (float, int))
                        or not math.isfinite(distance)
                        or not math.isfinite(duration)
                        or distance < 0
                        or duration < 0
                    ):
                        logger.warning("OSRM directions response contains invalid leg data.")
                        return [], []

                    if leaflet_coords and leaflet_coords[-1] == leg_geometry[0]:
                        leaflet_coords.extend(leg_geometry[1:])
                    else:
                        leaflet_coords.extend(leg_geometry)
                    segments_info.append({
                        "distance": distance / 1000.0,
                        "duration": duration / 60.0,
                        "geometry": leg_geometry,
                    })
                if len(leaflet_coords) < 2:
                    return [], []
                return leaflet_coords, segments_info
        else:
            logger.warning("OSRM directions request returned HTTP %s.", response.status_code)
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
        logger.warning("OSRM route request failed: %s", e)
    return [], []

@lru_cache(maxsize=64)
def _cached_matrix(locations: tuple[tuple[float, float], ...]):
    coords = [list(location) for location in locations]
    return _get_matrix_uncached(coords)


def _get_matrix_uncached(locations: list[list[float]]):
    """
    Return road distance in km and baseline duration in minutes.

    Matrix responses with missing/unreachable entries retain infinity so the
    optimizer cannot accidentally treat an unavailable leg as zero-cost.
    """
    pair_count = len(locations) ** 2
    if not locations or pair_count > 3500:
        raise HTTPException(status_code=400, detail="The route matrix exceeds the provider request limit.")

    is_dummy_key = not settings.ORS_API_KEY or settings.ORS_API_KEY.startswith("your_")
    if is_dummy_key:
        logger.info("ORS API key is not configured; using the OSRM matrix fallback.")
        dist, dur = get_osrm_matrix(locations)
        if dist and dur:
            return dist, dur
        raise HTTPException(status_code=502, detail="Failed to fetch a road matrix from OSRM.")

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
            if not isinstance(data, dict):
                raise ValueError("ORS matrix response must be an object.")
            distances = data.get("distances", [])
            durations_seconds = data.get("durations", [])
            if len(distances) == len(locations) and len(durations_seconds) == len(locations):
                distances_km = _as_matrix(distances, 1.0)
                durations_minutes = _as_matrix(durations_seconds, 1.0 / 60.0)
                if all(len(row) == len(locations) for row in distances_km + durations_minutes):
                    return distances_km, durations_minutes
            logger.warning("ORS returned a matrix with an invalid shape.")
        else:
            logger.warning("ORS matrix request returned HTTP %s.", response.status_code)
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
        logger.warning("ORS matrix response failed; trying OSRM fallback: %s", e)
        
    dist, dur = get_osrm_matrix(locations)
    if dist and dur:
        return dist, dur
        
    raise HTTPException(status_code=502, detail="Failed to fetch a road matrix from ORS and OSRM.")


def get_ors_matrix(locations: list[list[float]]):
    if not locations or len(locations) > 50 or not _valid_coordinates(locations):
        raise HTTPException(
            status_code=400,
            detail="Matrix requests require 1-50 valid [longitude, latitude] coordinates.",
        )
    result = _cached_matrix(tuple(tuple(float(value) for value in point) for point in locations))
    size = len(locations)
    distances, durations = result
    if (
        len(distances) != size
        or len(durations) != size
        or any(len(row) != size for row in distances + durations)
    ):
        raise HTTPException(status_code=502, detail="The routing provider returned a malformed matrix.")
    if any(
        math.isfinite(value) and value < 0
        for matrix in (distances, durations)
        for row in matrix
        for value in row
    ):
        raise HTTPException(status_code=502, detail="The routing provider returned negative route metrics.")
    return [row[:] for row in result[0]], [row[:] for row in result[1]]

def get_full_route_details(locations: list[list[float]]):
    """
    Calls ORS Directions API to get polyline for the optimized sequence, with robust OSRM fallback.
    """
    if len(locations) < 2 or len(locations) > 50 or not _valid_coordinates(locations):
        raise HTTPException(
            status_code=400,
            detail="Directions requests require 2-50 valid [longitude, latitude] coordinates.",
        )
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
            if not isinstance(data, dict):
                raise ValueError("ORS directions response must be an object.")
            features = data.get("features")
            if not isinstance(features, list) or len(features) != 1:
                raise ValueError("ORS directions response must contain exactly one feature.")
            feature = features[0]
            if not isinstance(feature, dict):
                raise ValueError("ORS directions feature must be an object.")
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            if not isinstance(geometry, dict) or not isinstance(properties, dict):
                raise ValueError("ORS directions feature is missing geometry or properties.")
            coordinates = geometry.get("coordinates", [])
            raw_segments = properties.get("segments", [])
            way_points = properties.get("way_points", [])
            if (
                not isinstance(coordinates, list)
                or len(coordinates) < 2
                or not isinstance(raw_segments, list)
                or not isinstance(way_points, list)
                or len(raw_segments) != len(locations) - 1
                or len(way_points) != len(raw_segments) + 1
                or any(
                    not isinstance(point, list)
                    or len(point) != 2
                    or any(
                        not isinstance(value, (int, float)) or not math.isfinite(value)
                        for value in point
                    )
                    for point in coordinates
                )
                or any(
                    not isinstance(index, int)
                    or index < 0
                    or index >= len(coordinates)
                    for index in way_points
                )
            ):
                raise ValueError("ORS directions response contains inconsistent geometry or leg boundaries.")
            leaflet_coords = [[lat, lng] for lng, lat in coordinates]
            
            segments_info = []
            for i, seg in enumerate(raw_segments):
                start_idx = way_points[i]
                end_idx = way_points[i+1]
                if end_idx < start_idx:
                    raise ValueError("ORS directions waypoints are not ordered.")
                seg_geometry = leaflet_coords[start_idx:end_idx+1]
                distance = seg.get("distance")
                duration = seg.get("duration")
                if (
                    not seg_geometry
                    or not isinstance(distance, (int, float))
                    or not isinstance(duration, (int, float))
                    or not math.isfinite(distance)
                    or not math.isfinite(duration)
                    or distance < 0
                    or duration < 0
                ):
                    raise ValueError("ORS directions response contains invalid leg metrics.")
                distance_km = distance / 1000.0
                duration_mins = duration / 60.0
                
                segments_info.append({
                    "distance": distance_km,
                    "duration": duration_mins,
                    "geometry": seg_geometry
                })
                
            return leaflet_coords, segments_info
        else:
            logger.warning("ORS directions request returned HTTP %s.", response.status_code)
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError, AttributeError) as e:
        logger.warning("ORS directions request failed; trying OSRM fallback: %s", e)
        
    return get_osrm_route_details(locations)
