"""Remote MCP server (/mcp, streamable HTTP) — transport + tool contracts.

Mirrors what ChatGPT connectors / claude.ai integrations actually send:
JSON-RPC over POST /mcp with Accept: application/json, text/event-stream.

Two subtleties these tests encode for future maintainers:
1. Tools bypass FastAPI dependency injection — they open sessions via
   ``get_sessionmaker()`` at call time. ``app.main.lifespan → init_db →
   get_engine()`` REBINDS that global sessionmaker onto the DATABASE_URL
   engine on first boot, so the ``mcp_client`` helper re-asserts the fixture
   maker AFTER the TestClient lifespan has run.
2. Unknown tool names do NOT produce a JSON-RPC -32602 error on SDK 1.29.x;
   the lowlevel server logs a warning and returns a result with
   ``isError: true`` — both shapes are accepted here.
"""
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import Run, Trial
from app.db.session import _DbState, get_session
from app.engine.client import LLMResponse
from app.engine.model_registry import load_model_registry
from app.ingest.demo import load_demo_catalog
from app.main import app

MCP_URL = "/mcp"
RPC_HEADERS = {"Accept": "application/json, text/event-stream"}


def _rpc(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def _call_tool(tc: TestClient, name: str, args: dict) -> dict:
    """tools/call → parsed text-content payload (what the agent reads)."""
    r = tc.post(MCP_URL, json=_rpc("tools/call",
                                   {"name": name, "arguments": args}),
                headers=RPC_HEADERS)
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result.get("isError") is not True, result
    return json.loads(result["content"][0]["text"])


class _SkewClient:
    """Deterministic fake LLM — same bias trick as test_audit_metrics."""

    POOL = ["sku_007", "sku_017", "sku_029", "sku_001"]

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        null_allowed = '{"product_id": null' in prompt
        h = hash((prompt[:48], seed)) & 0xFFFF
        if null_allowed and h % 9 == 0:
            choice = None
        else:
            choice = self.POOL[0] if h % 3 else self.POOL[h % len(self.POOL)]
        content = f'{{"product_id": {choice!r}, "reason": "mcp contract test"}}'
        return LLMResponse(content=content, prompt_tokens=400,
                           completion_tokens=30, cost_usd=0.001,
                           latency_ms=2, model_version=entry.version)


@contextmanager
def mcp_client(maker):
    """App under test with BOTH access paths pointed at the fixture DB."""
    async def _ov():
        async with maker() as s:
            yield s

    prev = _DbState.maker
    _DbState.maker = maker  # pre-lifespan swap (covers boot helpers)
    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as tc:
            # init_db rebound the global onto the env DATABASE_URL engine —
            # put the fixture maker back so MCP tools see seeded rows.
            _DbState.maker = maker
            yield tc
    finally:
        app.dependency_overrides.clear()
        if prev is None:
            # First boot in this test process happened INSIDE this helper —
            # restore the pristine pre-boot state instead of writing back a
            # None maker (which would crash the next test's lifespan).
            from app.db import session as _dbsession

            _dbsession._DbState.engine = None
            _dbsession._DbState.maker = None
        else:
            _DbState.maker = prev


@pytest.fixture()
def unified_db(db_env):
    """Session factory bound to a fresh in-memory engine (per-test)."""
    return db_env


async def _seed_run(maker, status: str = "done") -> str:
    async with maker() as session:
        cid = await load_demo_catalog(session)
        run = Run(
            id=str(uuid4()), catalog_id=cid, type="audit", status=status,
            models={}, seeds={}, trials_total=640,
            # naive datetime — mirrors SQLite round-trips (see test_audit_api #3)
            started_at=(datetime.now(timezone.utc) - timedelta(seconds=90)
                        ).replace(tzinfo=None),
        )
        session.add(run)
        for i in range(2):
            session.add(Trial(
                run_id=run.id, model="ox-alpha", model_version="test-snap",
                tier="bulk", persona_id=f"P{i}", condition="control", seed=i,
                presented_order=["sku_001"], choice="sku_001", prompt_hash="h",
                null_allowed=False, parse_ok=True,
            ))
        await session.commit()
        return run.id


async def _seed_completed_run_via_runner(maker) -> str:
    from app.engine.runner import Runner, RunnerDeps

    async with maker() as session:
        cid = await load_demo_catalog(session)
    deps = RunnerDeps(registry=load_model_registry(), client=_SkewClient())
    return await Runner(maker, deps).run_audit(cid)


async def test_initialize_handshake(unified_db):
    with mcp_client(unified_db) as tc:
        r = tc.post(MCP_URL, json=_rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "pytest-mcp", "version": "0.0.0"},
        }), headers=RPC_HEADERS)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert isinstance(result["protocolVersion"], str)
        assert result["protocolVersion"]
        assert result["serverInfo"]["name"] == "agentaudit-mcp"
        assert "tools" in result["capabilities"]


async def test_tools_list_exposes_exactly_three_tools(unified_db):
    with mcp_client(unified_db) as tc:
        r = tc.post(MCP_URL, json=_rpc("tools/list"), headers=RPC_HEADERS)
        assert r.status_code == 200, r.text
        tools = r.json()["result"]["tools"]
        names = sorted(t["name"] for t in tools)
        assert names == ["audit_status", "create_payment_link", "get_report"]
        schemas = {t["name"]: t.get("inputSchema", {}) for t in tools}
        assert set(schemas["audit_status"].get("required", [])) == {"run_id"}
        assert set(schemas["create_payment_link"].get("required", [])) == {"run_id", "sku"}


async def test_mcp_exact_path_redirects_then_serves(unified_db):
    """POST /mcp (no slash) → one standard 307 to /mcp/, which then serves.
    Hosted clients follow 307 preserving method+body (fetch/httpx both do)."""
    with mcp_client(unified_db) as tc:
        raw = tc.post(MCP_URL, json=_rpc("ping"),
                      headers=RPC_HEADERS, follow_redirects=False)
        assert raw.status_code == 307, (raw.status_code, raw.text[:200])
        assert raw.headers["location"].endswith("/mcp/")
        served = tc.post(MCP_URL, json=_rpc("ping"), headers=RPC_HEADERS)
        assert served.status_code == 200, served.text[:200]


async def test_audit_status_on_seeded_run(unified_db):
    # status "done" — the boot reaper correctly marks seeded "running" rows
    # engine_lost, which is crash-hardening behavior covered elsewhere.
    rid = await _seed_run(unified_db, status="done")
    with mcp_client(unified_db) as tc:
        payload = _call_tool(tc, "audit_status", {"run_id": rid})
        assert payload["run_id"] == rid
        assert payload["status"] == "done"
        assert payload["trials_done"] == 2
        assert payload["trials_total"] == 640


async def test_unknown_run_returns_rest_error_envelope(unified_db):
    with mcp_client(unified_db) as tc:
        r = tc.post(MCP_URL, json=_rpc(
            "tools/call",
            {"name": "audit_status", "arguments": {"run_id": "no-such-run"}},
        ), headers=RPC_HEADERS)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        # AppError → structured SCHEMA §7 envelope, NOT a bare tool error
        assert result.get("isError") is not True, result
        body = json.loads(result["content"][0]["text"])
        assert body["error"]["code"] == "E601"


async def test_get_report_returns_metrics_and_revenue(unified_db):
    rid = await _seed_completed_run_via_runner(unified_db)
    with mcp_client(unified_db) as tc:
        payload = _call_tool(tc, "get_report", {"run_id": rid})
        for key in ("score", "hhi_norm", "coverage", "stability",
                    "invisible_skus", "revenue_preview"):
            assert key in payload, key
        node = payload["score"]
        assert node["ci_low"] <= node["value"] <= node["ci_high"]
        assert payload["trials"]["total"] == 220


async def test_unknown_tool_surfaces_error_result(unified_db):
    with mcp_client(unified_db) as tc:
        r = tc.post(MCP_URL, json=_rpc(
            "tools/call", {"name": "does_not_exist", "arguments": {}}),
            headers=RPC_HEADERS)
        assert r.status_code == 200, r.text
        body = r.json()
        err = body.get("error")
        if err is not None:
            assert err["code"] == -32602  # JSON-RPC style
        else:
            assert body["result"]["isError"] is True  # SDK 1.29.x style


async def test_malformed_body_is_clean_4xx_not_500(unified_db):
    with mcp_client(unified_db) as tc:
        r = tc.post(MCP_URL, content=b"this is not json",
                    headers={**RPC_HEADERS,
                             "Content-Type": "application/json"})
        assert 400 <= r.status_code < 500, r.status_code
