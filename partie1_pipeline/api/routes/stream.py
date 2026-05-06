"""
TeleSight AI — SSE Stream Route (sync Redis version)
"""
import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.get("/live")
async def sse_live_stream(request: Request):
    r = request.app.state.redis

    async def event_generator():
        last_seen_id = None
        yield "data: {\"type\": \"connected\"}\n\n"

        while True:
            if await request.is_disconnected():
                break
            try:
                events = r.lrange("events:live", 0, 9)
                for raw in reversed(events):
                    try:
                        record   = json.loads(raw)
                        event_id = f"{record.get('cell_id','?')}_{record.get('timestamp','')}"
                        if event_id == last_seen_id:
                            continue
                        last_seen_id = event_id
                        yield f"data: {json.dumps(record, default=str)}\n\n"
                    except Exception:
                        continue
            except Exception as e:
                yield f"data: {{\"type\": \"error\", \"message\": \"{str(e)[:100]}\"}}\n\n"

            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/live/stats")
async def sse_stream_stats(request: Request):
    pool = request.app.state.pg_pool

    async def stats_generator():
        yield "data: {\"type\": \"connected\"}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                conn = pool.getconn()
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT COUNT(*) AS total_cells,
                                   ROUND(AVG(sinr)::numeric,2) AS avg_sinr,
                                   ROUND(AVG(latency)::numeric,2) AS avg_latency,
                                   COUNT(*) FILTER (WHERE alert_level='critical') AS critical,
                                   COUNT(*) FILTER (WHERE alert_level='warning')  AS warning,
                                   COUNT(*) FILTER (WHERE alert_level='normal')   AS normal
                            FROM cell_latest
                        """)
                        cols = [d[0] for d in cur.description]
                        row  = cur.fetchone()
                        if row:
                            yield f"data: {json.dumps(dict(zip(cols,row)), default=str)}\n\n"
                finally:
                    pool.putconn(conn)
            except Exception as e:
                yield f"data: {{\"error\": \"{str(e)[:100]}\"}}\n\n"
            await asyncio.sleep(5.0)

    return StreamingResponse(
        stats_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )