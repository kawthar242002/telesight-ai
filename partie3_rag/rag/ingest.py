"""
TeleSight AI — RAG Ingestion Pipeline (Part 3)
Converts KPI records + telecom docs into ChromaDB vector store.
Re-runs every 30 minutes to stay fresh.
"""

import os
import time
import logging
import requests
from pathlib import Path
from datetime import datetime

import httpx
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

# Charger le .env depuis partie3_rag/ (indépendamment du cwd)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [INGEST] %(message)s")

# ─── Config ──────────────────────────────────────────────────────────────────
P1_URL      = os.getenv("P1_URL", "http://localhost:8000")
CHROMA_DIR  = Path(__file__).resolve().parent.parent / "chroma_db"
COLLECTION  = "telesight_knowledge"
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")  # local sentence-transformer

# ─── ChromaDB Client ─────────────────────────────────────────────────────────
def get_chroma_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
    collection = client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


# ─── KPI Records → Text Chunks ───────────────────────────────────────────────
def kpi_to_text(record: dict) -> str:
    """Convert a KPI record dict to a descriptive French text chunk."""
    cell_id   = record.get("cell_id", "?")
    tech      = record.get("technology", "5G")
    ts        = record.get("last_updated") or record.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        time_str = dt.strftime("%Hh%M")
    except Exception:
        time_str = str(ts)[:16]

    sinr      = record.get("sinr", 0)
    rsrp      = record.get("rsrp", -95)
    latency   = record.get("latency", 20)
    thr_dl    = record.get("throughput_dl", 50)
    thr_ul    = record.get("throughput_ul", 20)
    pkt_loss  = record.get("packet_loss", 0.5)
    jitter    = record.get("jitter", 2)
    alert     = record.get("alert_level", "normal")
    sig_score = record.get("signal_score", 70)
    qos_score = record.get("qos_score", 0.2)

    return (
        f"Cellule {cell_id} [{tech}] à {time_str} — "
        f"SINR: {sinr:.1f} dB, RSRP: {rsrp:.0f} dBm, "
        f"Latence: {latency:.0f} ms, Jitter: {jitter:.1f} ms, "
        f"Débit DL: {thr_dl:.1f} Mbps, Débit UL: {thr_ul:.1f} Mbps, "
        f"Perte paquets: {pkt_loss:.1f}%, "
        f"Score signal: {sig_score:.1f}/100, Score QoS: {qos_score:.3f}. "
        f"Statut: {alert}."
    )


def ingest_kpi_records(collection):
    """Fetch latest KPIs from P1 and index into ChromaDB."""
    try:
        resp = httpx.get(f"{P1_URL}/api/kpi/latest", timeout=10)
        resp.raise_for_status()
        cells = resp.json().get("cells", [])
    except Exception as e:
        log.warning(f"Could not fetch KPI records from P1: {e}")
        cells = []

    if not cells:
        log.info("No KPI records to ingest")
        return 0

    docs, ids, metas = [], [], []
    for rec in cells:
        cell_id = rec.get("cell_id", "?")
        ts      = rec.get("last_updated", datetime.utcnow().isoformat())
        doc_id  = f"kpi_{cell_id}_{str(ts)[:19].replace(':', '-')}"

        docs.append(kpi_to_text(rec))
        ids.append(doc_id)
        metas.append({
            "cell_id":    cell_id,
            "doc_type":   "kpi_record",
            "alert_level":rec.get("alert_level", "normal"),
            "technology": rec.get("technology", "5G"),
            "timestamp":  str(ts),
        })

    # Upsert (add or update)
    collection.upsert(documents=docs, ids=ids, metadatas=metas)
    log.info(f"✓ Indexed {len(docs)} KPI records")
    return len(docs)


# ─── Anomaly History ─────────────────────────────────────────────────────────
def ingest_anomaly_history(collection):
    """Fetch recent anomalies and index them as alert summaries."""
    try:
        resp = httpx.get(f"{P1_URL}/api/kpi/anomalies?limit=100", timeout=10)
        resp.raise_for_status()
        anomalies = resp.json().get("anomalies", [])
    except Exception as e:
        log.warning(f"Could not fetch anomalies: {e}")
        return 0

    docs, ids, metas = [], [], []
    for rec in anomalies:
        cell_id = rec.get("cell_id", "?")
        alert   = rec.get("alert_level", "warning")
        ts      = rec.get("last_updated", datetime.utcnow().isoformat())
        doc_id  = f"alert_{cell_id}_{str(ts)[:19].replace(':', '-')}"

        text = (
            f"ALERTE {alert.upper()} — Cellule {cell_id}: "
            f"SINR={rec.get('sinr', '?')} dB, "
            f"Latence={rec.get('latency', '?')} ms, "
            f"Débit DL={rec.get('throughput_dl', '?')} Mbps. "
            f"Score signal: {rec.get('signal_score', '?')}/100."
        )
        docs.append(text)
        ids.append(doc_id)
        metas.append({
            "cell_id":    cell_id,
            "doc_type":   "anomaly_alert",
            "alert_level":alert,
            "timestamp":  str(ts),
        })

    if docs:
        collection.upsert(documents=docs, ids=ids, metadatas=metas)
        log.info(f"✓ Indexed {len(docs)} anomaly events")
    return len(docs)


# ─── Telecom Reference Docs ──────────────────────────────────────────────────
REFERENCE_DOCS = [
    {
        "id": "5g_nr_intro",
        "url": "https://en.wikipedia.org/wiki/5G_NR",
        "title": "5G New Radio — Introduction",
    },
    {
        "id": "lte_kpis",
        "url": "https://en.wikipedia.org/wiki/LTE_(telecommunication)",
        "title": "LTE Telecommunications",
    },
]

TELECOM_KNOWLEDGE = """
## KPI Thresholds — 5G NR (3GPP TS 38.101)
- SINR > 20 dB: Excellent signal quality. 5G NR operates optimally.
- SINR 10–20 dB: Good quality. High throughput achievable.
- SINR 0–10 dB: Acceptable. Some degradation in peak rates.
- SINR < 0 dB: Poor quality. High risk of call drops and handovers.
- SINR < -5 dB: Critical. Immediate intervention required.

## RSRP Thresholds (Reference Signal Received Power)
- RSRP > -80 dBm: Excellent coverage
- -80 to -95 dBm: Good coverage
- -95 to -110 dBm: Fair coverage, degraded rates
- -110 to -120 dBm: Poor coverage, frequent handovers
- < -120 dBm: No service

## Latency Standards
- 5G eMBB target latency: < 10 ms user-plane
- 5G URLLC target: < 1 ms
- 4G LTE target: < 30 ms
- Latency > 100 ms: Degraded user experience
- Latency > 200 ms: Unacceptable for real-time services

## QoS Classes (5G QI)
- QCI 1: Conversational voice (GBR, 100ms)
- QCI 2: Video call (GBR, 150ms)
- QCI 8: eMBB data (Non-GBR, 300ms)
- QCI 9: Default bearer (Non-GBR, 300ms)

## Common Root Causes of Anomalies
- High interference: Low SINR despite good RSRP → check neighboring cells
- Cell overload: High PRB utilization (>85%), rising latency
- Hardware fault: RSRP drop + SINR drop simultaneously
- Handover storm: Frequent handovers, ping-pong between cells
- Backhaul congestion: High latency, packet loss, normal SINR

## Handover Decision Criteria
A handover is triggered when:
- RSRP of serving cell < -110 dBm AND neighbor RSRP > serving + 3 dB (A3 event)
- RSRP < -120 dBm regardless of neighbors (A2 event)
- SINR < -3 dB for > 200ms continuously

## Spectral Efficiency
- Formula: SE = Throughput (bps) / Bandwidth (Hz)
- 5G theoretical max: 30 bits/s/Hz (256-QAM, 8×8 MIMO)
- Typical 4G LTE: 3-5 bits/s/Hz
- Low SE (< 1 bit/s/Hz) indicates poor channel conditions
"""


def ingest_telecom_docs(collection):
    """Index telecom reference knowledge into ChromaDB."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "],
    )

    # Index built-in knowledge
    chunks = splitter.split_text(TELECOM_KNOWLEDGE)
    docs, ids, metas = [], [], []
    for i, chunk in enumerate(chunks):
        docs.append(chunk)
        ids.append(f"telecom_ref_{i:04d}")
        metas.append({"doc_type": "reference", "source": "3gpp_standards"})

    collection.upsert(documents=docs, ids=ids, metadatas=metas)
    log.info(f"✓ Indexed {len(docs)} telecom reference chunks")
    return len(docs)


# ─── Main ingestion job ──────────────────────────────────────────────────────
def run_ingestion():
    log.info("=== Starting ingestion job ===")
    try:
        collection = get_chroma_collection()
        n1 = ingest_kpi_records(collection)
        n2 = ingest_anomaly_history(collection)
        n3 = ingest_telecom_docs(collection)
        total = collection.count()
        log.info(f"✓ Ingestion complete — Total vectors in DB: {total}")
    except Exception as e:
        log.error(f"Ingestion failed: {e}", exc_info=True)


if __name__ == "__main__":
    # Run once immediately, then every 30 minutes
    run_ingestion()

    scheduler = BlockingScheduler()
    scheduler.add_job(run_ingestion, "interval", minutes=30)
    log.info("Scheduler started — ingestion every 30 minutes")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Ingestion scheduler stopped")
