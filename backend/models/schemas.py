from pydantic import BaseModel
from typing import List, Optional

class Location(BaseModel):
    id: str
    type: str # "shop" or "customer" or "partner"
    lat: float
    lng: float
    shop_id: Optional[str] = None

class OptimizeRequest(BaseModel):
    locations: List[Location]
    selected_partner_id: str
    selected_shop_id: str
    departure_hour: Optional[int] = None

class RouteSegment(BaseModel):
    from_id: str
    to_id: str
    distance: float
    duration: float
    geometry: List[List[float]]

class OptimizationResult(BaseModel):
    partner_id: str
    shop_id: str
    customers: List[str]
    sequence: List[str]
    segments: List[RouteSegment]
    full_route_geometry: List[List[float]]
    total_distance: float
    total_duration: float
    fuel: float
    cost: float
    traffic_level: str
    delay_penalty: float
