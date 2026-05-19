import pickle
import os
import random
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

class DemandForecaster:
    def __init__(self):
        self.model = None
        self._load_or_train()

    def _load_or_train(self):
        model_path = os.path.join(os.path.dirname(__file__), "demand_forecaster.pkl")
        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    self.model = pickle.load(f)
                print("[RouteIQ] Loaded existing demand forecasting ML model.")
                return
            except Exception as e:
                print(f"[RouteIQ Warning] Failed to load demand forecaster: {e}. Re-training...")

        print("[RouteIQ] Training new Demand Forecasting Engine...")
        self._train_model(model_path)

    def _train_model(self, save_path: str):
        # Generate high-fidelity synthetic demand training samples
        data = []
        np.random.seed(101)
        random.seed(101)

        # Zones: T Nagar, OMR, Velachery, Anna Nagar, Tambaram, Adyar
        # Simulate peak demand hours (lunch peak 12-2 PM, dinner peak 7-9 PM)
        for _ in range(1500):
            hour = random.randint(0, 23)
            day = random.randint(0, 6)
            
            is_peak = (12 <= hour <= 14) or (19 <= hour <= 21)
            base_density = random.uniform(0.6, 0.95) if is_peak else random.uniform(0.1, 0.45)
            
            # Historical density matches peak hour patterns
            hist_density = round(max(0.05, min(base_density + random.uniform(-0.1, 0.1), 0.95)), 2)
            
            # Congestion slightly correlates with delivery demand spikes
            nearby_congestion = round(max(0.1, min(hist_density + random.uniform(-0.2, 0.3), 0.95)), 2)
            
            # Recent active deliveries in the area
            recent_activity = round(max(0.0, hist_density * 10.0 + random.uniform(-2, 2)), 1)
            
            # Future demand density predicted (20-30 mins ahead)
            future_density = hist_density
            if is_peak:
                future_density = min(0.98, future_density + random.uniform(0.05, 0.15))
            else:
                future_density = max(0.05, future_density - random.uniform(0.05, 0.1))

            data.append({
                "hour": hour,
                "day": day,
                "hist_density": hist_density,
                "nearby_congestion": nearby_congestion,
                "recent_activity": recent_activity,
                "future_density": round(future_density, 2)
            })

        df = pd.DataFrame(data)
        X = df[["hour", "day", "hist_density", "nearby_congestion", "recent_activity"]]
        y = df["future_density"]

        self.model = RandomForestRegressor(n_estimators=25, random_state=101, n_jobs=-1)
        self.model.fit(X, y)

        try:
            with open(save_path, "wb") as f:
                pickle.dump(self.model, f)
            print("[RouteIQ] Successfully trained and saved demand forecasting model.")
        except Exception as e:
            print(f"[RouteIQ Error] Could not save demand forecaster model: {e}")

    def predict_demand(self, hour: int, day: int, hist_density: float, nearby_congestion: float, recent_activity: float) -> float:
        """
        Predict future order demand density (0.0 to 1.0).
        """
        if self.model is None:
            # Fallback
            is_peak = (12 <= hour <= 14) or (19 <= hour <= 21)
            return min(0.95, hist_density + 0.2) if is_peak else max(0.05, hist_density - 0.1)

        input_df = pd.DataFrame([{
            "hour": hour,
            "day": day,
            "hist_density": hist_density,
            "nearby_congestion": nearby_congestion,
            "recent_activity": recent_activity
        }])
        
        pred = self.model.predict(input_df)[0]
        return float(max(0.05, min(pred, 0.98)))

demand_forecaster = DemandForecaster()
