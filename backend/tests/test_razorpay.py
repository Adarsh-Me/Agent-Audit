"""Razorpay integration tests — mocked transport + real HMAC math (T13.x)."""
import hashlib
import hmac as hmac_mod
import json

import httpx
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.engine.runner import Runner, RunnerDeps
from app.engine.model_registry import load_model_registry
from app.ingest.demo import load_demo_catalog
from app.main import app
from app.razorpay.client import RazorpayClient, verify_webhook_signature
from tests.test_runner import FakeClient


def _link_resp(link_id="plink_test123", amount=99900):
    return httpx.Response(200, json={
        "id": link_id, "short_url": f"https://rzp.io/i/{link_id}",
        "amount": amount, "status": "created",
    }, request=httpx.Request("POST", "https://api.razorpay.com/v1/payment_links"))


def _dispatching_handler(seen=None):
    """Serve both POST /payment_links and GET /payment_links/{id} with one body."""
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.setdefault("methods", []).append(request.method)
            seen["last_url"] = str(request.url)
        body = {
            "id": "plink_test123", "short_url": "https://rzp.io/i/plink_test123",
            "amount": 99900, "status": "created",
        }
        return httpx.Response(200, json=body, request=request)
    return handler


async def test_create_payment_link_mocked():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization", "")
        seen["body"] = json.loads(request.content)
        return _link_resp()

    client = RazorpayClient("key_test", "secret_test",
                            http_client=httpx.AsyncClient(
                                transport=httpx.MockTransport(handler)))
    try:
        link = await client.create_payment_link(amount_inr=999, reference_id="ref-1",
                                                description="d", idempotency_key="idem-1")
        assert link.id == "plink_test123"
        assert link.amount_inr == 999  # rupees preserved (API got paise)
        assert seen["body"]["amount"] == 99900
        assert seen["body"]["reference_id"] == "ref-1"
        assert seen["auth"].startswith("Basic ")
        assert seen and True
    finally:
        await client.aclose()


async def test_fetch_payment_link_mocked():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return _link_resp(amount=149900)

    client = RazorpayClient("key_test", "secret_test",
                            http_client=httpx.AsyncClient(
                                transport=httpx.MockTransport(handler)))
    try:
        link = await client.fetch_payment_link("plink_test123")
        assert link.id == "plink_test123"
        assert link.short_url == "https://rzp.io/i/plink_test123"
        assert link.amount_inr == 1499  # paise → rupees on the way back
        assert seen["url"].endswith("/v1/payment_links/plink_test123")
    finally:
        await client.aclose()


def test_webhook_signature_math():
    body = b'{"event":"payment_link.captured"}'
    secret = "whsec_test"
    good = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, good, secret)
    assert not verify_webhook_signature(body, good[::-1], secret)
    assert not verify_webhook_signature(body, good, "other-secret")


async def _seed_run(db_env) -> str:
    registry = load_model_registry()

    async with db_env() as session:
        catalog_id = await load_demo_catalog(session)
    return await Runner(db_env, RunnerDeps(registry=registry,
                                           client=FakeClient())).run_audit(catalog_id)


async def test_payment_link_endpoint_and_status(db_env, monkeypatch):
    run_id = await _seed_run(db_env)
    seen: dict = {}

    def fake_client():
        return RazorpayClient("key_test", "secret_test",
                              http_client=httpx.AsyncClient(
                                  transport=httpx.MockTransport(
                                      _dispatching_handler(seen))))

    monkeypatch.setattr("app.routers.payments._client", fake_client)

    async def _ov():
        async with db_env() as s:
            yield s

    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as tc:
            r = tc.post("/api/payments/link", json={"run_id": run_id, "sku": "sku_007"})
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["amount_inr"] == 999 and body["status"] == "created"

            # idempotent replay — same link, no new charge; short_url re-fetched live
            r2 = tc.post("/api/payments/link", json={"run_id": run_id, "sku": "sku_007"})
            assert r2.json()["idempotent_replay"] is True
            assert r2.json()["razorpay_link_id"] == body["razorpay_link_id"]
            assert r2.json()["short_url"] == "https://rzp.io/i/plink_test123"
            assert seen.get("methods", []) == ["POST", "GET"]

            # status endpoint pre-capture
            s = tc.get(f"/api/payments/{run_id}/status").json()
            assert s["captured"] is False and len(s["payments"]) == 1

            # --- webhook: bad signature → 400 E501 ---
            payload = {
                "event": "payment_link.captured",
                "payload": {"payment_link": {"entity": {"id":
                            body["razorpay_link_id"]}}},
            }
            raw = json.dumps(payload).encode()
            r3 = tc.post("/api/webhooks/razorpay", content=raw,
                         headers={"X-Razorpay-Signature": "deadbeef"})
            assert r3.status_code == 400
            assert r3.json()["error"]["code"] == "E501"

            # --- webhook: valid signature flips payment to captured ---
            class FakeSettings:
                razorpay_key_id = "k"
                razorpay_key_secret = "s"
                razorpay_webhook_secret = "test-webhook-secret"
                database_url = ""
                openrouter_api_key = ""
                cost_cap_usd = 30.0
                port = 8000

            monkeypatch.setattr("app.routers.payments.get_settings", lambda: FakeSettings())

            sig = hmac_mod.new(b"test-webhook-secret", raw, hashlib.sha256).hexdigest()
            r4 = tc.post("/api/webhooks/razorpay", content=raw,
                         headers={"X-Razorpay-Signature": sig})
            assert r4.status_code == 200, r4.text

            s5 = tc.get(f"/api/payments/{run_id}/status").json()
            assert s5["captured"] is True
            assert s5["payments"][0]["captured_at"] is not None

            # duplicate delivery → deduped silently
            r6 = tc.post("/api/webhooks/razorpay", content=raw,
                         headers={"X-Razorpay-Signature": sig})
            assert r6.status_code == 200
    finally:
        app.dependency_overrides.clear()
