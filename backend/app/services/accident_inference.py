from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


MODEL_PATH = (
    Path(__file__).resolve().parents[2] / "models" / "accident_model.joblib"
)
STANDARD_GRAVITY = 9.80665


@lru_cache(maxsize=1)
def load_model_bundle():
    return joblib.load(MODEL_PATH)


def extract_features(acceleration_g, rotation_deg_s):
    """Reproduce the 36 features from the Colab training notebook."""
    features = {}

    for prefix, readings in (
        ("acc", acceleration_g),
        ("gyro", rotation_deg_s),
    ):
        if readings.shape != (1600, 3):
            raise ValueError(f"{prefix}: expected 1,600 readings with 3 axes.")
        if not np.isfinite(readings).all():
            raise ValueError(f"{prefix}: readings must be finite.")

        for index, axis in enumerate("xyz"):
            values = readings[:, index]
            features[f"{prefix}_{axis}_mean"] = float(values.mean())
            features[f"{prefix}_{axis}_std"] = float(values.std())
            features[f"{prefix}_{axis}_min"] = float(values.min())
            features[f"{prefix}_{axis}_max"] = float(values.max())
            features[f"{prefix}_{axis}_abs_peak"] = float(np.abs(values).max())

        magnitude = np.linalg.norm(readings, axis=1)
        features[f"{prefix}_mag_mean"] = float(magnitude.mean())
        features[f"{prefix}_mag_std"] = float(magnitude.std())
        features[f"{prefix}_mag_peak"] = float(magnitude.max())

    return features


def predict_window(samples, *, sampling_hz):
    """Score an ordered, validated window in m/s² and degrees/second."""
    bundle = load_model_bundle()
    settings = bundle["settings"]

    if sampling_hz != settings["sampling_hz"]:
        raise ValueError(f"Expected {settings['sampling_hz']} Hz.")
    if len(samples) != settings["samples_per_event"]:
        raise ValueError(f"Expected {settings['samples_per_event']} samples.")

    acceleration = np.array(
        [[s["accel_x"], s["accel_y"], s["accel_z"]] for s in samples],
        dtype=float,
    ) / STANDARD_GRAVITY

    rotation = np.array(
        [[s["gyro_x"], s["gyro_y"], s["gyro_z"]] for s in samples],
        dtype=float,
    )

    features = extract_features(acceleration, rotation)
    feature_names = list(bundle["feature_names"])
    if len(feature_names) != len(features) or set(feature_names) != set(features):
        raise ValueError("Extracted feature names do not match the model bundle.")

    model = bundle["model"]
    frame = pd.DataFrame(
        [[features[name] for name in feature_names]],
        columns=feature_names,
    )

    crash_index = list(model.classes_).index(1)
    crash_score = float(model.predict_proba(frame)[0, crash_index])
    threshold = float(bundle["threshold"])
    predicted_class = int(crash_score >= threshold)

    return {
        "crash_score": crash_score,
        "threshold": threshold,
        "predicted_class": predicted_class,
        "label": bundle["model_labels"][str(predicted_class)],
    }