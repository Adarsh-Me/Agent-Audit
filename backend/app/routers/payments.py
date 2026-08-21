"""Payments + Razorpay webhook — agent-to-ledger proof (TECHSPEC §12, SCHEMA §9).

POST /api/payments/link      idempotent per (run_id, sku) — replays return the same
                             link with short_url re-fetched live
GET  /api/payments/{run_id}/status   webhook-badge polling (target ≤ 5 s)
POST /api/webhooks/razorpay          HMAC-verified, deduped via webhook_events
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.config import get_settings
from app.db.models import Payment, Product, Run, WebhookEvent
from app.db.session import get_session
from app.errors import AppError
from app.razorpay.client import RazorpayClient, RazorpayError

router = APIRouter()


class LinkRequest(BaseModel):
    run_id: str
    sku: str


def _client() -> RazorpayClient:
    s = get_settings()
    if not s.razorpay_key_id or not s.razorpay_key_secret:
        raise AppError("E502", "Razorpay keys not configured — set RAZORPAY_KEY_ID/"
                               "RAZORPAY_KEY_SECRET in .env", status_code=503)
    return RazorpayClient(s.razorpay_key_id, s.razorpay_key_secret)


@router.post("/api/payments/link", status_code=201)
async def create_link(body: LinkRequest,
                      session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.get(Run, body.run_id)
    if run is None:
        raise AppError("E601", "run not found", status_code=404)

    idem = f"agentaudit:{body.run_id}:{body.sku}"
    existing = await session.scalar(select(Payment).where(Payment.idempotency_key == idem))
    if existing is not None:
        # Replay: re-fetch the live link so short_url is always present (the frozen
        # DDL has no short_url column). If Razorpay is unreachable we still return
        # the DB state — the caller just gets short_url="" and can retry.
        rp = _client()
        try:
            link = await rp.fetch_payment_link(existing.razorpay_link_id)
            short_url = link.short_url
        except (RazorpayError, httpx.HTTPError):
            short_url = ""
        finally:
            await rp.aclose()
        return {"payment_id": existing.id, "razorpay_link_id": existing.razorpay_link_id,
                "short_url": short_url, "amount_inr": existing.amount_inr,
                "status": existing.status, "idempotent_replay": True}

    product = await session.scalar(
        select(Product).where(Product.catalog_id == run.catalog_id,
                              Product.sku == body.sku))
    if product is None or product.price_inr is None:
        raise AppError("E601", f"sku not found in run catalog: {body.sku}", status_code=404)

    rp = _client()
    try:
        link = await rp.create_payment_link(
            amount_inr=product.price_inr,
            reference_id=idem,
            description=f"AgentAudit checkout proof — {product.title}",
            idempotency_key=idem,
        )
    finally:
        await rp.aclose()

    payment = Payment(run_id=run.id, razorpay_link_id=link.id,
                      amount_inr=link.amount_inr, status="created",
                      idempotency_key=idem)
    session.add(payment)
    await session.commit()
    return {"payment_id": payment.id, "razorpay_link_id": link.id,
            "short_url": link.short_url, "amount_inr": link.amount_inr,
            "status": "created"}


@router.get("/api/payments/{run_id}/status")
async def payment_status(run_id: str,
                         session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        (await session.execute(
            select(Payment).where(Payment.run_id == run_id).order_by(Payment.id.desc())
        ))
        .scalars()
        .all()
    )
    latest = rows[0] if rows else None
    return {
        "run_id": run_id,
        "payments": [
            {"razorpay_link_id": p.razorpay_link_id, "amount_inr": p.amount_inr,
             "status": p.status,
             "captured_at": p.captured_at.isoformat() if p.captured_at else None}
            for p in rows
        ],
        "captured": bool(latest and latest.status == "captured"),
    }


@router.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request,
                           session: AsyncSession = Depends(get_session)) -> Response:
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = get_settings().razorpay_webhook_secret
    from app.razorpay.client import verify_webhook_signature

    if not secret or not verify_webhook_signature(raw, signature, secret):
        raise AppError("E501", "webhook signature mismatch", status_code=400)

    import json

    event = json.loads(raw.decode("utf-8"))
    etype = event.get("event", "unknown")
    payload_entity = event.get("payload", {})

    # entity key per type: payment_link.{paid|captured} → link id; else top-level id
    entity_key = ""
    if "payment_link" in payload_entity:
        entity = payload_entity["payment_link"].get("entity", {})
        entity_key = entity.get("id", "")
    elif "payment" in payload_entity:
        entity = payload_entity["payment"].get("entity", {})
        entity_key = entity.get("id", "")
        if not entity_key:
            entity_key = entity.get("payment_link_id") if isinstance(
                entity.get("payment_link_id"), str) else ""
    if not entity_key:
        entity_key = hashlib_sha256(raw)

    dedupe = WebhookEvent(source="razorpay", type=etype, entity_key=entity_key,
                          payload=event)
    session.add(dedupe)
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        return Response(status_code=200)  # duplicate delivery — already processed

    if etype.startswith("payment_link.") and entity_key:
        link_row = await session.scalar(
            select(Payment).where(Payment.razorpay_link_id == entity_key))
        if link_row is not None:
            if etype in ("payment_link.captured", "payment_link.paid"):
                from datetime import datetime, timezone

                link_row.status = "captured"
                link_row.captured_at = datetime.now(timezone.utc)
            elif etype == "payment_link.failed" or "failed" in etype:
                link_row.status = "failed"
    await session.commit()
    return Response(status_code=200)


def hashlib_sha256(data: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(data).hexdigest()[:32]
