import pickle
import os
import random
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

class RoadPredictor:
    def __init__(self):
        self.model = None
        self._load_or_train()

    def _load_or_train(self):
        model_path = os.path.join(os.path.dirname(__file__), "road_traffic_predictor.pkl")
        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    self.model = pickle.load(f)
                print("[RouteIQ] Loaded existing road-level ML predictor.")
                return
            except Exception as e:
                print(f"[RouteIQ Warning] Failed to load road predictor: {e}. Re-training...")

        # No model or error loading, let's train a high-fidelity synthetic model
        print("[RouteIQ] Training new Time-Dependent Road Predictor model...")
        self._train_model(model_path)

    def _train_model(self, save_path: str):
        # Generate high-fidelity synthetic training samples
        # Representing diverse times of day (rush hours vs light hours), road types, and speeds
        data = []
        # Simulate 1000 records of traffic state
        np.random.seed(42)
        random.seed(42)

        for _ in range(2000):
            hour = random.randint(0, 23)
            day = random.randint(0, 6)
            
            # Historical congestion generally higher in peak hours
            is_peak = (8 <= hour <= 10) or (17 <= hour <= 19)
            base_hist = random.uniform(0.5, 0.85) if is_peak else random.uniform(0.1, 0.4)
            hist = round(max(0.1, min(base_hist + random.uniform(-0.1, 0.1), 0.95)), 2)
            
            # Vehicle speeds drop under congestion
            avg_speed = round(max(10.0, 50.0 * (1.0 - hist)), 1)
            
            # Neighboring roads usually match the congestion pattern (correlation)
            neighbor_congestion = round(max(0.1, min(hist + random.uniform(-0.15, 0.15), 0.95)), 2)
            upstream_congestion = round(max(0.1, min(hist + random.uniform(-0.15, 0.15), 0.95)), 2)
            
            # Future congestion: add time-of-day peak trends
            # Let's say downstream bottleneck becomes worse during rush hours
            future_congestion = hist
            if is_peak:
                future_congestion = min(0.95, future_congestion + random.uniform(0.05, 0.2))
            else:
                future_congestion = max(0.1, future_congestion - random.uniform(0.05, 0.15))
                
            data.append({
                "hour": hour,
                "day": day,
                "hist": hist,
                "speed": avg_speed,
                "neighbor": neighbor_congestion,
                "upstream": upstream_congestion,
                "future_congestion": round(future_congestion, 2)
            })

        df = pd.DataFrame(data)
        X = df[["hour", "day", "hist", "speed", "neighbor", "upstream"]]
        y = df["future_congestion"]

        self.model = RandomForestRegressor(n_estimators=30, random_state=42, n_jobs=-1)
        self.model.fit(X, y)

        try:
            with open(save_path, "wb") as f:
                pickle.dump(self.model, f)
            print("[RouteIQ] Successfully trained and saved time-dependent road predictor.")
        except Exception as e:
            print(f"[RouteIQ Error] Could not save trained model: {e}")

    def predict_congestion(self, hour: int, day: int, hist: float, speed: float, neighbor: float, upstream: float) -> float:
        """
        Predicts future congestion at a specific future arrival time (hour/day).
        """
        if self.model is None:
            # High-fidelity fallback logic
            is_peak = (8 <= hour <= 10) or (17 <= hour <= 19)
            base = hist
            if is_peak:
                base = min(0.95, base + 0.15)
            else:
                base = max(0.1, base - 0.1)
            return base

        input_df = pd.DataFrame([{
            "hour": hour,
            "day": day,
            "hist": hist,
            "speed": speed,
            "neighbor": neighbor,
            "upstream": upstream
        }])
        
        pred = self.model.predict(input_df)[0]
        return float(max(0.1, min(pred, 0.95)))

road_predictor = RoadPredictor()
