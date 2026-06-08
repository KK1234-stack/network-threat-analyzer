"""
Preprocessing logic shared between training (ml/train.py) and inference (ml/model.py).
Keeping this in one place ensures training and serving use identical transformations.
Populated after CICIDS EDA in ml/preprocess.py.
"""

import pandas as pd
import numpy as np

# These will be set after EDA on CICIDS2017
FEATURE_COLUMNS = []
LABEL_COLUMN = "Label"


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop infinite values and NaNs — common issue with CICIDS2017."""
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()
    return df


def preprocess_for_inference(df: pd.DataFrame, scaler) -> np.ndarray:
    """
    Applies the same transformations used during training.
    scaler should be loaded from the saved scaler artifact.
    """
    df = clean_df(df)
    X = df[FEATURE_COLUMNS].values
    X = scaler.transform(X)
    return X
