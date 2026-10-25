import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


FEATURES = ["zone", "hour", "day", "hist", "density", "speed"]
REQUIRED_COLUMNS = {"timestamp", "zone", "congestion", "vehicle_density", "avg_speed"}


def _time_splits(target_times: pd.Series):
    unique_times = sorted(target_times.dropna().unique())
    if len(unique_times) < 10:
        raise ValueError("At least 10 distinct target timestamps are required for chronological evaluation.")

    train_end = max(1, int(len(unique_times) * 0.7))
    validation_end = min(
        max(train_end + 1, int(len(unique_times) * 0.85)),
        len(unique_times) - 1,
    )
    train_cutoff = unique_times[train_end - 1]
    validation_cutoff = unique_times[validation_end - 1]

    train_mask = target_times <= train_cutoff
    validation_mask = (target_times > train_cutoff) & (target_times <= validation_cutoff)
    test_mask = target_times > validation_cutoff
    if not train_mask.any() or not validation_mask.any() or not test_mask.any():
        raise ValueError("The traffic dataset is too small for non-empty train, validation, and test periods.")
    return train_mask, validation_mask, test_mask, train_cutoff, validation_cutoff


def train_from_csv(input_path: Path, output_path: Path) -> dict:
    observations = pd.read_csv(input_path)
    missing_columns = REQUIRED_COLUMNS - set(observations.columns)
    if missing_columns:
        raise ValueError(f"Traffic CSV is missing required columns: {', '.join(sorted(missing_columns))}")

    observations["timestamp"] = pd.to_datetime(
        observations["timestamp"], errors="coerce", utc=True
    )
    for column in ("congestion", "vehicle_density", "avg_speed"):
        observations[column] = pd.to_numeric(observations[column], errors="coerce")
    observations["zone"] = observations["zone"].astype("string").str.strip()
    required = ["timestamp", "zone", "congestion", "vehicle_density", "avg_speed"]
    if observations[required].isna().any().any() or (observations["zone"] == "").any():
        raise ValueError("Traffic CSV contains missing or invalid required values.")
    if observations.empty:
        raise ValueError("Traffic CSV contains no valid observations.")
    if not np.isfinite(observations[["congestion", "vehicle_density", "avg_speed"]]).all().all():
        raise ValueError("Traffic CSV contains non-finite measurements.")
    if (
        ((observations["congestion"] < 0) | (observations["congestion"] > 1)).any()
        or ((observations["vehicle_density"] < 0) | (observations["vehicle_density"] > 1)).any()
        or (observations["avg_speed"] <= 0).any()
    ):
        raise ValueError("Congestion and density must be in [0, 1], and avg_speed must be positive.")

    observations = (
        observations.groupby(["zone", "timestamp"], as_index=False, sort=True)
        .agg(
            congestion=("congestion", "mean"),
            vehicle_density=("vehicle_density", "mean"),
            avg_speed=("avg_speed", "mean"),
        )
        .sort_values(["zone", "timestamp"])
    )
    grouped = observations.groupby("zone", sort=False)
    observations["future_congestion"] = grouped["congestion"].shift(-1)
    observations["target_timestamp"] = grouped["timestamp"].shift(-1)
    observations["hour"] = observations["timestamp"].dt.hour
    observations["day"] = observations["timestamp"].dt.dayofweek
    observations["hist"] = observations["congestion"]
    observations["density"] = observations["vehicle_density"]
    observations["speed"] = observations["avg_speed"]
    examples = observations.dropna(subset=["future_congestion", "target_timestamp"]).copy()
    if examples.empty:
        raise ValueError("Each zone needs at least two timestamped observations.")

    train_mask, validation_mask, test_mask, train_cutoff, validation_cutoff = _time_splits(
        examples["target_timestamp"]
    )
    feature_transform = ColumnTransformer(
        [("zone", OneHotEncoder(handle_unknown="ignore"), ["zone"])],
        remainder="passthrough",
    )
    model = Pipeline(
        [
            ("features", feature_transform),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=200,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    x_values = examples[FEATURES]
    y_values = examples["future_congestion"]
    model.fit(x_values[train_mask], y_values[train_mask])

    def score(mask):
        actual = y_values[mask]
        predicted = model.predict(x_values[mask])
        metrics = {
            "mae": float(mean_absolute_error(actual, predicted)),
            "rmse": float(math.sqrt(mean_squared_error(actual, predicted))),
        }
        if len(actual) > 1:
            metrics["r2"] = float(r2_score(actual, predicted))
        return metrics

    metrics = {
        "validation": score(validation_mask),
        "test": score(test_mask),
    }
    metadata = {
        "model": model,
        "features": FEATURES,
        "training_source": "historical_csv",
        "target": "congestion at the next observation for the same zone",
        "input_file": input_path.name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "rows": {
            "train": int(train_mask.sum()),
            "validation": int(validation_mask.sum()),
            "test": int(test_mask.sum()),
        },
        "time_boundaries": {
            "train_through": str(train_cutoff),
            "validation_through": str(validation_cutoff),
        },
        "metrics": metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as model_file:
        pickle.dump(metadata, model_file)
    return metadata


def main():
    parser = argparse.ArgumentParser(
        description="Train and chronologically evaluate RouteIQ's zone-level traffic predictor."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="CSV with timestamp, zone, congestion, vehicle_density, and avg_speed columns",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("road_traffic_predictor.pkl"),
        help="Model output path (defaults to the predictor used by RouteIQ).",
    )
    arguments = parser.parse_args()
    metadata = train_from_csv(arguments.csv_path, arguments.output)
    print(f"Model saved to {arguments.output}")
    print(f"Training rows: {metadata['rows']['train']}")
    print(f"Validation metrics: {metadata['metrics']['validation']}")
    print(f"Test metrics: {metadata['metrics']['test']}")


if __name__ == "__main__":
    main()
