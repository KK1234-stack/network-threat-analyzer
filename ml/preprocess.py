"""
CICIDS2017 preprocessing pipeline.
Run this standalone before training.
Outputs: X_train.npy, X_test.npy, y_train.npy, y_test.npy, scaler.pkl, label_encoder.pkl
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE
import joblib
import os

DATA_DIR = "./data"
OUTPUT_DIR = "./processed"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Columns to drop — identifiers, target, constants, near-constants, and exact duplicate
# FEATURE_COLUMNS (65 total) derived from EDA in ml/eda_and_training.ipynb
DROP_COLS = [
    "Label",
    "Fwd Header Length.1",       # exact duplicate of Fwd Header Length
    # constant across all flows
    "Bwd PSH Flags", "Bwd URG Flags",
    "Fwd Avg Bytes/Bulk", "Fwd Avg Packets/Bulk", "Fwd Avg Bulk Rate",
    "Bwd Avg Bytes/Bulk", "Bwd Avg Packets/Bulk", "Bwd Avg Bulk Rate",
    # near-constant (>99.9% single value)
    "Fwd URG Flags", "RST Flag Count", "CWE Flag Count", "ECE Flag Count",
]


def load_cicids(data_dir: str) -> pd.DataFrame:
    """Load all CICIDS2017 CSVs from a directory and concat."""
    dfs = []
    for f in os.listdir(data_dir):
        if f.endswith(".csv"):
            print(f"Loading {f}...")
            dfs.append(pd.read_csv(os.path.join(data_dir, f), low_memory=False))
    return pd.concat(dfs, ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()
    return df


def main():
    df = load_cicids(DATA_DIR)
    df = clean(df)

    print(f"Total samples: {len(df)}")
    print(f"Label distribution:\n{df['Label'].value_counts()}")

    X = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    y = df["Label"].values

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X.values, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    # Handle class imbalance with SMOTE on training set only
    print("Applying SMOTE...")
    sm = SMOTE(random_state=42)
    X_train, y_train = sm.fit_resample(X_train, y_train)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # Save artifacts
    np.save(os.path.join(OUTPUT_DIR, "X_train.npy"), X_train)
    np.save(os.path.join(OUTPUT_DIR, "X_test.npy"), X_test)
    np.save(os.path.join(OUTPUT_DIR, "y_train.npy"), y_train)
    np.save(os.path.join(OUTPUT_DIR, "y_test.npy"), y_test)
    joblib.dump(scaler, os.path.join(OUTPUT_DIR, "scaler.pkl"))
    joblib.dump(le, os.path.join(OUTPUT_DIR, "label_encoder.pkl"))

    print(f"Saved to {OUTPUT_DIR}/")
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")
    print(f"Classes: {le.classes_}")


if __name__ == "__main__":
    main()
