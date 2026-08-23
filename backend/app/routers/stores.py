"""Store import — POST /api/stores/import (SCHEMA §3.1.4 extension).

Fetches a real store's public product feed (Shopify /products.json), maps it to
canonical upload rows, validates with the shared pipeline, creates the catalog,
and — before the 201 returns — runs the legibility pass so rich/medium/starved
tiers are committed to the DB. The frontend fires createAudit immediately on
201; tiers must already exist by then (no async gap).

  E210 not a Shopify store / feed not public · E211 rate-limited
  E212 refused host · E101/E107 from the shared validator
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import STORE_FX_TO_INR, STORE_MAX_PRODUCTS
from app.db.session import get_session
from app.errors import AppError
from app.ingest.store import (
    StoreImportError,
    fetch_shopify_rows,
    normalize_store_url,
)
from app.ingest.upload import (
    PayloadError,
    create_upload_catalog,
    validate_product_list,
)
from app.stats.legibility import score_catalog_and_persist
from urllib.parse import urlsplit

router = APIRouter()


class StoreImportRequest(BaseModel):
    url: str = Field(min_length=4, max_length=300)
    store_currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    max_products: int = Field(default=STORE_MAX_PRODUCTS, ge=5, le=STORE_MAX_PRODUCTS)


@router.post("/api/stores/import", status_code=201)
async def import_store(body: StoreImportRequest,
                       session: AsyncSession = Depends(get_session)) -> dict:
    try:
        base_url = normalize_store_url(body.url)
    except StoreImportError as exc:
        raise AppError(exc.code, exc.message, status_code=400) from exc

    try:
        fetched = await fetch_shopify_rows(base_url, body.store_currency, body.max_products)
    except StoreImportError as exc:
        status = 503 if exc.code == "E211" else 400
        raise AppError(exc.code, exc.message, status_code=status) from exc

    try:
        validation = validate_product_list(fetched.rows)
    except PayloadError as exc:
        raise AppError(exc.code, exc.message, status_code=400) from exc

    host = urlsplit(base_url).hostname or base_url
    catalog_id = await create_upload_catalog(session, validation.valid, merchant_name=host)

    # synchronous tier assignment — committed before the response so an
    # immediately-following createAudit reads tiered products, never 'unknown'
    await score_catalog_and_persist(session, catalog_id)

    fx_rate = STORE_FX_TO_INR[body.store_currency]
    converted = body.store_currency != "INR"
    return {
        "catalog_id": catalog_id,
        "store_url": base_url,
        "merchant": host,
        "products": {
            "valid": len(validation.valid),
            "invalid": [
                {"row": e.row, "code": e.code, "message": e.message}
                for e in validation.errors
            ] + fetched.warnings,
            "capped_to": fetched.capped_to,
            "pages_fetched": fetched.pages_fetched,
        },
        "store_currency": body.store_currency,
        "fx": {
            "rate": fx_rate,
            "converted": converted,
            "note": (
                f"prices converted at 1 {body.store_currency} = ₹{fx_rate:.0f} [assumed FX]"
                if converted else "native INR prices"
            ),
        },
    }
