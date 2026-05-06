"""
TeleSight AI — ML Feature Engineering (Part 2)
Loads unified CSV and builds the 17-feature matrix for model training.
"""

import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
DATA_CSV   = BASE_DIR / "data" / "unified_kpi_with_anomalies.csv"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


def load_and_engineer(csv_path: Path = DATA_CSV) -> pd.DataFrame:
    print(f"[1/3] Loading data from {csv_path}...")
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    # ─── Raw features ───────────────────────────────────────────────────────
    df["rsrp"]         = pd.to_numeric(df["rsrp"], errors="coerce").fillna(-95)
    df["rsrq"]         = pd.to_numeric(df["rsrq"], errors="coerce").fillna(-10)
    df["sinr"]         = pd.to_numeric(df["sinr"], errors="coerce").fillna(10)
    df["throughput_dl"]= pd.to_numeric(df["throughput_dl"], errors="coerce").fillna(50)
    df["throughput_ul"]= pd.to_numeric(df["throughput_ul"], errors="coerce").fillna(20)
    df["latency"]      = pd.to_numeric(df["latency"], errors="coerce").fillna(20)
    df["jitter"]       = pd.to_numeric(df["jitter"], errors="coerce").fillna(2)
    df["packet_loss"]  = pd.to_numeric(df["packet_loss"], errors="coerce").fillna(0.5)

    # ─── Derived features (9 more) ──────────────────────────────────────────
    df["sinr_rsrp_ratio"]       = df["sinr"] / (df["rsrp"].abs() + 1e-6)
    df["signal_degradation"]    = (df["rsrp"] + df["sinr"]).clip(-50, 30)
    df["qos_composite_score"]   = (
        0.4 * df["latency"].clip(0,500)/500
        + 0.25 * df["packet_loss"].clip(0,100)/100
        + 0.25 * (1 - df["throughput_dl"].clip(0,500)/500)
        + 0.10 * df["jitter"].clip(0,200)/200
    )
    df["latency_high"]          = (df["latency"] > 100).astype(int)
    df["throughput_low"]        = (df["throughput_dl"] < 10).astype(int)
    df["packet_loss_high"]      = (df["packet_loss"] > 3).astype(int)
    df["rsrp_normalized"]       = (df["rsrp"] + 140) / 70   # [-140,0] → [0,2]
    df["throughput_ratio"]      = df["throughput_dl"] / (df["throughput_ul"] + 1e-6)
    df["sinr_squared"]          = df["sinr"] ** 2

    print(f"[1/3] ✓ {len(df)} rows, {df['cell_id'].nunique()} cells")
    print(f"      Anomaly rate: {df['is_anomaly'].mean()*100:.1f}%")
    return df


FEATURE_COLS = [
    "rsrp", "rsrq", "sinr", "throughput_dl", "throughput_ul",
    "latency", "jitter", "packet_loss",
    "sinr_rsrp_ratio", "signal_degradation", "qos_composite_score",
    "latency_high", "throughput_low", "packet_loss_high",
    "rsrp_normalized", "throughput_ratio", "sinr_squared",
]


def prepare_splits(df: pd.DataFrame):
    print("[2/3] Preparing train/test splits...")
    X = df[FEATURE_COLS].values
    y_anomaly   = df["is_anomaly"].values
    y_handover  = df["handover_label"].fillna(0).astype(int).values

    X_train, X_test, ya_train, ya_test, yh_train, yh_test = train_test_split(
        X, y_anomaly, y_handover,
        test_size=0.2, random_state=42, stratify=y_anomaly
    )

    scaler  = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test  = scaler.transform(X_test)

    print(f"[2/3] ✓ Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"      Anomalies train: {ya_train.sum()} | test: {ya_test.sum()}")

    # Save artifacts
    pickle.dump(scaler,       open(MODELS_DIR / "scaler.pkl", "wb"))
    pickle.dump(FEATURE_COLS, open(MODELS_DIR / "feature_cols.pkl", "wb"))
    print(f"[2/3] ✓ Saved scaler.pkl + feature_cols.pkl")

    return X_train, X_test, ya_train, ya_test, yh_train, yh_test, scaler, df


if __name__ == "__main__":
    print("=== TeleSight AI — Feature Engineering ===\n")
    df = load_and_engineer()
    X_train, X_test, ya_train, ya_test, yh_train, yh_test, scaler, df_full = prepare_splits(df)
    print("\n[3/3] Feature summary:")
    for i, col in enumerate(FEATURE_COLS):
        print(f"  [{i+1:2d}] {col}")
    print("\n✓ Feature engineering complete. Run training scripts next.")
