"""
TeleSight AI — RAG FastAPI (Part 3) — Port 8002
Intègre : pipeline RAG + agent + ingestion ChromaDB planifiée (toutes les 30 min)
"""

import logging
import os
import sys
import threading
import httpx
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── .env absolu ───────────────────────────────────────────────────────────────
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# ── sys.path : rendre le dossier rag/ importable depuis n'importe où ─────────
_RAG_DIR = Path(__file__).resolve().parent.parent / "rag"
if str(_RAG_DIR) not in sys.path:
    sys.path.insert(0, str(_RAG_DIR))

log = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="TeleSight AI — RAG Agent API",
    description="GenAI RAG agent for telecom network Q&A — Part 3",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

P1_URL = os.getenv("P1_URL", "http://localhost:8000")

# Singletons
_agent    = None
_pipeline = None


# ─── Ingestion en arrière-plan ────────────────────────────────────────────────
def _run_ingest_scheduler():
    """Lance l'ingestion ChromaDB une fois au démarrage puis toutes les 30 min.
    Tourne dans un thread daemon pour ne pas bloquer l'API."""
    try:
        from ingest import run_ingestion
        from apscheduler.schedulers.background import BackgroundScheduler

        log.info("→ Ingestion ChromaDB initiale en cours...")
        run_ingestion()
        log.info("✓ Ingestion initiale terminée")

        scheduler = BackgroundScheduler()
        scheduler.add_job(run_ingestion, "interval", minutes=30, id="rag_ingest")
        scheduler.start()
        log.info("✓ Scheduler d'ingestion démarré (toutes les 30 min)")
    except Exception as e:
        log.error(f"Ingestion scheduler failed: {e}", exc_info=True)


# ─── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global _agent, _pipeline

    # 1. Initialiser le pipeline RAG + agent
    try:
        from agent    import get_agent
        from pipeline import get_pipeline
        _pipeline = get_pipeline()
        _agent    = get_agent()
        log.info("✓ RAG pipeline + agent prêts")
    except Exception as e:
        log.error(f"Échec d'initialisation RAG: {e}", exc_info=True)

    # 2. Lancer l'ingestion ChromaDB dans un thread daemon (non-bloquant)
    t = threading.Thread(target=_run_ingest_scheduler, daemon=True, name="chroma-ingest")
    t.start()
    log.info("→ Thread d'ingestion ChromaDB lancé en arrière-plan")


# ─── Schemas ──────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question:  str
    use_agent: bool = True   # True = full agent with tools, False = simple RAG


class QueryResponse(BaseModel):
    answer:     str
    sources:    list = []
    tool_calls: list = []


# ─── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/api/agent/query", response_model=QueryResponse)
async def agent_query(req: QueryRequest):
    """
    Pose une question à l'agent TeleSight AI sur l'état du réseau.
    L'agent utilise ses outils pour chercher des données temps réel et des prédictions ML.
    """
    if _agent is None or _pipeline is None:
        raise HTTPException(503, "Agent IA non initialisé. Vérifiez les logs.")

    if req.use_agent:
        result = _agent.query(req.question)
    else:
        result = _pipeline.query(req.question)

    return QueryResponse(**result)


@app.get("/api/agent/report")
async def generate_report():
    """
    Génère automatiquement un rapport de supervision réseau pour la dernière heure.
    Résume les anomalies, les cellules les plus dégradées, les tendances et recommandations.
    """
    if _pipeline is None:
        raise HTTPException(503, "Pipeline RAG non initialisé.")

    anomalies, stats = [], {}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r1 = await client.get(f"{P1_URL}/api/kpi/anomalies?limit=20")
            anomalies = r1.json().get("anomalies", [])
        except Exception:
            pass
        try:
            r2 = await client.get(f"{P1_URL}/api/kpi/stats/global")
            stats = r2.json()
        except Exception:
            pass

    report = _pipeline.generate_report(anomalies, stats)
    return {
        "report":        report,
        "timestamp":     __import__("datetime").datetime.utcnow().isoformat(),
        "stats":         stats,
        "anomaly_count": len(anomalies),
    }


@app.get("/api/agent/status")
async def agent_status():
    return {
        "agent_ready":    _agent    is not None,
        "pipeline_ready": _pipeline is not None,
        "service":        "telesight-rag",
        "llm_provider":   os.getenv("LLM_PROVIDER", "ollama"),
        "llm_model":      os.getenv("LLM_MODEL",    "tinyllama"),
        "ollama_url":     os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "telesight-rag"}
