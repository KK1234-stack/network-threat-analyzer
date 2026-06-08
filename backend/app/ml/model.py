"""
Model loading and inference.
Actual model files (.pt for LSTM, .pkl for RF) are mounted into /app/models/
at runtime via docker-compose volume mount.

Until the ML training is done (ml/train.py), this module returns dummy predictions
so the rest of the app can be built and tested independently.
"""

import os
import time
import numpy as np
import pandas as pd

_model = None
_model_version = "dummy-v0"
_model_type = "dummy"  # "rf" | "lstm" | "dummy"

MODELS_DIR = "/app/models"
FEATURE_COLUMNS = []  # populated after CICIDS EDA

RF_MODEL_NAME = "network-threat-analyzer-rf"
LSTM_MODEL_NAME = "network-threat-analyzer-lstm"


def _load_from_registry() -> bool:
    """
    Check MLflow registry for a Production model.
    Returns True if a model was loaded, False otherwise.
    """
    global _model, _model_version, _model_type
    try:
        from mlflow.tracking import MlflowClient
        from app.core.config import settings

        client = MlflowClient(tracking_uri=settings.MLFLOW_TRACKING_URI)

        rf_versions = client.get_latest_versions(RF_MODEL_NAME, stages=["Production"])
        if rf_versions:
            import joblib
            rf_path = os.path.join(MODELS_DIR, "rf_model.pkl")
            if os.path.exists(rf_path):
                _model = joblib.load(rf_path)
                _model_type = "rf"
                _model_version = f"rf-v{rf_versions[0].version}"
                print(f"[model] Loaded from registry: {_model_version}")
                return True

        lstm_versions = client.get_latest_versions(LSTM_MODEL_NAME, stages=["Production"])
        if lstm_versions:
            _model_type = "lstm"
            _model_version = f"lstm-v{lstm_versions[0].version}"
            print(f"[model] Registry says lstm is Production: {_model_version}")
            return True

    except Exception as e:
        print(f"[model] Registry check failed ({e}), falling back to files")
    return False


def load_model():
    """Called at startup and after retraining. Checks registry first, then falls back to files."""
    global _model, _model_version, _model_type

    if _load_from_registry():
        return

    lstm_path = os.path.join(MODELS_DIR, "lstm_model.pt")
    rf_path = os.path.join(MODELS_DIR, "rf_model.pkl")

    if os.path.exists(rf_path):
        import joblib
        _model = joblib.load(rf_path)
        _model_type = "rf"
        _model_version = "rf-v1"

    elif os.path.exists(lstm_path):
        _model_type = "lstm"
        _model_version = "lstm-v1"

    else:
        _model = None
        _model_type = "dummy"
        _model_version = "dummy-v0"

    print(f"[model] Loaded: {_model_version} ({_model_type})")


def run_inference(df: pd.DataFrame) -> dict:
    """
    Takes a DataFrame of network flows, returns labels + confidences.
    Falls back to dummy random predictions if no model is loaded.
    """
    start = time.time()

    if _model_type == "dummy" or _model is None:
        # Dummy predictions for development/testing
        classes = ["BENIGN", "DDoS", "PortScan", "DoS Hulk", "FTP-Patator"]
        weights = [0.7, 0.1, 0.08, 0.07, 0.05]
        labels = np.random.choice(classes, size=len(df), p=weights).tolist()
        confidences = np.random.uniform(0.6, 0.99, size=len(df)).tolist()

    elif _model_type == "rf":
        # TODO: preprocess df with the same pipeline used during training
        # X = preprocess(df)
        # labels = _model.predict(X).tolist()
        # confidences = _model.predict_proba(X).max(axis=1).tolist()
        pass

    elif _model_type == "lstm":
        # TODO: preprocess + run through LSTM
        pass

    elapsed_ms = (time.time() - start) * 1000

    return {
        "labels": labels,
        "confidences": confidences,
        "model_version": _model_version,
        "inference_time_ms": round(elapsed_ms, 2),
    }
