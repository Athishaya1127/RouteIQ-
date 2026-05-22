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
            
            # Stochastic fluctuations with periodic severe traffic spikes
            # Stochastically trigger a severe traffic event in one random zone 35% of the time!
            # To ensure the user can easily witness dynamic AI rerouting without waiting forever,
            # we prioritize picking a zone that the active route actually traverses!
            active_zones = []
            if global_state.active_route and global_state.active_route.get("segments"):
                ZONES_COORDS = {
                    "T Nagar": (13.0418, 80.2341),
                    "OMR": (12.9229, 80.2234),
                    "Velachery": (12.9815, 80.2180),
                    "Anna Nagar": (13.0850, 80.2101),
                    "Tambaram": (12.9249, 80.1000),
                    "Adyar": (13.0012, 80.2565)
                }
                import math
                for seg in global_state.active_route["segments"]:
                    geom = seg.get("geometry", [])
                    if geom:
                        mid_pt = geom[len(geom) // 2]
                        closest_zone = min(
                            ZONES_COORDS.keys(),
                            key=lambda z: math.hypot(ZONES_COORDS[z][0] - mid_pt[0], ZONES_COORDS[z][1] - mid_pt[1])
                        )
                        if closest_zone not in active_zones:
                            active_zones.append(closest_zone)
            
            spiked_zone = None
            if random.random() < 0.35: # 35% chance to spike a zone
                if active_zones:
                    spiked_zone = random.choice(active_zones)
                    print(f"[Traffic Incident System] Spiking active route zone: {spiked_zone} to trigger dynamic reroute!")
                else:
                    spiked_zone = random.choice(ZONES)

            for zone in ZONES:
                if zone == spiked_zone:
                    congestion = round(random.uniform(0.78, 0.95), 2)
                    density = round(random.uniform(0.80, 0.95), 2)
                    avg_speed = round(random.uniform(5.0, 12.0), 1)
                else:
                    congestion = round(random.uniform(0.1, 0.50), 2)
                    density = round(random.uniform(0.1, 0.50), 2)
                    avg_speed = round(max(15.0, 40.0 * (1.0 - congestion)), 1)
                
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
                
                if zone == spiked_zone:
                    predicted_congestion = round(random.uniform(0.78, 0.92), 2)
                else:
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

            # Dynamic AI Orchestration Engine Run
            from backend.services.orchestrator import evaluate_orchestration
            try:
                orchestration_data = await evaluate_orchestration()
            except Exception as e:
                print(f"[Orchestrator Error] Failed to evaluate orchestration: {e}")
                orchestration_data = {"demand_forecasts": {}, "risk_score": None, "events": []}

            # Broadcast
            payload = {
                "type": "SIMULATION_TICK",
                "traffic": traffic_payloads,
                "ai_events": ai_events,
                "orchestration": orchestration_data
            }
            
            await manager.broadcast(payload)
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Simulation Error: {e}")
            await asyncio.sleep(5)
