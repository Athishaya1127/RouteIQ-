import asyncio
import random
from datetime import datetime
from backend.services.websocket import manager
from backend.database import SessionLocal
from backend.models.db_models import TrafficLog
from backend.ml.live_forecaster import live_forecaster
import backend.services.global_state as global_state

ZONES = ["T Nagar", "OMR", "Velachery", "Anna Nagar", "Tambaram", "Adyar"]

# Maintain historical congestion state
historical_state = {z: [] for z in ZONES}

async def run_simulation():
    """
    Synthetic stochastic simulation environment.
    """
    while True:
        try:
            db = SessionLocal()
            traffic_payloads = []
            ai_events = []
            
            for zone in ZONES:
                # Stochastic fluctuations
                congestion = round(random.uniform(0.1, 0.95), 2)
                density = round(random.uniform(0.1, 0.95), 2)
                avg_speed = round(max(5.0, 40.0 * (1.0 - congestion)), 1)
                
                # Update rolling history (last 5 ticks)
                historical_state[zone].append(congestion)
                if len(historical_state[zone]) > 5:
                    historical_state[zone].pop(0)
                hist_avg = sum(historical_state[zone]) / len(historical_state[zone])
                
                # Database Logging
                log = TrafficLog(
                    zone_name=zone,
                    congestion_level=congestion,
                    vehicle_density=density,
                    avg_speed=avg_speed
                )
                db.add(log)
                
                # AI Prediction
                now = datetime.utcnow()
                prediction = live_forecaster.predict(
                    zone=zone,
                    hour=now.hour,
                    day_of_week=now.weekday(),
                    hist_congestion=hist_avg,
                    density=density,
                    speed=avg_speed
                )
                
                predicted_congestion = prediction["predicted_congestion"]
                
                # Proactive Reroute Logic
                reroute_triggered = False
                if predicted_congestion > 0.75:
                    reroute_triggered = True
                    ai_events.append(f"Predicted congestion spike detected in {zone}. Rerouting triggered.")
                    
                traffic_payloads.append({
                    "zone": zone,
                    "current_congestion": congestion,
                    "predicted_congestion": predicted_congestion,
                    "reroute_triggered": reroute_triggered,
                    "recommended_route_score": 0.0 # Placeholder, frontend will re-optimize
                })
                
                # Update global state for routing engine
                global_state.latest_simulation_state[zone] = {
                    "current_congestion": congestion,
                    "predicted_congestion": predicted_congestion
                }

            db.commit()
            db.close()

            # Broadcast
            payload = {
                "type": "SIMULATION_TICK",
                "traffic": traffic_payloads,
                "ai_events": ai_events
            }
            
            await manager.broadcast(payload)
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Simulation Error: {e}")
            await asyncio.sleep(5)
