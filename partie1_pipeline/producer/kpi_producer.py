"""
TeleSight AI — Kafka KPI Producer
Reads unified_kpi_with_anomalies.csv row by row and streams to Kafka.
Simulates real-time telemetry at 0.1s per record (10 records/sec).
"""

import csv
import json
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

# ─── Config ──────────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP   = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC       = os.getenv("KAFKA_TOPIC", "telecom_kpis")
SEND_INTERVAL_SEC = float(os.getenv("SEND_INTERVAL", "0.1"))
BASE_DIR          = Path(__file__).resolve().parent.parent.parent
DATA_CSV          = BASE_DIR / "data" / "unified_kpi_with_anomalies.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PRODUCER] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def wait_for_kafka(bootstrap: str, retries: int = 30, delay: float = 3.0) -> KafkaProducer:
    """Retry until Kafka is available."""
    for attempt in range(1, retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=bootstrap,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
                max_block_ms=10000,
            )
            log.info(f"✓ Connected to Kafka at {bootstrap}")
            return producer
        except NoBrokersAvailable:
            log.warning(f"Kafka not ready (attempt {attempt}/{retries}), retrying in {delay}s...")
            time.sleep(delay)
    raise RuntimeError("Could not connect to Kafka after multiple retries")


def stream_csv(producer: KafkaProducer, csv_path: Path):
    """Stream CSV rows to Kafka in a loop."""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {csv_path}. "
            "Run producer/data_preparation.py first."
        )

    log.info(f"Streaming from: {csv_path}")
    row_count = 0
    loop_count = 0

    while True:
        loop_count += 1
        log.info(f"Starting loop #{loop_count} ...")

        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Add live timestamp (current time, not historical)
                record = {
                    "cell_id":       row.get("cell_id", "CELL_001"),
                    "timestamp":     datetime.now(timezone.utc).isoformat(),
                    "technology":    row.get("technology", "5G"),
                    "rsrp":          safe_float(row.get("rsrp")),
                    "rsrq":          safe_float(row.get("rsrq")),
                    "sinr":          safe_float(row.get("sinr")),
                    "throughput_dl": safe_float(row.get("throughput_dl")),
                    "throughput_ul": safe_float(row.get("throughput_ul")),
                    "latency":       safe_float(row.get("latency")),
                    "jitter":        safe_float(row.get("jitter")),
                    "packet_loss":   safe_float(row.get("packet_loss")),
                    "handover_label":safe_int(row.get("handover_label")),
                    "is_anomaly":    safe_int(row.get("is_anomaly")),
                    "latitude":      safe_float(row.get("latitude")),
                    "longitude":     safe_float(row.get("longitude")),
                    "prb_utilization": safe_float(row.get("prb_utilization", 50)),
                    "active_users":  safe_int(row.get("active_users", 20)),
                }

                cell_id = record["cell_id"]
                future  = producer.send(KAFKA_TOPIC, key=cell_id, value=record)

                row_count += 1
                if row_count % 500 == 0:
                    log.info(f"Sent {row_count:,} records | Last: {cell_id} | Alert: {record.get('is_anomaly')}")

                try:
                    future.get(timeout=5)
                except Exception as e:
                    log.error(f"Kafka send error: {e}")

                time.sleep(SEND_INTERVAL_SEC)

        log.info(f"Loop #{loop_count} complete — {row_count:,} total records sent. Restarting...")


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def safe_int(val, default=0):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    log.info("=== TeleSight AI — KPI Producer ===")
    producer = wait_for_kafka(KAFKA_BOOTSTRAP)
    try:
        stream_csv(producer, DATA_CSV)
    except KeyboardInterrupt:
        log.info("Producer stopped by user.")
    finally:
        producer.flush()
        producer.close()
