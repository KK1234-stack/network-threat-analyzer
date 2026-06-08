"""
Train RF baseline and LSTM model on preprocessed CICIDS2017 data.
All runs tracked with MLflow. Best model saved to ./models/
Run after preprocess.py.
"""

import numpy as np
import mlflow
import mlflow.sklearn
import mlflow.pytorch
import joblib
import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score

PROCESSED_DIR = "./processed"
MODELS_DIR = "./models"
os.makedirs(MODELS_DIR, exist_ok=True)

mlflow.set_experiment("network-threat-analyzer")


# --- Load data ---

def load_data():
    X_train = np.load(os.path.join(PROCESSED_DIR, "X_train.npy"))
    X_test = np.load(os.path.join(PROCESSED_DIR, "X_test.npy"))
    y_train = np.load(os.path.join(PROCESSED_DIR, "y_train.npy"))
    y_test = np.load(os.path.join(PROCESSED_DIR, "y_test.npy"))
    return X_train, X_test, y_train, y_test


# --- RF Baseline ---

def train_rf(X_train, X_test, y_train, y_test):
    with mlflow.start_run(run_name="random-forest-baseline"):
        params = {"n_estimators": 100, "max_depth": 20, "random_state": 42, "n_jobs": -1}
        mlflow.log_params(params)

        model = RandomForestClassifier(**params)
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        f1 = f1_score(y_test, preds, average="weighted")
        mlflow.log_metric("weighted_f1", f1)

        print(f"\n[RF] Weighted F1: {f1:.4f}")
        print(classification_report(y_test, preds))

        joblib.dump(model, os.path.join(MODELS_DIR, "rf_model.pkl"))
        mlflow.sklearn.log_model(model, "rf_model")

    return f1


# --- LSTM Model ---

class LSTMClassifier(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.3)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        # x shape: (batch, seq_len, features)
        out, _ = self.lstm(x)
        out = self.fc(out[:, -1, :])  # take last timestep
        return out


def train_lstm(X_train, X_test, y_train, y_test, num_classes):
    with mlflow.start_run(run_name="lstm-classifier"):
        # Hyperparams
        SEQ_LEN = 10       # treat each flow as a sequence of SEQ_LEN sub-windows
        HIDDEN = 128
        LAYERS = 2
        EPOCHS = 20
        BATCH = 256
        LR = 1e-3

        params = {
            "seq_len": SEQ_LEN, "hidden_size": HIDDEN, "num_layers": LAYERS,
            "epochs": EPOCHS, "batch_size": BATCH, "lr": LR,
        }
        mlflow.log_params(params)

        # Reshape flat features into (samples, seq_len, features_per_step)
        # For CICIDS this means splitting the 78 features into SEQ_LEN windows
        n_features = X_train.shape[1]
        features_per_step = n_features // SEQ_LEN
        trim = features_per_step * SEQ_LEN

        X_tr = torch.tensor(X_train[:, :trim].reshape(-1, SEQ_LEN, features_per_step), dtype=torch.float32)
        X_te = torch.tensor(X_test[:, :trim].reshape(-1, SEQ_LEN, features_per_step), dtype=torch.float32)
        y_tr = torch.tensor(y_train, dtype=torch.long)
        y_te = torch.tensor(y_test, dtype=torch.long)

        loader = DataLoader(TensorDataset(X_tr, y_tr), batch_size=BATCH, shuffle=True)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = LSTMClassifier(features_per_step, HIDDEN, LAYERS, num_classes).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=LR)
        criterion = nn.CrossEntropyLoss()

        for epoch in range(EPOCHS):
            model.train()
            total_loss = 0
            for xb, yb in loader:
                xb, yb = xb.to(device), yb.to(device)
                optimizer.zero_grad()
                loss = criterion(model(xb), yb)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            avg_loss = total_loss / len(loader)
            mlflow.log_metric("train_loss", avg_loss, step=epoch)
            print(f"Epoch {epoch+1}/{EPOCHS} | Loss: {avg_loss:.4f}")

        # Evaluate
        model.eval()
        with torch.no_grad():
            preds = model(X_te.to(device)).argmax(dim=1).cpu().numpy()

        f1 = f1_score(y_test, preds, average="weighted")
        mlflow.log_metric("weighted_f1", f1)

        print(f"\n[LSTM] Weighted F1: {f1:.4f}")
        print(classification_report(y_test, preds))

        torch.save(model.state_dict(), os.path.join(MODELS_DIR, "lstm_model.pt"))
        mlflow.pytorch.log_model(model, "lstm_model")

    return f1


# --- Main ---

if __name__ == "__main__":
    X_train, X_test, y_train, y_test = load_data()
    num_classes = len(np.unique(y_train))

    print("=== Training RF Baseline ===")
    rf_f1 = train_rf(X_train, X_test, y_train, y_test)

    print("\n=== Training LSTM ===")
    lstm_f1 = train_lstm(X_train, X_test, y_train, y_test, num_classes)

    print(f"\n=== Results ===")
    print(f"RF F1:   {rf_f1:.4f}")
    print(f"LSTM F1: {lstm_f1:.4f}")
    print(f"Winner:  {'LSTM' if lstm_f1 > rf_f1 else 'RF'}")
