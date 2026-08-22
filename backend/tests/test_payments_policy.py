"""Agent money-policy gates — cap / whitelist / test-mode-only (SAFETY.md).

POST /api/payments/link must reject: over-cap amounts (E503), non-whitelisted
skus (E504) and live Razorpay keys (E505), while the under-cap demo happy path
keeps working. Mirrors the mocked-transport pattern from test_razorpay.py (T13.x).
"""
import httpx
from fastapi.testclient import TestClient

from app.db.models import Product, Run
from app.db.session import get_session
from app.engine.model_registry import load_model_registry
from app.engine.runner import Runner, RunnerDeps
from app.ingest.demo import load_demo_catalog
from app.main import app
from app.razorpay.client import RazorpayClient
from tests.test_runner import FakeClient


def _mock_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "plink_pol123", "short_url": "https://rzp.io/i/plink_pol123",
            "amount": 99900, "status": "created",
        }, request=request)

    return RazorpayClient("rzp_test_policy", "secret_test",
                          http_client=httpx.AsyncClient(
                              transport=httpx.MockTransport(handler)))


class PolicySettings:
    """Settings stand-in with money-policy fields (mirrors test_razorpay.FakeSettings)."""

    def __init__(self, **overrides):
        self.openrouter_api_key = ""
        self.razorpay_key_id = "rzp_test_policy"
        self.razorpay_key_secret = "secret_test"
        self.razorpay_webhook_secret = ""
        self.database_url = ""
        self.cost_cap_usd = 30.0
        self.port = 8000
        self.max_agent_spend_inr = 2000
        self.agent_allowed_skus = ""
        for key, value in overrides.items():
            setattr(self, key, value)


async def _seed_run(db_env) -> str:
    registry = load_model_registry()

    async with db_env() as session:
        catalog_id = await load_demo_catalog(session)
    return await Runner(db_env, RunnerDeps(registry=registry,
                                           client=FakeClient())).run_audit(catalog_id)


def _install(app_env, db_env, monkeypatch, settings):
    async def _ov():
        async with db_env() as s:
            yield s

    monkeypatch.setattr("app.routers.payments.get_settings", lambda: settings)
    if settings.razorpay_key_id.startswith("rzp_test_"):
        # Only mock the transport for legit test-mode keys; live-key tests must hit
        # the real _client() so the mode guard itself is what fires.
        monkeypatch.setattr("app.routers.payments._client", lambda: _mock_client())
    app_env.dependency_overrides[get_session] = _ov


async def test_under_cap_happy_path_still_works(db_env, monkeypatch):
    run_id = await _seed_run(db_env)
    _install(app, db_env, monkeypatch, PolicySettings())
    try:
        with TestClient(app) as tc:
            r = tc.post("/api/payments/link", json={"run_id": run_id,
                                                    "sku": "sku_007"})  # ₹999 < ₹2,000 cap
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["amount_inr"] == 999 and body["status"] == "created"
            assert body["short_url"].startswith("https://rzp.io/i/")
    finally:
        app.dependency_overrides.clear()


async def test_over_cap_sku_rejected_e503(db_env, monkeypatch):
    run_id = await _seed_run(db_env)
    _install(app, db_env, monkeypatch, PolicySettings())
    try:
        with TestClient(app) as tc:
            r = tc.post("/api/payments/link", json={"run_id": run_id,
                                                    "sku": "sku_016"})  # ₹2,499 > ₹2,000
            assert r.status_code == 403, r.text
            err = r.json()["error"]
            assert err["code"] == "E503"
            assert err["details"]["policy"] == "spend_cap"
            assert err["details"]["requested_inr"] == 2499
            assert err["details"]["cap_inr"] == 2000
            assert "MAX_AGENT_SPEND_INR" in err["message"]
    finally:
        app.dependency_overrides.clear()


async def test_non_whitelisted_sku_rejected_e504(db_env, monkeypatch):
    """Off-demo-catalog SKU exists in the run's catalog but isn't on the allowlist."""
    run_id = await _seed_run(db_env)
    async with db_env() as session:
        run = await session.get(Run, run_id)
        session.add(Product(catalog_id=run.catalog_id, sku="sku_901",
                            title="Off-list Gadget", price_inr=899,
                            description="exists in catalog, not on whitelist",
                            tier="medium"))
        await session.commit()

    _install(app, db_env, monkeypatch, PolicySettings())
    try:
        with TestClient(app) as tc:
            r = tc.post("/api/payments/link", json={"run_id": run_id, "sku": "sku_901"})
            assert r.status_code == 403, r.text
            err = r.json()["error"]
            assert err["code"] == "E504"
            assert err["details"]["policy"] == "sku_whitelist"
            assert err["details"]["sku"] == "sku_901"
            assert "AGENT_ALLOWED_SKUS" in err["message"]
    finally:
        app.dependency_overrides.clear()


async def test_whitelist_override_narrows_default_list(db_env, monkeypatch):
    """AGENT_ALLOWED_SKUS csv replaces the default demo list when set."""
    run_id = await _seed_run(db_env)
    _install(app, db_env, monkeypatch,
             PolicySettings(agent_allowed_skus="sku_007"))  # merchant narrows to one SKU
    try:
        with TestClient(app) as tc:
            # sku_009 (₹1,199) is a demo SKU under the cap — still rejected: not listed.
            r = tc.post("/api/payments/link", json={"run_id": run_id, "sku": "sku_009"})
            assert r.status_code == 403, r.text
            err = r.json()["error"]
            assert err["code"] == "E504" and err["details"]["policy"] == "sku_whitelist"

            ok = tc.post("/api/payments/link", json={"run_id": run_id, "sku": "sku_007"})
            assert ok.status_code == 201, ok.text
    finally:
        app.dependency_overrides.clear()


async def test_live_key_rejected_e505_before_any_network_call(db_env, monkeypatch):
    run_id = await _seed_run(db_env)
    # Real _client() stays unpatched — the rzp_live_ key must be refused by the
    # mode guard itself, before any RazorpayClient/transport is constructed.
    _install(app, db_env, monkeypatch,
             PolicySettings(razorpay_key_id="rzp_live_ACCIDENTALKEY"))
    try:
        with TestClient(app) as tc:
            r = tc.post("/api/payments/link", json={"run_id": run_id, "sku": "sku_007"})
            assert r.status_code == 403, r.text
            err = r.json()["error"]
            assert err["code"] == "E505"
            assert err["details"]["policy"] == "test_mode_only"
            assert "rzp_test_" in err["message"]
    finally:
        app.dependency_overrides.clear()
