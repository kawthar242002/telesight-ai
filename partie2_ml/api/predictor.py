"""
TeleSight AI — ML Predictor (Part 2)
Loads all trained models and performs ensemble anomaly scoring.
"""

import pickle
from pathlib import Path
from typing import Optional
import numpy as np
import torch
import torch.nn as nn
import httpx

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


# ─── LSTM Model (same class as in training script) ───────────────────────────
class AttentionLayer(nn.Module):
    def __init__(self, hidden_size):
        super().__init__()
        self.attention = nn.Linear(hidden_size, 1)

    def forward(self, lstm_out):
        weights = torch.softmax(self.attention(lstm_out), dim=1)
        return (weights * lstm_out).sum(dim=1)


class LSTMWithAttention(nn.Module):
    def __init__(self, n_features, hidden_size, n_layers, dropout):
        super().__init__()
        self.lstm      = nn.LSTM(n_features, hidden_size, n_layers,
                                 batch_first=True,
                                 dropout=dropout if n_layers > 1 else 0.0)
        self.attention = AttentionLayer(hidden_size)
        self.dropout   = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 32), nn.ReLU(),
            nn.Dropout(dropout), nn.Linear(32, 1), nn.Identity(),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        ctx    = self.dropout(self.attention(out))
        return self.classifier(ctx).squeeze(1)


class TelecomPredictor:
    """
    Ensemble predictor combining:
    - Isolation Forest (unsupervised)
    - XGBoost (supervised anomaly + handover)
    - LSTM with Attention (time-series)

    Final anomaly_score = 0.45 * xgb_proba + 0.35 * if_norm + 0.20 * lstm_proba
    Thresholds: score >= 0.7 → critical, >= 0.4 → warning
    """

    THRESHOLD_CRITICAL = 0.7
    THRESHOLD_WARNING  = 0.4

    def __init__(self):
        self._load_models()

    def _load_models(self):
        print("Loading ML models...")
        # Scaler + feature list
        self.scaler      = pickle.load(open(MODELS_DIR / "scaler.pkl", "rb"))
        self.feature_cols = pickle.load(open(MODELS_DIR / "feature_cols.pkl", "rb"))

        # Isolation Forest
        self.iso_forest  = pickle.load(open(MODELS_DIR / "isolation_forest.pkl", "rb"))
        self.if_score_min = float(np.load(MODELS_DIR / "if_score_min.npy")[0])
        self.if_score_max = float(np.load(MODELS_DIR / "if_score_max.npy")[0])

        # XGBoost
        self.xgb_anomaly  = pickle.load(open(MODELS_DIR / "xgboost_anomaly.pkl", "rb"))
        self.xgb_handover = pickle.load(open(MODELS_DIR / "xgboost_handover.pkl", "rb"))

        # LSTM
        self.lstm_config = pickle.load(open(MODELS_DIR / "lstm_config.pkl", "rb"))
        self.ts_means    = np.load(MODELS_DIR / "ts_means.npy")
        self.ts_stds     = np.load(MODELS_DIR / "ts_stds.npy")
        self.lstm_model  = self._load_lstm()

        # Cell sequence buffers for LSTM (last 20 records per cell)
        self._cell_buffers: dict = {}

        print("✓ All models loaded successfully")

    def _load_lstm(self) -> Optional[LSTMWithAttention]:
        cfg  = self.lstm_config
        model = LSTMWithAttention(
            n_features=cfg["n_features"],
            hidden_size=cfg["hidden_size"],
            n_layers=cfg["n_layers"],
            dropout=cfg["dropout"],
        )
        weights_path = MODELS_DIR / "lstm_best.pt"
        if weights_path.exists():
            model.load_state_dict(torch.load(weights_path, map_location="cpu"))
            model.eval()
            return model
        print("⚠ lstm_best.pt not found, LSTM disabled")
        return None

    def _extract_features(self, record: dict) -> np.ndarray:
        """Build the 17-feature vector from a KPI record dict."""
        rsrp          = float(record.get("rsrp", -95))
        rsrq          = float(record.get("rsrq", -10))
        sinr          = float(record.get("sinr", 10))
        throughput_dl = float(record.get("throughput_dl", 50))
        throughput_ul = float(record.get("throughput_ul", 20))
        latency       = float(record.get("latency", 20))
        jitter        = float(record.get("jitter", 2))
        packet_loss   = float(record.get("packet_loss", 0.5))

        row = {
            "rsrp": rsrp, "rsrq": rsrq, "sinr": sinr,
            "throughput_dl": throughput_dl, "throughput_ul": throughput_ul,
            "latency": latency, "jitter": jitter, "packet_loss": packet_loss,
            "sinr_rsrp_ratio":    sinr / (abs(rsrp) + 1e-6),
            "signal_degradation": np.clip(rsrp + sinr, -50, 30),
            "qos_composite_score": (
                0.4 * min(latency/500, 1) + 0.25 * min(packet_loss/100, 1) +
                0.25 * (1 - min(throughput_dl/500, 1)) + 0.10 * min(jitter/200, 1)
            ),
            "latency_high":    int(latency > 100),
            "throughput_low":  int(throughput_dl < 10),
            "packet_loss_high":int(packet_loss > 3),
            "rsrp_normalized": (rsrp + 140) / 70,
            "throughput_ratio":throughput_dl / (throughput_ul + 1e-6),
            "sinr_squared":    sinr ** 2,
        }
        return np.array([row[f] for f in self.feature_cols], dtype=np.float32)

    def _normalize_if_score(self, raw_score: float) -> float:
        """Normalize IF score to [0,1] where 1 = most anomalous."""
        rng   = self.if_score_max - self.if_score_min
        if rng == 0:
            return 0.5
        normed = (raw_score - self.if_score_min) / rng
        return float(np.clip(1.0 - normed, 0.0, 1.0))  # invert: low score = anomaly

    def _lstm_predict(self, cell_id: str, record: dict) -> float:
        """LSTM prediction using per-cell rolling buffer."""
        if self.lstm_model is None:
            return 0.0

        cfg_feats = self.lstm_config["features"]
        seq_len   = self.lstm_config["seq_len"]

        vec = np.array([float(record.get(f, 0)) for f in cfg_feats], dtype=np.float32)
        vec = (vec - self.ts_means) / (self.ts_stds + 1e-8)

        buf = self._cell_buffers.get(cell_id, [])
        buf.append(vec)
        if len(buf) > seq_len:
            buf = buf[-seq_len:]
        self._cell_buffers[cell_id] = buf

        if len(buf) < seq_len:
            return 0.0  # not enough history yet

        x   = torch.tensor(np.array(buf), dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            logit  = self.lstm_model(x)
            proba  = torch.sigmoid(logit).item()
        return proba

    def predict(self, record: dict) -> dict:
        """
        Full ensemble prediction for a single KPI record.
        Returns the structured prediction dict.
        """
        cell_id = record.get("cell_id", "UNKNOWN")

        # 1. Feature extraction + scaling
        features_raw    = self._extract_features(record)
        features_scaled = self.scaler.transform(features_raw.reshape(1, -1))

        # 2. Isolation Forest
        if_raw_score = self.iso_forest.decision_function(features_scaled)[0]
        if_norm      = self._normalize_if_score(if_raw_score)

        # 3. XGBoost anomaly
        xgb_anomaly_proba  = float(self.xgb_anomaly.predict_proba(features_scaled)[0, 1])

        # 4. XGBoost handover
        xgb_handover_proba = float(self.xgb_handover.predict_proba(features_scaled)[0, 1])

        # 5. LSTM
        lstm_proba = self._lstm_predict(cell_id, record)

        # 6. Ensemble
        if self.lstm_model is not None and lstm_proba > 0:
            anomaly_score = 0.45 * xgb_anomaly_proba + 0.35 * if_norm + 0.20 * lstm_proba
        else:
            anomaly_score = 0.55 * xgb_anomaly_proba + 0.45 * if_norm

        anomaly_score = round(float(np.clip(anomaly_score, 0, 1)), 4)

        # 7. Alert level
        if anomaly_score >= self.THRESHOLD_CRITICAL:
            alert_level = "critical"
            is_anomaly  = 1
        elif anomaly_score >= self.THRESHOLD_WARNING:
            alert_level = "warning"
            is_anomaly  = 1
        else:
            alert_level = "normal"
            is_anomaly  = 0

        # 8. Human-readable explanation
        explanation = self._build_explanation(record, anomaly_score)

        return {
            "cell_id":                cell_id,
            "is_anomaly":             is_anomaly,
            "anomaly_score":          anomaly_score,
            "isolation_forest_score": round(float(if_raw_score), 4),
            "xgboost_anomaly_proba":  round(xgb_anomaly_proba, 4),
            "xgboost_handover_proba": round(xgb_handover_proba, 4),
            "lstm_proba":             round(lstm_proba, 4),
            "handover_probability":   round(xgb_handover_proba, 4),
            "alert_level":            alert_level,
            "explanation":            explanation,
        }

    def predict_batch(self, records: list) -> list:
        return [self.predict(r) for r in records]

    def _build_explanation(self, record: dict, score: float) -> str:
        issues = []
        sinr          = float(record.get("sinr", 10))
        latency       = float(record.get("latency", 20))
        throughput_dl = float(record.get("throughput_dl", 50))
        packet_loss   = float(record.get("packet_loss", 0.5))
        rsrp          = float(record.get("rsrp", -95))

        if sinr < 0:
            issues.append(f"SINR dégradé ({sinr:.1f} dB)")
        if latency > 100:
            issues.append(f"Latence élevée ({latency:.0f} ms)")
        if throughput_dl < 10:
            issues.append(f"Débit DL faible ({throughput_dl:.1f} Mbps)")
        if packet_loss > 3:
            issues.append(f"Perte de paquets ({packet_loss:.1f}%)")
        if rsrp < -110:
            issues.append(f"Signal faible RSRP ({rsrp:.0f} dBm)")

        if not issues:
            return f"Réseau nominal. Score: {score:.2f}."
        return f"Anomalies détectées : {', '.join(issues)}. Score global: {score:.2f}."
