import pickle
import os
import random
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

class RoadPredictor:
    def __init__(self):
        self.model = None
        self.model_uses_zone = False
        self.training_source = "synthetic_fallback"
        self._load_or_train()

    def _load_or_train(self):
        model_path = os.path.join(os.path.dirname(__file__), "road_traffic_predictor.pkl")
        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    saved_model = pickle.load(f)
                if isinstance(saved_model, dict) and "model" in saved_model:
                    self.model = saved_model["model"]
                    self.model_uses_zone = "zone" in saved_model.get("features", [])
                    self.training_source = saved_model.get("training_source", "unverified")
                else:
                    self.model = saved_model
                    self.training_source = "legacy_synthetic_model"
                print(f"[RouteIQ] Loaded road-level ML predictor ({self.training_source}).")
                return
            except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ValueError, TypeError) as e:
                print(f"[RouteIQ Warning] Failed to load road predictor: {e}. Using synthetic fallback.")

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
        self.training_source = "synthetic_fallback"

        try:
            with open(save_path, "wb") as f:
                pickle.dump(
                    {
                        "model": self.model,
                        "features": ["hour", "day", "hist", "speed", "neighbor", "upstream"],
                        "training_source": self.training_source,
                    },
                    f,
                )
            print("[RouteIQ] Successfully trained and saved time-dependent road predictor.")
        except OSError as e:
            print(f"[RouteIQ Error] Could not save trained model: {e}")

    def predict_congestion(
        self,
        hour: int,
        day: int,
        hist: float,
        speed: float,
        neighbor: float,
        upstream: float,
        zone: str = "",
        density: float = 0.3,
    ) -> float:
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

        features = {
            "hour": hour,
            "day": day,
            "hist": hist,
            "speed": speed,
        }
        if self.model_uses_zone:
            features["zone"] = zone
            features["density"] = density
        else:
            features["neighbor"] = neighbor
            features["upstream"] = upstream

        input_df = pd.DataFrame([features])
        
        pred = self.model.predict(input_df)[0]
        return float(max(0.1, min(pred, 0.95)))

road_predictor = RoadPredictor()
