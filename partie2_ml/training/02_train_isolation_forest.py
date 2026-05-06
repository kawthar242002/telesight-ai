"""
TeleSight AI — Train Isolation Forest (unsupervised anomaly detection)
Trained on normal samples only (is_anomaly == 0).
"""

import pickle
import sys
import importlib.util
from pathlib import Path
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, roc_auc_score

# Import 01_prepare_features.py via importlib (filename starts with digit)
_spec = importlib.util.spec_from_file_location(
    "prepare_features", Path(__file__).parent / "01_prepare_features.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["prepare_features"] = _mod
_spec.loader.exec_module(_mod)
load_and_engineer = _mod.load_and_engineer
prepare_splits    = _mod.prepare_splits
MODELS_DIR        = _mod.MODELS_DIR

MODELS_DIR.mkdir(exist_ok=True)


def train():
    print("=== TeleSight AI — Isolation Forest Training ===\n")
    df = load_and_engineer()
    X_train, X_test, ya_train, ya_test, _, _, scaler, _ = prepare_splits(df)

    # Train on normal samples ONLY
    normal_mask = ya_train == 0
    X_normal    = X_train[normal_mask]
    print(f"\n[3/4] Training Isolation Forest on {len(X_normal)} normal samples...")

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        max_samples="auto",
        max_features=1.0,
        bootstrap=False,
        random_state=42,
        n_jobs=-1,
        verbose=0,
    )
    model.fit(X_normal)

    # Evaluate on test set
    print("[4/4] Evaluating...")
    scores  = model.decision_function(X_test)   # higher = more normal
    preds   = model.predict(X_test)             # 1=normal, -1=anomaly
    # Convert to binary (1 = anomaly)
    y_pred  = (preds == -1).astype(int)

    print(f"\nClassification Report:\n{classification_report(ya_test, y_pred, target_names=['normal','anomaly'])}")
    try:
        auc = roc_auc_score(ya_test, -scores)  # negate: lower score = more anomalous
        print(f"ROC-AUC: {auc:.4f}")
    except Exception as e:
        print(f"AUC error: {e}")

    # Save model
    model_path = MODELS_DIR / "isolation_forest.pkl"
    pickle.dump(model, open(model_path, "wb"))
    print(f"\n✓ Saved: {model_path}")

    # Also save raw score stats for normalization during inference
    all_scores = model.decision_function(X_test)
    np.save(MODELS_DIR / "if_score_min.npy", np.array([all_scores.min()]))
    np.save(MODELS_DIR / "if_score_max.npy", np.array([all_scores.max()]))
    print("✓ Saved score normalization bounds")


if __name__ == "__main__":
    train()
