"""
Evaluate a saved model on the test set.
Run after training to get final metrics and confusion matrix.
"""

import numpy as np
import joblib
import os
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, f1_score

PROCESSED_DIR = "./processed"
MODELS_DIR = "./models"


def evaluate_rf():
    X_test = np.load(os.path.join(PROCESSED_DIR, "X_test.npy"))
    y_test = np.load(os.path.join(PROCESSED_DIR, "y_test.npy"))
    le = joblib.load(os.path.join(PROCESSED_DIR, "label_encoder.pkl"))
    model = joblib.load(os.path.join(MODELS_DIR, "rf_model.pkl"))

    preds = model.predict(X_test)
    print("=== RF Evaluation ===")
    print(classification_report(y_test, preds, target_names=le.classes_))

    cm = confusion_matrix(y_test, preds)
    plt.figure(figsize=(12, 10))
    sns.heatmap(cm, annot=True, fmt="d", xticklabels=le.classes_, yticklabels=le.classes_)
    plt.title("RF Confusion Matrix")
    plt.tight_layout()
    plt.savefig(os.path.join(MODELS_DIR, "rf_confusion_matrix.png"))
    print("Saved confusion matrix to models/rf_confusion_matrix.png")


if __name__ == "__main__":
    evaluate_rf()
