import asyncio
import random
from datetime import datetime
from backend.services.websocket import manager
from backend.services.routing_api import get_ors_matrix
from backend.config import settings
import backend.services.global_state as global_state

async def run_realtime_polling():
    """
    Polls ORS for live traffic updates and triggers reroutes if delays exceed thresholds.
    """
    print("[Realtime Tracker] Started live traffic polling loop...")
    while True:
        try:
            # Poll every 10 seconds for demonstration purposes (simulating 2-5 min polling)
            await asyncio.sleep(10)
            
            if not getattr(global_state, 'active_route_session', None):
                continue
                
            session = global_state.active_route_session
            locations = session["locations"]
            
            # Fetch matrix asynchronously so we don't block the loop
            coords = [[loc.lng, loc.lat] for loc in locations]
            distances, durations = await asyncio.to_thread(get_ors_matrix, coords)
            
            # Simulate real-world events since standard ORS matrix is relatively static
            spike_multiplier = 1.0
            event_msg = None
            should_reroute = False
            
            rand = random.random()
            if rand > 0.8:
                spike_multiplier = random.uniform(1.3, 2.0)
                if spike_multiplier > 1.6:
                    event_msg = "Severe accident detected on route! Major slowdowns."
                    should_reroute = True
                else:
                    event_msg = "Traffic spike detected!"
            elif rand > 0.6:
                spike_multiplier = random.uniform(1.1, 1.3)
                event_msg = "Route slowdown detected due to congestion."
            
            # Apply traffic conditions
            for i in range(len(durations)):
                for j in range(len(durations[i])):
                    durations[i][j] *= spike_multiplier
            
            # Evaluate new duration of current active route
            current_route_sequence_indices = session["raw_route_indices"]
            new_total_duration = 0
            for i in range(len(current_route_sequence_indices) - 1):
                from_idx = current_route_sequence_indices[i]
                to_idx = current_route_sequence_indices[i+1]
                new_total_duration += durations[from_idx][to_idx]
            
            old_duration = session["total_duration"]
            duration_diff = new_total_duration - old_duration
            
            # If delay > 15 mins or severe accident, force re-optimization
            if should_reroute or duration_diff > 15.0:
                print(f"[Realtime Tracker] Triggering reroute. Delay: {duration_diff:.2f} mins.")
                await manager.broadcast({
                    "type": "REROUTE_TRIGGERED",
                    "event": event_msg or "Significant route delay detected. Re-optimizing.",
                    "old_duration": old_duration,
                    "new_duration": new_total_duration
                })
                # We clear active session so we don't keep triggering until the new route is fetched
                global_state.active_route_session = None 
                
            elif event_msg:
                print(f"[Realtime Tracker] Traffic update. New ETA: {new_total_duration:.2f} mins.")
                await manager.broadcast({
                    "type": "REALTIME_UPDATE",
                    "event": event_msg,
                    "new_total_duration": round(new_total_duration, 2),
                    "delay": round(duration_diff, 2)
                })

        except Exception as e:
            print(f"[Realtime Tracker] Error: {e}")
            await asyncio.sleep(5)
