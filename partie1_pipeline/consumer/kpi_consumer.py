"""
TeleSight AI — Kafka KPI Consumer
Reads from Kafka topic, enriches records with derived features,
writes to PostgreSQL, and updates Redis cache.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
import redis
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from feature_engineering import enrich_record

# ─── Config ──────────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP  = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC      = os.getenv("KAFKA_TOPIC", "telecom_kpis")
KAFKA_GROUP      = os.getenv("KAFKA_GROUP", "telecom-kpi-consumer")

PG_DSN = os.getenv("DATABASE_URL",
    "host=127.0.0.1 port=5432 dbname=telesight user=telesight password=telesight123"
)
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL  = int(os.getenv("REDIS_TTL", "300"))   # 5 minutes
EVENTS_MAX = int(os.getenv("EVENTS_MAX", "200"))   # live events ring buffer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONSUMER] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─── DB helpers ──────────────────────────────────────────────────────────────
UPSERT_KPI = """
INSERT INTO kpi_records (
    cell_id, timestamp, technology, rsrp, rsrq, sinr,
    throughput_dl, throughput_ul, latency, jitter, packet_loss,
    handover_label, is_anomaly, latitude, longitude,
    signal_score, qos_score, alert_level, spectral_efficiency,
    prb_utilization, active_users
) VALUES (
    %(cell_id)s, %(timestamp)s, %(technology)s, %(rsrp)s, %(rsrq)s, %(sinr)s,
    %(throughput_dl)s, %(throughput_ul)s, %(latency)s, %(jitter)s, %(packet_loss)s,
    %(handover_label)s, %(is_anomaly)s, %(latitude)s, %(longitude)s,
    %(signal_score)s, %(qos_score)s, %(alert_level)s, %(spectral_efficiency)s,
    %(prb_utilization)s, %(active_users)s
);
"""

UPSERT_LATEST = """
INSERT INTO cell_latest (
    cell_id, technology, rsrp, rsrq, sinr,
    throughput_dl, throughput_ul, latency, jitter, packet_loss,
    handover_label, is_anomaly, latitude, longitude,
    signal_score, qos_score, alert_level, spectral_efficiency,
    prb_utilization, active_users, last_updated
) VALUES (
    %(cell_id)s, %(technology)s, %(rsrp)s, %(rsrq)s, %(sinr)s,
    %(throughput_dl)s, %(throughput_ul)s, %(latency)s, %(jitter)s, %(packet_loss)s,
    %(handover_label)s, %(is_anomaly)s, %(latitude)s, %(longitude)s,
    %(signal_score)s, %(qos_score)s, %(alert_level)s, %(spectral_efficiency)s,
    %(prb_utilization)s, %(active_users)s, NOW()
) ON CONFLICT (cell_id) DO UPDATE SET
    technology=EXCLUDED.technology, rsrp=EXCLUDED.rsrp, rsrq=EXCLUDED.rsrq,
    sinr=EXCLUDED.sinr, throughput_dl=EXCLUDED.throughput_dl, throughput_ul=EXCLUDED.throughput_ul,
    latency=EXCLUDED.latency, jitter=EXCLUDED.jitter, packet_loss=EXCLUDED.packet_loss,
    handover_label=EXCLUDED.handover_label, is_anomaly=EXCLUDED.is_anomaly,
    latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude,
    signal_score=EXCLUDED.signal_score, qos_score=EXCLUDED.qos_score,
    alert_level=EXCLUDED.alert_level, spectral_efficiency=EXCLUDED.spectral_efficiency,
    prb_utilization=EXCLUDED.prb_utilization, active_users=EXCLUDED.active_users,
    last_updated=NOW();
"""


def wait_for_kafka(bootstrap, retries=30, delay=3.0):
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=bootstrap,
                group_id=KAFKA_GROUP,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
                max_poll_records=50,
                session_timeout_ms=30000,
            )
            log.info(f"✓ Connected to Kafka at {bootstrap}")
            return consumer
        except NoBrokersAvailable:
            log.warning(f"Kafka not ready (attempt {attempt}/{retries}), retrying in {delay}s...")
            time.sleep(delay)
    raise RuntimeError("Could not connect to Kafka")


def wait_for_postgres(dsn, retries=30, delay=3.0):
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(dsn)
            log.info("✓ Connected to PostgreSQL")
            return conn
        except Exception as e:
            log.warning(f"Postgres not ready (attempt {attempt}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to PostgreSQL")


def connect_redis():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    log.info(f"✓ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    return r


def write_to_postgres(conn, record: dict):
    with conn.cursor() as cur:
        cur.execute(UPSERT_KPI, record)
        cur.execute(UPSERT_LATEST, record)
    conn.commit()


def update_redis(r: redis.Redis, record: dict):
    cell_id = record["cell_id"]

    # 1. Latest state per cell
    key = f"cell:latest:{cell_id}"
    r.hset(key, mapping={k: str(v) for k, v in record.items()})
    r.expire(key, REDIS_TTL)

    # 2. Live events ring buffer (newest-first)
    event_key = "events:live"
    r.lpush(event_key, json.dumps(record, default=str))
    r.ltrim(event_key, 0, EVENTS_MAX - 1)

    # 3. Critical anomaly set
    if record.get("alert_level") == "critical":
        r.sadd("anomalies:active", cell_id)
        r.expire("anomalies:active", 300)
    elif record.get("alert_level") == "normal":
        r.srem("anomalies:active", cell_id)


def prepare_record(raw: dict) -> dict:
    """Normalize and enrich a raw Kafka message."""
    record = {
        "cell_id":       str(raw.get("cell_id", "UNKNOWN")),
        "timestamp":     raw.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "technology":    str(raw.get("technology", "5G")),
        "rsrp":          float(raw.get("rsrp") or -95),
        "rsrq":          float(raw.get("rsrq") or -10),
        "sinr":          float(raw.get("sinr") or 10),
        "throughput_dl": float(raw.get("throughput_dl") or 50),
        "throughput_ul": float(raw.get("throughput_ul") or 20),
        "latency":       float(raw.get("latency") or 20),
        "jitter":        float(raw.get("jitter") or 2),
        "packet_loss":   float(raw.get("packet_loss") or 0.5),
        "handover_label":int(raw.get("handover_label") or 0),
        "is_anomaly":    int(raw.get("is_anomaly") or 0),
        "latitude":      float(raw.get("latitude") or 36.82),
        "longitude":     float(raw.get("longitude") or 10.17),
        "prb_utilization": float(raw.get("prb_utilization") or 50),
        "active_users":  int(raw.get("active_users") or 20),
    }
    return enrich_record(record)


def main():
    log.info("=== TeleSight AI — KPI Consumer ===")

    consumer = wait_for_kafka(KAFKA_BOOTSTRAP)
    pg_conn  = wait_for_postgres(PG_DSN)
    r        = connect_redis()

    processed = 0
    errors    = 0

    log.info(f"Listening on topic '{KAFKA_TOPIC}' (group '{KAFKA_GROUP}')...")

    for message in consumer:
        try:
            raw    = message.value
            record = prepare_record(raw)

            write_to_postgres(pg_conn, record)
            update_redis(r, record)

            processed += 1
            if processed % 100 == 0:
                log.info(
                    f"Processed {processed:,} | Errors {errors} | "
                    f"Last: {record['cell_id']} [{record['alert_level']}] "
                    f"SINR={record['sinr']:.1f}dB LAT={record['latency']:.0f}ms"
                )

        except psycopg2.OperationalError as e:
            log.error(f"Postgres connection lost: {e}, reconnecting...")
            try:
                pg_conn = wait_for_postgres(PG_DSN, retries=5)
            except Exception:
                log.critical("Cannot reconnect to Postgres, exiting.")
                break
        except Exception as e:
            errors += 1
            log.error(f"Error processing message: {e} | raw={message.value}")


if __name__ == "__main__":
    main()
