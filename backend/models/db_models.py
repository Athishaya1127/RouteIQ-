from sqlalchemy import Column, Integer, String, Float, DateTime
import datetime
from backend.database import Base

class TrafficLog(Base):
    __tablename__ = "traffic_logs"

    id = Column(Integer, primary_key=True, index=True)
    zone_name = Column(String, index=True)
    congestion_level = Column(Float)
    vehicle_density = Column(Float)
    avg_speed = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
