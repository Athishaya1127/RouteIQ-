import pandas as pd
import numpy as np
import random
import pickle
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

def generate_traffic_data(num_samples=2000):
    data = []
    for _ in range(num_samples):
        hour = random.randint(0, 23)
        day_of_week = random.randint(0, 6)
        hist_congestion = round(random.uniform(0.1, 0.9), 2)
        vehicle_density = round(random.uniform(0.1, 0.9), 2)
        avg_speed = round(random.uniform(10.0, 50.0), 1)
        
        # Ground truth formulation
        is_peak = 1 if hour in [8, 9, 10, 17, 18, 19, 20] else 0
        base = hist_congestion * 0.4 + vehicle_density * 0.4 + is_peak * 0.1
        noise = random.uniform(-0.1, 0.1)
        
        actual_future_congestion = min(max(base + noise, 0.1), 0.95)
        
        data.append({
            "hour": hour,
            "day": day_of_week,
            "hist": hist_congestion,
            "density": vehicle_density,
            "speed": avg_speed,
            "future_congestion": actual_future_congestion
        })
    return pd.DataFrame(data)

def train():
    print("Generating synthetic data for predictive traffic-aware routing...")
    df = generate_traffic_data()
    
    X = df[["hour", "day", "hist", "density", "speed"]]
    y = df["future_congestion"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training RandomForestRegressor...")
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)
    
    print(f"Model R^2 Score: {model.score(X_test, y_test):.4f}")
    
    os.makedirs(os.path.dirname(__file__), exist_ok=True)
    model_path = os.path.join(os.path.dirname(__file__), "traffic_predictor.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
        
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train()
