"""
TeleSight AI — Part 1 FastAPI (psycopg2 version — stable on Windows)
"""
import os
import logging
import psycopg2
import psycopg2.pool
import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path

# Charger le .env depuis le dossier partie1_pipeline/ (independamment du cwd)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

import sys
sys.path.insert(0, str(Path(__file__).parent))

from routes.kpi import router as kpi_router
from routes.stream import router as stream_router

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="TeleSight AI — Pipeline API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _build_pg_dsn() -> str:
    """Convertit postgresql://user:pass@host:port/db en format psycopg2 DSN si necessaire."""
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        # Parser l'URL manuellement
        import urllib.parse
        r = urllib.parse.urlparse(url)
        return (
            f"host={r.hostname} port={r.port or 5432} "
            f"dbname={r.path.lstrip('/')} "
            f"user={r.username} password={r.password}"
        )
    # Deja en format libpq (host=... dbname=...)
    return url or "host=127.0.0.1 port=5432 dbname=telesight user=telesight password=telesight123"


PG_DSN    = _build_pg_dsn()
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")

@app.on_event("startup")
async def startup():
    app.state.pg_pool = psycopg2.pool.ThreadedConnectionPool(2, 10, PG_DSN)
    app.state.redis   = redis.from_url(REDIS_URL, decode_responses=True)
    app.state.redis.ping()
    log.info("PostgreSQL pool + Redis ready")

@app.on_event("shutdown")
async def shutdown():
    app.state.pg_pool.closeall()

app.include_router(kpi_router,    prefix="/api/kpi",    tags=["KPI"])
app.include_router(stream_router, prefix="/api/stream", tags=["Stream"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "telesight-pipeline"}