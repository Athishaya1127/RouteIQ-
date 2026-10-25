from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class Location(BaseModel):
    id: str
    type: Literal["shop", "customer", "partner"]
    available: bool = True
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    shop_id: Optional[str] = None
    demand: int = Field(default=1, ge=0)
    service_minutes: int = Field(default=0, ge=0)
    ready_after_minutes: Optional[int] = Field(default=None, ge=0)
    due_by_minutes: Optional[int] = Field(default=None, ge=0)
    capacity: Optional[int] = Field(default=None, ge=0)

class OptimizeRequest(BaseModel):
    locations: List[Location]
    selected_partner_id: str
    selected_shop_id: str
    departure_hour: Optional[int] = Field(default=None, ge=0, le=23)

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
