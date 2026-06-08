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

# Model will be loaded once at startup
_model = None
_model_version = "dummy-v0"
_model_type = "dummy"  # will be "lstm" or "rf" once trained

MODELS_DIR = "/app/models"
FEATURE_COLUMNS = []  # will be populated after CICIDS EDA


def load_model():
    """Called once at app startup. Loads whichever model file exists."""
    global _model, _model_version, _model_type

    lstm_path = os.path.join(MODELS_DIR, "lstm_model.pt")
    rf_path = os.path.join(MODELS_DIR, "rf_model.pkl")

    if os.path.exists(lstm_path):
        import torch
        # TODO: import your LSTM class here once defined in ml/train.py
        # _model = LSTMClassifier(...)
        # _model.load_state_dict(torch.load(lstm_path))
        # _model.eval()
        _model_type = "lstm"
        _model_version = "lstm-v1"

    elif os.path.exists(rf_path):
        import joblib
        _model = joblib.load(rf_path)
        _model_type = "rf"
        _model_version = "rf-v1"

    else:
        # No model file yet — dummy mode for development
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
