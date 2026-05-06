"""
TeleSight AI — ML FastAPI (Part 2) — Port 8001
"""

import logging
import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from predictor import TelecomPredictor

log = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="TeleSight AI — ML API",
    description="Anomaly detection + handover prediction — Part 2",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

P1_URL = os.getenv("P1_URL", "http://localhost:8000")

# ─── Load models at startup ──────────────────────────────────────────────────
predictor: TelecomPredictor = None


@app.on_event("startup")
async def load_models():
    global predictor
    predictor = TelecomPredictor()
    log.info("✓ TelecomPredictor ready")


# ─── Schemas ─────────────────────────────────────────────────────────────────
class KPIRecord(BaseModel):
    cell_id:       str   = "CELL_001"
    technology:    str   = "5G"
    rsrp:          float = -95.0
    rsrq:          float = -10.0
    sinr:          float = 10.0
    throughput_dl: float = 50.0
    throughput_ul: float = 20.0
    latency:       float = 20.0
    jitter:        float = 2.0
    packet_loss:   float = 0.5
    handover_label:int   = 0
    is_anomaly:    int   = 0
    latitude:      float = 36.82
    longitude:     float = 10.17


# ─── Endpoints ───────────────────────────────────────────────────────────────
@app.post("/api/ml/predict")
async def predict_single(record: KPIRecord):
    """Predict anomaly score for a single KPI record."""
    if predictor is None:
        raise HTTPException(503, "Models not loaded yet")
    result = predictor.predict(record.dict())
    return result


@app.post("/api/ml/predict/batch")
async def predict_batch(records: List[KPIRecord]):
    """Predict anomaly scores for multiple KPI records."""
    if predictor is None:
        raise HTTPException(503, "Models not loaded yet")
    if len(records) > 500:
        raise HTTPException(400, "Maximum 500 records per batch")
    results = predictor.predict_batch([r.dict() for r in records])
    return {"count": len(results), "predictions": results}


@app.get("/api/ml/score/all-cells")
async def score_all_cells():
    """
    Fetch latest KPIs from P1, score all cells, return summary.
    """
    if predictor is None:
        raise HTTPException(503, "Models not loaded yet")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{P1_URL}/api/kpi/latest")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise HTTPException(503, f"Cannot reach P1 API: {e}")

    cells = data.get("cells", [])
    if not cells:
        return {"critical": 0, "warning": 0, "normal": 0, "cells": []}

    predictions = predictor.predict_batch(cells)

    summary = {"critical": 0, "warning": 0, "normal": 0}
    for pred in predictions:
        summary[pred["alert_level"]] += 1

    return {
        **summary,
        "total": len(predictions),
        "cells": predictions,
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models_loaded": predictor is not None,
        "service": "telesight-ml",
    }
