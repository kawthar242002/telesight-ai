"""
TeleSight AI — KPI Routes (psycopg2 version)
"""
import json
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query

router = APIRouter()

def _pg(request: Request):
    return request.app.state.pg_pool

def _redis(request: Request):
    return request.app.state.redis

def _fetchall(pool, query, params=()):
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        pool.putconn(conn)

def _fetchone(pool, query, params=()):
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cols = [d[0] for d in cur.description]
            row  = cur.fetchone()
            return dict(zip(cols, row)) if row else None
    finally:
        pool.putconn(conn)


@router.get("/latest")
async def get_latest_kpis(request: Request):
    r    = _redis(request)
    pool = _pg(request)

    keys = r.keys("cell:latest:*")
    if keys:
        records = []
        for key in keys:
            data = r.hgetall(key)
            if data:
                records.append(_parse_record(data))
        return {"count": len(records), "cells": records}

    rows = _fetchall(pool, "SELECT * FROM cell_latest ORDER BY last_updated DESC")
    return {"count": len(rows), "cells": rows}


@router.get("/cells")
async def get_cells(request: Request):
    pool = _pg(request)
    rows = _fetchall(pool,
        "SELECT cell_id, technology, alert_level, latitude, longitude, last_updated "
        "FROM cell_latest ORDER BY cell_id"
    )
    return {"count": len(rows), "cells": rows}


@router.get("/anomalies")
async def get_anomalies(
    request: Request,
    level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    pool = _pg(request)
    if level in ("critical", "warning"):
        rows = _fetchall(pool,
            "SELECT * FROM cell_latest WHERE alert_level = %s ORDER BY last_updated DESC LIMIT %s",
            (level, limit)
        )
    else:
        rows = _fetchall(pool,
            "SELECT * FROM cell_latest WHERE alert_level != 'normal' ORDER BY last_updated DESC LIMIT %s",
            (limit,)
        )
    return {"count": len(rows), "anomalies": rows}


@router.get("/stats/global")
async def get_global_stats(request: Request):
    pool = _pg(request)
    row  = _fetchone(pool, """
        SELECT
            COUNT(*)                                         AS total_cells,
            ROUND(AVG(sinr)::numeric, 2)                    AS avg_sinr,
            ROUND(AVG(latency)::numeric, 2)                 AS avg_latency,
            ROUND(AVG(throughput_dl)::numeric, 2)           AS avg_throughput_dl,
            ROUND(AVG(packet_loss)::numeric, 4)             AS avg_packet_loss,
            COUNT(*) FILTER (WHERE alert_level='critical')  AS critical_count,
            COUNT(*) FILTER (WHERE alert_level='warning')   AS warning_count,
            COUNT(*) FILTER (WHERE alert_level='normal')    AS normal_count,
            ROUND(
                (COUNT(*) FILTER (WHERE alert_level != 'normal'))::numeric
                / NULLIF(COUNT(*),0) * 100, 1
            ) AS anomaly_rate_pct
        FROM cell_latest
    """)
    return row or {"total_cells": 0}


@router.get("/history/{cell_id}")
async def get_cell_history(
    request: Request,
    cell_id: str,
    limit: int = Query(100, ge=1, le=1000),
    hours: Optional[int] = Query(None),
):
    pool = _pg(request)
    if hours:
        rows = _fetchall(pool,
            "SELECT * FROM kpi_records WHERE cell_id = %s "
            "AND timestamp >= NOW() - (%s || ' hours')::INTERVAL "
            "ORDER BY timestamp DESC LIMIT %s",
            (cell_id, str(hours), limit)
        )
    else:
        rows = _fetchall(pool,
            "SELECT * FROM kpi_records WHERE cell_id = %s ORDER BY timestamp DESC LIMIT %s",
            (cell_id, limit)
        )
    if not rows:
        raise HTTPException(404, f"Cell '{cell_id}' not found")
    return {"cell_id": cell_id, "count": len(rows), "history": rows}


def _parse_record(data: dict) -> dict:
    float_cols = {"rsrp","rsrq","sinr","throughput_dl","throughput_ul","latency",
                  "jitter","packet_loss","latitude","longitude",
                  "signal_score","qos_score","spectral_efficiency","prb_utilization"}
    int_cols   = {"handover_label","is_anomaly","active_users"}
    result = {}
    for k, v in data.items():
        if k in float_cols:
            result[k] = float(v) if v not in ("", "None", "null") else None
        elif k in int_cols:
            result[k] = int(float(v)) if v not in ("", "None", "null") else None
        else:
            result[k] = v
    return result