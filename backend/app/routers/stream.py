"""SSE stream — GET /api/stream/{run_id}."""
import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.db.session import get_sessionmaker
from app.events import HEARTBEAT_S, bus, sse_format
from app.errors import AppError

router = APIRouter()


@router.get("/api/stream/{run_id}")
async def stream_run(run_id: str):
    from app.db.models import Run

    maker = get_sessionmaker()
    async with maker() as session:
        run = await session.get(Run, run_id)
    if run is None:
        raise AppError("E601", "run not found", status_code=404)

    async def gen():
        q = bus.subscribe(run_id)
        try:
            if run.status in ("done", "partial", "failed"):
                yield sse_format("complete", {"run_id": run_id, "status": run.status})
                return
            last = bus.last(run_id)
            if last:
                yield sse_format(last.get("type", "progress"), last)
            yield sse_format("connected", {"run_id": run_id, "status": "running"})
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_S)
                    ev_type = ev.pop("type", "message")
                    yield sse_format(ev_type, ev)
                    if ev_type == "complete":
                        break
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            bus.unsubscribe(run_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
