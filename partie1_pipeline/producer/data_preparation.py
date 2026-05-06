"""
TeleSight AI — Data Preparation
Merges real datasets into unified_kpi_with_anomalies.csv
Handles the actual column names from the provided datasets.
"""

import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent.parent
DATA_DIR   = BASE_DIR / "data"
OUTPUT_CSV = DATA_DIR / "unified_kpi_with_anomalies.csv"

DATASET_5G        = BASE_DIR / "dataset1_5g_network_kpi.csv"
DATASET_NETWORK   = BASE_DIR / "network_logs_1.csv"
DATASET_PROCESSED = BASE_DIR / "ds1_processed.csv"
DATASET_TELECOM   = BASE_DIR / "data.csv"

# ─── GPS réelles par cellule (villes tunisiennes) ─────────────────────────────
CELL_GPS = {
    "CELL_001": (36.8190, 10.1658),  # Tunis centre
    "CELL_002": (36.7255, 10.2067),  # Ben Arous
    "CELL_003": (36.8500, 10.2833),  # Ariana
    "CELL_004": (36.8062, 10.1777),  # Tunis Medina
    "CELL_005": (36.8441, 10.2041),  # La Marsa
    "CELL_006": (33.8869,  9.5375),  # Gafsa
    "CELL_007": (34.7406, 10.7603),  # Sfax
    "CELL_008": (35.6757, 10.0963),  # Sousse
    "CELL_009": (36.0450,  9.3700),  # Siliana
    "CELL_010": (33.5130,  9.0600),  # Tozeur
    "CELL_011": (36.9000, 10.3300),  # Bizerte
    "CELL_012": (36.7500, 10.0900),  # Manouba
    "CELL_013": (36.8000, 10.1500),  # Tunis Est
    "CELL_014": (35.7640, 10.8020),  # Monastir
    "CELL_015": (36.4091,  8.7756),  # Jendouba
    "CELL_016": (37.2735,  9.8736),  # Bizerte Nord
    "CELL_017": (36.9023, 10.2124),  # Carthage
    "CELL_018": (35.0000,  9.3600),  # Kasserine
    "CELL_019": (36.8670, 10.3180),  # Sidi Bou Said
    "CELL_020": (33.8815, 10.0982),  # Gabes
}


def get_gps(cell_id: str):
    """Retourne les coordonnées GPS d'une cellule — fixes et reproductibles."""
    if cell_id in CELL_GPS:
        return CELL_GPS[cell_id]
    # Coordonnées déterministes pour les cellules inconnues
    rng = np.random.default_rng(abs(hash(cell_id)) % (2**32))
    lat = rng.uniform(33.0, 37.5)
    lon = rng.uniform(8.0, 11.5)
    return (round(lat, 4), round(lon, 4))


def apply_gps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applique les coordonnées GPS correctes par cell_id.
    TOUJOURS depuis CELL_GPS — ignore les valeurs existantes dans le CSV.
    """
    coords = df["cell_id"].apply(get_gps)
    df["latitude"]  = coords.apply(lambda x: x[0])
    df["longitude"] = coords.apply(lambda x: x[1])
    return df


def load_5g_kpi() -> pd.DataFrame:
    """Load dataset1_5g_network_kpi.csv — the primary 5G dataset."""
    df = pd.read_csv(DATASET_5G, parse_dates=["timestamp"])
    df = df.rename(columns={
        "throughput_mbps":     "throughput_dl",
        "latency_ms":          "latency",
        "packet_loss_pct":     "packet_loss",
        "rsrp_dbm":            "rsrp",
        "rsrq_db":             "rsrq",
        "handover_count":      "handover_label",
        "prb_utilization_pct": "prb_utilization",
    })
    df["technology"]     = "5G"
    df["throughput_ul"]  = df["throughput_dl"] * np.random.uniform(0.3, 0.5, len(df))
    df["sinr"]           = np.random.uniform(-5, 30, len(df))
    df["jitter"]         = df["latency"] * np.random.uniform(0.05, 0.2, len(df))
    if "rsrq" not in df.columns:
        df["rsrq"]       = np.random.uniform(-15, -3, len(df))
    df["handover_label"] = (df["handover_label"] > 0).astype(int)
    df["is_anomaly"]     = 0
    df["active_users"]   = np.random.randint(5, 60, len(df))
    df["sla_compliant"]  = 1
    df["prb_utilization"] = df.get("prb_utilization", pd.Series(np.random.uniform(20, 80, len(df))))
    print(f"  ✓ 5G KPI dataset: {len(df)} rows, {df['cell_id'].nunique()} cells")
    return df


def load_network_logs() -> pd.DataFrame:
    """Load network_logs_1.csv — 4G LTE drive test data."""
    df = pd.read_csv(DATASET_NETWORK)
    for col in ["RSRP", "RSRQ", "SINR", "Downlink(Mbps)", "Uplink(Mbps)", "Velocity(km/h)"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.extract(r"([-\d.]+)").astype(float)

    df = df.rename(columns={
        "Timestamp":      "timestamp",
        "DeviceID":       "cell_id",
        "NetworkType":    "technology",
        "RSRP":           "rsrp",
        "RSRQ":           "rsrq",
        "SINR":           "sinr",
        "Downlink(Mbps)": "throughput_dl",
        "Uplink(Mbps)":   "throughput_ul",
    })
    # Supprimer les colonnes GPS du CSV si elles existent (on va les remplacer)
    df.drop(columns=["Latitude", "Longitude"], errors="ignore", inplace=True)

    df["timestamp"]      = pd.to_datetime(df["timestamp"], errors="coerce")
    df["technology"]     = df["technology"].str.extract(r"(\dG)").fillna("4G")
    df["latency"]        = np.random.uniform(10, 60, len(df))
    df["jitter"]         = np.random.uniform(1, 10, len(df))
    df["packet_loss"]    = np.random.uniform(0, 3, len(df))
    df["handover_label"] = 0
    df["is_anomaly"]     = 0
    df["prb_utilization"] = np.random.uniform(20, 80, len(df))
    df["active_users"]   = np.random.randint(5, 50, len(df))
    df["sla_compliant"]  = 1

    # Remap DeviceID → CELL_XXX style
    uids   = df["cell_id"].unique()
    id_map = {uid: f"CELL_{str(i+1).zfill(3)}" for i, uid in enumerate(uids)}
    df["cell_id"] = df["cell_id"].map(id_map)
    print(f"  ✓ Network logs (4G): {len(df)} rows, {df['cell_id'].nunique()} cells")
    return df


def unify_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all required columns exist with correct types."""
    REQUIRED = {
        "cell_id":          "CELL_001",
        "timestamp":        pd.Timestamp.now(),
        "technology":       "5G",
        "rsrp":             -95.0,
        "rsrq":             -10.0,
        "sinr":             10.0,
        "throughput_dl":    50.0,
        "throughput_ul":    20.0,
        "latency":          20.0,
        "jitter":           2.0,
        "packet_loss":      0.5,
        "handover_label":   0,
        "is_anomaly":       0,
        "prb_utilization":  50.0,
        "active_users":     20,
        "sla_compliant":    1,
    }
    for col, default in REQUIRED.items():
        if col not in df.columns:
            df[col] = default

    # Type enforcement
    df["timestamp"]      = pd.to_datetime(df["timestamp"], errors="coerce")
    df["handover_label"] = df["handover_label"].fillna(0).astype(int)
    df["is_anomaly"]     = df["is_anomaly"].fillna(0).astype(int)
    df = df.dropna(subset=["timestamp", "rsrp", "throughput_dl"])

    # TOUJOURS appliquer les GPS depuis CELL_GPS (pas depuis le CSV)
    df = apply_gps(df)

    return df


def inject_anomalies(df: pd.DataFrame, rate: float = 0.05) -> pd.DataFrame:
    """Inject synthetic anomalies (5%) with extreme KPI values."""
    n_anomalies = int(len(df) * rate)
    indices     = np.random.choice(df.index, size=n_anomalies, replace=False)

    # Type 1: Extreme SINR degradation
    n1   = n_anomalies // 3
    idx1 = indices[:n1]
    df.loc[idx1, "sinr"] = np.random.uniform(-10, -3, n1)
    df.loc[idx1, "rsrp"] = np.random.uniform(-130, -110, n1)

    # Type 2: High latency + packet loss
    n2   = n_anomalies // 3
    idx2 = indices[n1:n1+n2]
    df.loc[idx2, "latency"]     = np.random.uniform(200, 500, n2)
    df.loc[idx2, "packet_loss"] = np.random.uniform(10, 30, n2)
    df.loc[idx2, "jitter"]      = np.random.uniform(50, 150, n2)

    # Type 3: Very low throughput
    idx3 = indices[n1+n2:]
    df.loc[idx3, "throughput_dl"] = np.random.uniform(0.5, 5, len(idx3))
    df.loc[idx3, "throughput_ul"] = np.random.uniform(0.1, 2, len(idx3))

    df.loc[indices, "is_anomaly"] = 1
    print(f"  ✓ Injected {n_anomalies} synthetic anomalies ({rate*100:.0f}%)")
    return df


def generate_synthetic(n_cells=20, n_rows=50000) -> pd.DataFrame:
    """Fallback: generate realistic synthetic 5G/4G KPI data."""
    np.random.seed(42)
    cell_ids = [f"CELL_{str(i+1).zfill(3)}" for i in range(n_cells)]
    rows = []
    start = pd.Timestamp("2024-01-01")
    for i in range(n_rows):
        cell = np.random.choice(cell_ids)
        ts   = start + pd.Timedelta(seconds=i * 10)
        rows.append({
            "cell_id":        cell,
            "timestamp":      ts,
            "technology":     np.random.choice(["4G", "5G"], p=[0.4, 0.6]),
            "rsrp":           np.random.uniform(-110, -70),
            "rsrq":           np.random.uniform(-15, -3),
            "sinr":           np.random.uniform(-5, 30),
            "throughput_dl":  np.random.uniform(10, 200),
            "throughput_ul":  np.random.uniform(5, 80),
            "latency":        np.random.uniform(5, 50),
            "jitter":         np.random.uniform(1, 10),
            "packet_loss":    np.random.uniform(0, 2),
            "handover_label": int(np.random.random() < 0.15),
            "is_anomaly":     0,
            "prb_utilization": np.random.uniform(20, 85),
            "active_users":   np.random.randint(5, 60),
            "sla_compliant":  1,
        })
    df = pd.DataFrame(rows)
    print(f"  ✓ Generated {len(df)} synthetic rows")
    return df


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dfs = []

    print("[1/4] Loading datasets...")

    if DATASET_5G.exists():
        try:
            dfs.append(load_5g_kpi())
        except Exception as e:
            print(f"  ⚠ 5G dataset error: {e}")
    else:
        print(f"  ⚠ {DATASET_5G.name} not found, skipping")

    if DATASET_NETWORK.exists():
        try:
            dfs.append(load_network_logs())
        except Exception as e:
            print(f"  ⚠ Network logs error: {e}")
    else:
        print(f"  ⚠ {DATASET_NETWORK.name} not found, skipping")

    if not dfs:
        print("  ⚠ No real datasets found — generating synthetic data")
        dfs.append(generate_synthetic())

    print("\n[2/4] Merging datasets...")
    unified = pd.concat(dfs, ignore_index=True)
    unified = unify_schema(unified)
    unified = unified.sort_values("timestamp").reset_index(drop=True)

    COLS = [
        "cell_id", "timestamp", "technology", "rsrp", "rsrq", "sinr",
        "throughput_dl", "throughput_ul", "latency", "jitter", "packet_loss",
        "handover_label", "is_anomaly", "latitude", "longitude",
        "prb_utilization", "active_users", "sla_compliant",
    ]
    unified = unified[[c for c in COLS if c in unified.columns]]
    print(f"  ✓ Merged: {len(unified)} rows, {unified['cell_id'].nunique()} cells")

    print("\n[3/4] Injecting synthetic anomalies...")
    unified = inject_anomalies(unified, rate=0.05)

    print(f"\n[4/4] Saving to {OUTPUT_CSV}...")
    unified.to_csv(OUTPUT_CSV, index=False)
    print(f"  ✓ Done! {len(unified)} rows saved")

    print(f"\n=== Dataset Statistics ===")
    print(f"  Total rows:   {len(unified):,}")
    print(f"  Total cells:  {unified['cell_id'].nunique()}")
    print(f"  Technologies: {unified['technology'].value_counts().to_dict()}")
    print(f"  Anomalies:    {unified['is_anomaly'].sum():,} ({unified['is_anomaly'].mean()*100:.1f}%)")
    print(f"  GPS sample:")
    for cell_id, group in unified.groupby("cell_id").first()[["latitude","longitude"]].head(5).iterrows():
        print(f"    {cell_id}: ({group.latitude}, {group.longitude})")
    return unified


if __name__ == "__main__":
    print("=== TeleSight AI — Data Preparation ===\n")
    main()