"""
TeleSight AI — Train XGBoost Models
Two classifiers: anomaly detection + handover prediction.
"""

import pickle
import sys
import importlib.util
from pathlib import Path
import numpy as np
from sklearn.metrics import classification_report, roc_auc_score, f1_score
import xgboost as xgb

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


def train_xgboost(
    X_train, X_test, y_train, y_test,
    model_name: str, pos_label_name: str = "anomaly"
):
    """Train a single XGBoost binary classifier."""
    n_pos = y_train.sum()
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / (n_pos + 1e-6)
    print(f"\n  Positives: {n_pos} | Negatives: {n_neg} | scale_pos_weight: {scale_pos_weight:.2f}")

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="aucpr",
        early_stopping_rounds=20,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # Evaluate
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred  = (y_proba >= 0.5).astype(int)
    f1   = f1_score(y_test, y_pred, zero_division=0)
    auc  = roc_auc_score(y_test, y_proba)
    print(f"\n  {model_name} Results:")
    print(f"  F1-Score: {f1:.4f} | ROC-AUC: {auc:.4f}")
    print(f"  Best iteration: {model.best_iteration}")
    print(classification_report(y_test, y_pred, target_names=["normal", pos_label_name]))

    # Feature importance
    importances = model.feature_importances_
    feat_names  = pickle.load(open(MODELS_DIR / "feature_cols.pkl", "rb"))
    top_feats   = sorted(zip(feat_names, importances), key=lambda x: -x[1])[:5]
    print(f"  Top 5 features:")
    for fname, imp in top_feats:
        print(f"    {fname}: {imp:.4f}")

    return model


def main():
    print("=== TeleSight AI — XGBoost Training ===\n")
    df = load_and_engineer()
    X_train, X_test, ya_train, ya_test, yh_train, yh_test, scaler, _ = prepare_splits(df)

    # ─── Model 1: Anomaly Detection ─────────────────────────────────────────
    print("[3/4] Training XGBoost — Anomaly Detection...")
    model_anomaly = train_xgboost(
        X_train, X_test, ya_train, ya_test,
        model_name="Anomaly Classifier", pos_label_name="anomaly"
    )
    pickle.dump(model_anomaly, open(MODELS_DIR / "xgboost_anomaly.pkl", "wb"))
    print(f"  ✓ Saved: xgboost_anomaly.pkl")

    # ─── Model 2: Handover Prediction ───────────────────────────────────────
    print("\n[4/4] Training XGBoost — Handover Prediction...")
    model_handover = train_xgboost(
        X_train, X_test, yh_train, yh_test,
        model_name="Handover Classifier", pos_label_name="handover"
    )
    pickle.dump(model_handover, open(MODELS_DIR / "xgboost_handover.pkl", "wb"))
    print(f"  ✓ Saved: xgboost_handover.pkl")

    print("\n✓ XGBoost training complete!")


if __name__ == "__main__":
    main()
