"""
TeleSight AI — Feature Engineering
Computes derived KPI features: signal_score, qos_score, alert_level, spectral_efficiency.
"""

import numpy as np


# ─── Thresholds (3GPP + industry standards) ──────────────────────────────────
SINR_EXCELLENT  =  20.0   # dB
SINR_GOOD       =  10.0
SINR_POOR       =   0.0
SINR_CRITICAL   =  -5.0

RSRP_EXCELLENT  = -80.0   # dBm
RSRP_GOOD       = -95.0
RSRP_POOR       = -110.0
RSRP_CRITICAL   = -120.0

RSRQ_EXCELLENT  =  -5.0   # dB
RSRQ_GOOD       = -10.0
RSRQ_POOR       = -15.0

LATENCY_5G_GOOD =  10.0   # ms
LATENCY_4G_GOOD =  30.0
LATENCY_WARN    =  100.0
LATENCY_CRIT    =  200.0

THROUGHPUT_GOOD =  50.0   # Mbps
THROUGHPUT_WARN =  10.0
THROUGHPUT_CRIT =   5.0

PACKET_LOSS_GOOD = 0.5    # %
PACKET_LOSS_WARN = 3.0
PACKET_LOSS_CRIT = 10.0

BANDWIDTH_MHZ   = 20.0    # assumed 20 MHz channel


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def compute_signal_score(rsrp: float, rsrq: float, sinr: float) -> float:
    """
    Composite signal quality score 0–100.
    Weights: SINR 50%, RSRP 35%, RSRQ 15%
    """
    # SINR component (0–100)
    if sinr >= SINR_EXCELLENT:
        sinr_score = 100.0
    elif sinr >= SINR_GOOD:
        sinr_score = 75.0 + 25.0 * (sinr - SINR_GOOD) / (SINR_EXCELLENT - SINR_GOOD)
    elif sinr >= SINR_POOR:
        sinr_score = 40.0 + 35.0 * (sinr - SINR_POOR) / (SINR_GOOD - SINR_POOR)
    elif sinr >= SINR_CRITICAL:
        sinr_score = 10.0 + 30.0 * (sinr - SINR_CRITICAL) / (SINR_POOR - SINR_CRITICAL)
    else:
        sinr_score = 0.0

    # RSRP component (0–100)
    if rsrp >= RSRP_EXCELLENT:
        rsrp_score = 100.0
    elif rsrp >= RSRP_GOOD:
        rsrp_score = 70.0 + 30.0 * (rsrp - RSRP_GOOD) / (RSRP_EXCELLENT - RSRP_GOOD)
    elif rsrp >= RSRP_POOR:
        rsrp_score = 30.0 + 40.0 * (rsrp - RSRP_POOR) / (RSRP_GOOD - RSRP_POOR)
    elif rsrp >= RSRP_CRITICAL:
        rsrp_score = 5.0 + 25.0 * (rsrp - RSRP_CRITICAL) / (RSRP_POOR - RSRP_CRITICAL)
    else:
        rsrp_score = 0.0

    # RSRQ component (0–100)
    if rsrq >= RSRQ_EXCELLENT:
        rsrq_score = 100.0
    elif rsrq >= RSRQ_GOOD:
        rsrq_score = 60.0 + 40.0 * (rsrq - RSRQ_GOOD) / (RSRQ_EXCELLENT - RSRQ_GOOD)
    elif rsrq >= RSRQ_POOR:
        rsrq_score = 20.0 + 40.0 * (rsrq - RSRQ_POOR) / (RSRQ_GOOD - RSRQ_POOR)
    else:
        rsrq_score = 0.0

    score = 0.50 * sinr_score + 0.35 * rsrp_score + 0.15 * rsrq_score
    return round(_clamp(score), 2)


def compute_qos_score(
    latency: float, jitter: float, packet_loss: float, throughput_dl: float
) -> float:
    """
    QoS degradation score 0–1 (0 = perfect, 1 = totally degraded).
    Higher = worse network quality.
    """
    # Latency penalty (0–1)
    if latency <= LATENCY_5G_GOOD:
        lat_pen = 0.0
    elif latency <= LATENCY_4G_GOOD:
        lat_pen = 0.1 * (latency - LATENCY_5G_GOOD) / (LATENCY_4G_GOOD - LATENCY_5G_GOOD)
    elif latency <= LATENCY_WARN:
        lat_pen = 0.1 + 0.3 * (latency - LATENCY_4G_GOOD) / (LATENCY_WARN - LATENCY_4G_GOOD)
    elif latency <= LATENCY_CRIT:
        lat_pen = 0.4 + 0.4 * (latency - LATENCY_WARN) / (LATENCY_CRIT - LATENCY_WARN)
    else:
        lat_pen = 1.0

    # Jitter penalty (0–1)
    jitter_pen = _clamp(jitter / 50.0, 0, 1)

    # Packet loss penalty (0–1)
    if packet_loss <= PACKET_LOSS_GOOD:
        loss_pen = 0.0
    elif packet_loss <= PACKET_LOSS_WARN:
        loss_pen = 0.2 * (packet_loss - PACKET_LOSS_GOOD) / (PACKET_LOSS_WARN - PACKET_LOSS_GOOD)
    elif packet_loss <= PACKET_LOSS_CRIT:
        loss_pen = 0.2 + 0.5 * (packet_loss - PACKET_LOSS_WARN) / (PACKET_LOSS_CRIT - PACKET_LOSS_WARN)
    else:
        loss_pen = 1.0

    # Throughput penalty (0–1)
    if throughput_dl >= THROUGHPUT_GOOD:
        thr_pen = 0.0
    elif throughput_dl >= THROUGHPUT_WARN:
        thr_pen = 0.3 * (THROUGHPUT_GOOD - throughput_dl) / (THROUGHPUT_GOOD - THROUGHPUT_WARN)
    elif throughput_dl >= THROUGHPUT_CRIT:
        thr_pen = 0.3 + 0.5 * (THROUGHPUT_WARN - throughput_dl) / (THROUGHPUT_WARN - THROUGHPUT_CRIT)
    else:
        thr_pen = 1.0

    qos = 0.40 * lat_pen + 0.10 * jitter_pen + 0.25 * loss_pen + 0.25 * thr_pen
    return round(_clamp(qos, 0, 1), 4)


def compute_alert_level(signal_score: float, qos_score: float, is_anomaly: int = 0) -> str:
    """
    Three-level alert classification.
    Returns: 'normal' | 'warning' | 'critical'
    """
    if is_anomaly == 1 or qos_score > 0.65 or signal_score < 20:
        return "critical"
    elif qos_score > 0.35 or signal_score < 45:
        return "warning"
    else:
        return "normal"


def compute_spectral_efficiency(throughput_dl_mbps: float, bandwidth_mhz: float = BANDWIDTH_MHZ) -> float:
    """
    Spectral efficiency in bits/s/Hz (Shannon capacity approximation).
    throughput_dl in Mbps, bandwidth in MHz.
    """
    if bandwidth_mhz <= 0 or throughput_dl_mbps < 0:
        return 0.0
    se = (throughput_dl_mbps * 1e6) / (bandwidth_mhz * 1e6)  # bits/s/Hz
    return round(se, 6)


def enrich_record(record: dict) -> dict:
    """
    Applies all derived features to a KPI record dict.
    Modifies in-place and returns the enriched dict.
    """
    rsrp         = float(record.get("rsrp", -95))
    rsrq         = float(record.get("rsrq", -10))
    sinr         = float(record.get("sinr", 10))
    latency      = float(record.get("latency", 20))
    jitter       = float(record.get("jitter", 2))
    packet_loss  = float(record.get("packet_loss", 0.5))
    throughput_dl = float(record.get("throughput_dl", 50))
    is_anomaly   = int(record.get("is_anomaly", 0))

    signal_score = compute_signal_score(rsrp, rsrq, sinr)
    qos_score    = compute_qos_score(latency, jitter, packet_loss, throughput_dl)
    alert_level  = compute_alert_level(signal_score, qos_score, is_anomaly)
    spectral_eff = compute_spectral_efficiency(throughput_dl)

    record["signal_score"]         = signal_score
    record["qos_score"]            = qos_score
    record["alert_level"]          = alert_level
    record["spectral_efficiency"]  = spectral_eff
    return record
