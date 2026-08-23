"""AgentAudit backend — FastAPI application entry point."""
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.constants import RATE_LIMIT_POST_RPM
from app.db.session import init_db
from app.errors import AppError, error_payload
from app.routers import audit as audit_router
from app.routers import catalog as catalog_router
from app.routers import delta as delta_router
from app.routers import payments as payments_router
from app.routers import remediations as remediations_router
from app.routers import report as report_router
from app.routers import runs as runs_router
from app.routers import stores as stores_router
from app.routers import stream as stream_router
from app.routers import uploads as uploads_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await _reap_orphaned_runs()
    yield


async def _reap_orphaned_runs() -> None:
    """Engine tasks live inside this process; a restart (or crash) kills them
    silently and used to leave run rows stuck at 'running' forever. Any run
    still queued/running at boot belongs to a dead engine — mark it failed
    with an honest reason. Trials already persisted stay queryable (mid-data)."""
    from datetime import datetime, timezone

    from sqlalchemy import select, update

    from app.db.models import Run
    from app.db.session import get_sessionmaker

    maker = get_sessionmaker()
    async with maker() as session:
        orphans = (await session.execute(
            select(Run.id).where(Run.status.in_(("queued", "running")))
        )).scalars().all()
        if not orphans:
            return
        await session.execute(
            update(Run)
            .where(Run.id.in_(orphans))
            .values(
                status="failed",
                abort_reason=(
                    "engine_lost: the server restarted mid-run — recorded trials are "
                    "preserved and auditable below"
                ),
                completed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
    print(f"[reaper] marked {len(orphans)} orphaned run(s) failed (engine_lost)")


app = FastAPI(title="AgentAudit", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rate limiting: 60 req/min/IP on POST endpoints → 429 E602 (SCHEMA §7.1) ---
_post_hits: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_posts(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith("/api"):
        now = time.monotonic()
        key = request.client.host if request.client else "unknown"
        hits = _post_hits[key]
        while hits and now - hits[0] > 60.0:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_POST_RPM:
            return JSONResponse(
                status_code=429,
                content=error_payload("E602", "Rate limited — retry in 60s"),
            )
        hits.append(now)
    return await call_next(request)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


app.include_router(catalog_router.router)
app.include_router(uploads_router.router)
app.include_router(stores_router.router)
app.include_router(runs_router.router)
app.include_router(audit_router.router)
app.include_router(report_router.router)
app.include_router(stream_router.router)
app.include_router(remediations_router.router)
app.include_router(delta_router.router)
app.include_router(payments_router.router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
