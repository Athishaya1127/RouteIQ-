import pickle
import os
import pandas as pd

class LiveForecaster:
    def __init__(self):
        self.model = None
        self._load_model()
        
    def _load_model(self):
        model_path = os.path.join(os.path.dirname(__file__), "traffic_predictor.pkl")
        if os.path.exists(model_path):
            with open(model_path, "rb") as f:
                self.model = pickle.load(f)
        else:
            print("[Warning] traffic_predictor.pkl not found.")

    def predict(self, zone: str, hour: int, day_of_week: int, hist_congestion: float, density: float, speed: float) -> dict:
        predicted = hist_congestion # fallback
        if self.model:
            input_df = pd.DataFrame([{
                "hour": hour,
                "day": day_of_week,
                "hist": hist_congestion,
                "density": density,
                "speed": speed
            }])
            predicted = self.model.predict(input_df)[0]
            
        return {
            "predicted_congestion": max(0.1, min(predicted, 0.95))
        }

live_forecaster = LiveForecaster()
