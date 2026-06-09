import os
import time
import numpy as np
import pandas as pd

_model = None
_scaler = None
_label_encoder = None
_model_version = "not-loaded"
_model_type = "dummy"  # "rf" | "lstm" | "dummy"

MODELS_DIR    = "/app/models"
PROCESSED_DIR = "/app/processed"

RF_MODEL_NAME   = "network-threat-analyzer-rf"
LSTM_MODEL_NAME = "network-threat-analyzer-lstm"


def _load_artifacts():
    """Load scaler and label encoder — shared by RF and LSTM."""
    global _scaler, _label_encoder
    import joblib
    scaler_path = os.path.join(PROCESSED_DIR, "scaler.pkl")
    le_path     = os.path.join(PROCESSED_DIR, "label_encoder.pkl")
    if os.path.exists(scaler_path) and os.path.exists(le_path):
        _scaler        = joblib.load(scaler_path)
        _label_encoder = joblib.load(le_path)
        return True
    print("[model] scaler.pkl or label_encoder.pkl not found in /app/processed/")
    return False


def _load_from_registry() -> bool:
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
                _model        = joblib.load(rf_path)
                _model_type   = "rf"
                _model_version = f"rf-v{rf_versions[0].version}"
                print(f"[model] Loaded from registry: {_model_version}")
                return True

        lstm_versions = client.get_latest_versions(LSTM_MODEL_NAME, stages=["Production"])
        if lstm_versions:
            _model_type   = "lstm"
            _model_version = f"lstm-v{lstm_versions[0].version}"
            print(f"[model] Registry says lstm is Production: {_model_version}")
            return True

    except Exception as e:
        print(f"[model] Registry check failed ({e}), falling back to files")
    return False


def load_model():
    global _model, _model_version, _model_type

    _load_artifacts()

    if _load_from_registry():
        return

    rf_path   = os.path.join(MODELS_DIR, "rf_model.pkl")
    lstm_path = os.path.join(MODELS_DIR, "lstm_model.pt")

    if os.path.exists(rf_path):
        import joblib
        _model        = joblib.load(rf_path)
        _model_type   = "rf"
        _model_version = "rf-v1"

    elif os.path.exists(lstm_path):
        _model_type   = "lstm"
        _model_version = "lstm-v1"

    else:
        _model        = None
        _model_type   = "dummy"
        _model_version = "dummy-v0"

    print(f"[model] Loaded: {_model_version} ({_model_type})")


def run_inference(df: pd.DataFrame) -> dict:
    from app.ml.preprocess import preprocess_for_inference, FEATURE_COLUMNS

    start = time.time()

    if _model_type == "dummy" or _model is None:
        classes     = ["BENIGN", "DDoS", "PortScan", "DoS Hulk", "FTP-Patator"]
        weights     = [0.7, 0.1, 0.08, 0.07, 0.05]
        labels      = np.random.choice(classes, size=len(df), p=weights).tolist()
        confidences = np.random.uniform(0.6, 0.99, size=len(df)).tolist()

    elif _model_type == "rf":
        missing = [c for c in FEATURE_COLUMNS if c not in df.columns.str.strip().tolist()]
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing[:5]}{'...' if len(missing) > 5 else ''}")

        X           = preprocess_for_inference(df, _scaler)
        preds       = _model.predict(X)
        proba       = _model.predict_proba(X)
        labels      = _label_encoder.inverse_transform(preds).tolist()
        confidences = proba.max(axis=1).tolist()

    elif _model_type == "lstm":
        # TODO: wire up when LSTM is promoted to production
        raise NotImplementedError("LSTM inference not yet implemented")

    elapsed_ms = (time.time() - start) * 1000

    return {
        "labels":           labels,
        "confidences":      confidences,
        "model_version":    _model_version,
        "inference_time_ms": round(elapsed_ms, 2),
    }
