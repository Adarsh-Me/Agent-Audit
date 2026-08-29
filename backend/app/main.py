"""AgentAudit backend — FastAPI application entry point."""
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import RATE_LIMIT_POST_RPM
from app.config import get_settings
from app.db.session import get_session, init_db
from app.errors import AppError, error_payload
from app.mcp_server import build_mcp_asgi_app, mcp_http_endpoint, mcp_lifespan
from app.routers import audit as audit_router
from app.routers import catalog as catalog_router
from app.routers import delta as delta_router
from app.routers import evidence as evidence_router
from app.routers import payments as payments_router
from app.routers import remediations as remediations_router
from app.routers import report as report_router
from app.routers import runs as runs_router
from app.routers import stores as stores_router
from app.routers import stream as stream_router
from app.routers import uploads as uploads_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    on_primary = await init_db()
    if not on_primary:
        print("[boot] serving on fallback SQLite — audit data resets on redeploy")
    await _migrate_add_raw_head()
    await _ensure_demo_catalog()
    await _reap_orphaned_runs()
    # MCP streamable-HTTP transport: mounted sub-apps get no lifespan of their
    # own, so its session manager runs inside ours (see app/mcp_server.py).
    async with mcp_lifespan():
        yield


async def _migrate_add_raw_head() -> None:
    """create_all creates missing TABLES but never new COLUMNS — add trials.raw_head
    for existing databases (2026-08-29 parse_ok=0 diagnosability column)."""
    from sqlalchemy import text

    from app.db.session import get_engine

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE trials ADD COLUMN IF NOT EXISTS raw_head TEXT"))
    except Exception:  # noqa: BLE001 — SQLite has no IF NOT EXISTS for columns
        try:
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE trials ADD COLUMN raw_head TEXT"))
        except Exception:  # noqa: BLE001 — column already exists
            pass


async def _ensure_demo_catalog() -> None:
    """Fresh deployments boot with an empty database — seed the demo catalog so
    the store is browsable and auditable without a manual make step (idempotent)."""
    from sqlalchemy import func, select

    from app.db.models import Catalog
    from app.db.session import get_sessionmaker
    from app.ingest.demo import load_demo_catalog

    maker = get_sessionmaker()
    async with maker() as session:
        n = (await session.execute(
            select(func.count()).select_from(Catalog)
        )).scalar()
        if n:
            return
        cid = await load_demo_catalog(session)
        await session.commit()
    print(f"[seed] empty database — loaded demo catalog {cid}")


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

_origins_raw = get_settings().cors_origins.strip()
if _origins_raw == "*":
    # Public demo mode: any origin may read; credentials stay off (cookie-free API)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    _origins = [o.strip() for o in _origins_raw.split(",") if o.strip()] or [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
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
app.include_router(evidence_router.router)
app.include_router(payments_router.router)

# Remote MCP (ChatGPT connectors / claude.ai integrations / any MCP client):
# same three tools as mcp-server/server.mjs, over streamable HTTP. The exact
# Route serves POST /mcp directly (the edge 411s redirected request bodies);
# the Mount covers /mcp/… paths.
from starlette.routing import Route as _Route  # noqa: E402

app.router.routes.append(_Route("/mcp", mcp_http_endpoint,
                                methods=["GET", "POST", "DELETE"]))
app.mount("/mcp", build_mcp_asgi_app())


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/dbstatus")
async def dbstatus() -> dict:
    """Ops probe — reports which database this container landed on. The
    platform edge 404s /healthz, so the same signal lives under /api."""
    from app.db.session import db_status

    return db_status()


@app.get("/api/enginecheck")
async def enginecheck(realistic: bool = False,
                      t: float = 0.0,
                      n: int = 1,
                      session: AsyncSession = Depends(get_session)) -> dict:
    """Live LLM calls FROM THIS CONTAINER — tiny probes by default, or pass
    ?realistic=1 to replay an audit-sized prompt built by the engine's own
    builder over the current default catalog (the 2026-08-26 deployed run
    recorded 640/640 unusable answers while identical keys worked from dev;
    this separates egress/credential failures from payload-size failures).
    ?t=1.0 sends the runner's temperature; ?n=3 repeats the probe n times so
    runner-specific variables (temperature, bursts) can be bisected in-container.
    Never echoes keys; provider bodies are truncated."""
    import httpx
    from sqlalchemy import select

    from app.db.models import Product
    from app.engine.prompts import build_prompt
    from app.routers.catalog import _canonical, _resolve_catalog

    s = get_settings()
    prompt_body = 'Return JSON {"ok":true}'
    out: dict[str, object] = {}
    if realistic:
        catalog = await _resolve_catalog(session, None)
        rows = (
            (await session.execute(
                select(Product).where(Product.catalog_id == catalog.id).order_by(Product.sku)
            ))
            .scalars()
            .all()
        )
        persona = {
            "profile_summary": "Pragmatic gift shopper buying one item",
            "task": "Pick exactly one product that best matches your needs",
            "budget_inr": 3000,
        }
        prompt_body = build_prompt(
            persona, [_canonical(r) for r in rows], null_allowed=True
        )
        out["probe"] = {
            "catalog": catalog.source,
            "products": len(rows),
            "prompt_chars": len(prompt_body),
            "approx_tokens": len(prompt_body) // 4,
        }

    # Registry-driven probe: exercises whatever model is pinned in models.yaml
    # (SINGLE-MODEL MODE) instead of hardcoding provider slugs that rot.
    from app.engine.model_registry import load_model_registry

    entry = load_model_registry().bulk[0]
    key_field = entry.api_key_env or "openrouter_api_key"
    api_key = getattr(s, key_field, "") or s.openrouter_api_key
    base = (entry.base_url or "https://openrouter.ai/api/v1").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    payload: dict[str, object] = {
        "model": entry.openrouter_id,
        # 2026-08-29: was 32 — far too small to fit the JSON answer, so the
        # probe ALWAYS reported finish_reason=length + parse_ok:false even when
        # the model was healthy. Match the engine's real output budget.
        "max_tokens": 6000,
        "messages": [{"role": "user", "content": prompt_body}],
    }
    # 2026-08-29: runner bisecting — ?t=1.0 replicates the runner's temperature.
    if t > 0:
        payload["temperature"] = t
    if entry.json_mode:
        payload["response_format"] = {"type": "json_object"}
    checks = [
        (
            f"{entry.id}:{entry.openrouter_id}",
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {api_key}",
             "Content-Type": "application/json"},
            payload,
        ),
    ]
    n = max(1, min(int(n), 5))
    results: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=90) as client:
        for name, url, headers, payload in checks:
            runs: list[dict] = []
            for attempt in range(n):
                try:
                    r = await client.post(url, json=payload, headers=headers)
                    body_preview = r.text[:200]
                    parsed_ok = False
                    parsed_choice = None
                    content_head = None
                    if r.status_code < 400:
                        # 2026-08-27: realistic-mode probe now also tries to parse
                        # the assistant content the same way the engine does, so
                        # a 200 with content=null shows up as "parse_ok":false —
                        # this is what the previous enginecheck missed (which made
                        # the 28-min run's 0/220 parse failure look like a
                        # passing health check).
                        try:
                            msg = r.json()["choices"][0]["message"]
                            from app.engine.parse import parse_response as _pr
                            content = msg.get("content")
                            if isinstance(content, str) and content.strip():
                                # 2026-08-29: validate against the REAL catalog skus —
                                # the old empty set() made every real choice fail the
                                # membership check, so the probe always showed
                                # parse_ok:false regardless of model health.
                                probe_skus = {r2.sku for r2 in rows} if realistic else set()
                                parsed = _pr(content, probe_skus, null_allowed=True)
                                parsed_ok = parsed.parse_ok
                                parsed_choice = parsed.choice
                                content_head = content[:160]
                        except Exception:
                            pass
                    runs.append({
                        "http": r.status_code,
                        "body": body_preview,
                        "parse_ok": parsed_ok,
                        "parsed_choice": parsed_choice,
                        "content_head": content_head,
                    })
                except Exception as exc:  # noqa: BLE001 — diagnostics endpoint
                    runs.append({"error": f"{type(exc).__name__}: {exc}"[:200]})
            results[name] = {"n": n, "temperature": t or None,
                             "parse_ok_count": sum(1 for x in runs if x.get("parse_ok")),
                             "runs": runs}
    out.update(results)
    return out


@app.get("/api/debug/trials/{run_id}")
async def debug_trial_failures(run_id: str,
                               session: AsyncSession = Depends(get_session)) -> dict:
    """Diagnose parse_ok=0 runs — samples the raw model output head captured on
    failed trials (2026-08-29). Read-only, no credentials, truncated."""
    from sqlalchemy import func, select

    from app.db.models import Trial

    rows = (
        (await session.execute(
            select(Trial.persona_id, Trial.condition, Trial.latency_ms, Trial.raw_head)
            .where(Trial.run_id == run_id, Trial.parse_ok.is_(False))
            .order_by(Trial.latency_ms.desc())
            .limit(6)
        ))
        .all()
    )
    total_failed = (await session.scalar(
        select(func.count()).select_from(Trial)
        .where(Trial.run_id == run_id, Trial.parse_ok.is_(False))
    )) or 0
    return {
        "run_id": run_id,
        "failed": int(total_failed),
        "samples": [
            {"persona_id": r.persona_id, "condition": r.condition,
             "latency_ms": r.latency_ms, "raw_head": (r.raw_head or "")[:400]}
            for r in rows
        ],
    }
