"""
Background retraining logic. Trains RF + LSTM on preprocessed CICIDS data,
registers both to the MLflow model registry, and promotes the winner to Production.
After training completes, hot-reloads the model in the running API process.
"""

import os
import time
import threading
import numpy as np
import joblib
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
import mlflow
import mlflow.sklearn
import mlflow.pytorch
from mlflow.tracking import MlflowClient

from app.core.config import settings

PROCESSED_DIR = "/app/processed"
MODELS_DIR = "/app/models"

RF_MODEL_NAME = "network-threat-analyzer-rf"
LSTM_MODEL_NAME = "network-threat-analyzer-lstm"

_state: dict = {
    "status": "idle",   # idle | running | done | failed
    "started_at": None,
    "finished_at": None,
    "metrics": None,
    "error": None,
}
_lock = threading.Lock()


def get_state() -> dict:
    with _lock:
        return _state.copy()


def _set_state(**kwargs):
    with _lock:
        _state.update(kwargs)


class LSTMClassifier(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.3)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def _promote(client: MlflowClient, model_name: str, version: str):
    client.transition_model_version_stage(model_name, version, "Production", archive_existing_versions=True)


def _run_training():
    try:
        _set_state(status="running", started_at=time.time(), error=None, metrics=None)

        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment("network-threat-analyzer")
        client = MlflowClient(tracking_uri=settings.MLFLOW_TRACKING_URI)

        X_train = np.load(os.path.join(PROCESSED_DIR, "X_train.npy"))
        X_test  = np.load(os.path.join(PROCESSED_DIR, "X_test.npy"))
        y_train = np.load(os.path.join(PROCESSED_DIR, "y_train.npy"))
        y_test  = np.load(os.path.join(PROCESSED_DIR, "y_test.npy"))
        num_classes = len(np.unique(y_train))

        # --- RF ---
        with mlflow.start_run(run_name="rf-retrain") as run:
            params = {"n_estimators": 100, "max_depth": 20, "random_state": 42, "n_jobs": -1}
            mlflow.log_params(params)
            rf = RandomForestClassifier(**params)
            rf.fit(X_train, y_train)
            rf_f1 = f1_score(y_test, rf.predict(X_test), average="weighted")
            mlflow.log_metric("weighted_f1", rf_f1)
            model_info = mlflow.sklearn.log_model(rf, "rf_model", registered_model_name=RF_MODEL_NAME)
            rf_version = client.get_latest_versions(RF_MODEL_NAME, stages=["None"])[0].version

        # --- LSTM ---
        SEQ_LEN, HIDDEN, LAYERS, EPOCHS, BATCH, LR = 10, 128, 2, 20, 256, 1e-3
        with mlflow.start_run(run_name="lstm-retrain"):
            mlflow.log_params({"seq_len": SEQ_LEN, "hidden_size": HIDDEN, "num_layers": LAYERS,
                               "epochs": EPOCHS, "batch_size": BATCH, "lr": LR})
            fps = X_train.shape[1] // SEQ_LEN
            trim = fps * SEQ_LEN
            X_tr = torch.tensor(X_train[:, :trim].reshape(-1, SEQ_LEN, fps), dtype=torch.float32)
            X_te = torch.tensor(X_test[:, :trim].reshape(-1, SEQ_LEN, fps), dtype=torch.float32)
            y_tr = torch.tensor(y_train, dtype=torch.long)
            y_te = torch.tensor(y_test, dtype=torch.long)
            loader = DataLoader(TensorDataset(X_tr, y_tr), batch_size=BATCH, shuffle=True)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            lstm_model = LSTMClassifier(fps, HIDDEN, LAYERS, num_classes).to(device)
            optimizer = torch.optim.Adam(lstm_model.parameters(), lr=LR)
            criterion = nn.CrossEntropyLoss()
            for epoch in range(EPOCHS):
                lstm_model.train()
                total_loss = 0.0
                for xb, yb in loader:
                    xb, yb = xb.to(device), yb.to(device)
                    optimizer.zero_grad()
                    loss = criterion(lstm_model(xb), yb)
                    loss.backward()
                    optimizer.step()
                    total_loss += loss.item()
                mlflow.log_metric("train_loss", total_loss / len(loader), step=epoch)
            lstm_model.eval()
            with torch.no_grad():
                lstm_preds = lstm_model(X_te.to(device)).argmax(dim=1).cpu().numpy()
            lstm_f1 = f1_score(y_test, lstm_preds, average="weighted")
            mlflow.log_metric("weighted_f1", lstm_f1)
            torch.save(lstm_model.state_dict(), os.path.join(MODELS_DIR, "lstm_model.pt"))
            mlflow.pytorch.log_model(lstm_model, "lstm_model", registered_model_name=LSTM_MODEL_NAME)
            lstm_version = client.get_latest_versions(LSTM_MODEL_NAME, stages=["None"])[0].version

        # --- Promote winner, archive loser ---
        if rf_f1 >= lstm_f1:
            joblib.dump(rf, os.path.join(MODELS_DIR, "rf_model.pkl"))
            _promote(client, RF_MODEL_NAME, rf_version)
            winner = "rf"
        else:
            _promote(client, LSTM_MODEL_NAME, lstm_version)
            winner = "lstm"

        metrics = {"rf_f1": round(rf_f1, 4), "lstm_f1": round(lstm_f1, 4), "winner": winner}
        _set_state(status="done", finished_at=time.time(), metrics=metrics)

        # Hot-reload the newly saved model
        from app.ml.model import load_model
        load_model()

    except Exception as e:
        _set_state(status="failed", finished_at=time.time(), error=str(e))


def trigger_retrain() -> bool:
    """Start retraining in a background thread. Returns False if already running."""
    with _lock:
        if _state["status"] == "running":
            return False
    thread = threading.Thread(target=_run_training, daemon=True)
    thread.start()
    return True
