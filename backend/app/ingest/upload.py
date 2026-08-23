"""Upload ingestion — POST /api/uploads (SCHEMA §3.1.4, TECHSPEC §6.3).

Validation rules (exhaustive):
  E101 > 500 products · E102 payload > 5 MB · E103 missing required field
  E104 price out of range/non-integer · E105 description > 2,000 chars
  E106 duplicate product id · E107 < 5 valid products
Unknown fields are warned-and-stripped. Uploaded catalogs get tier='unknown'.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    DESCRIPTION_MAX_CHARS,
    PRICE_MAX_INR,
    PRICE_MIN_INR,
    TITLE_MAX_CHARS,
    UPLOAD_MAX_PRODUCTS,
    UPLOAD_MAX_PAYLOAD_MB,
    UPLOAD_MIN_PRODUCTS,
    UPLOAD_PURGE_DAYS,
)
from app.db.models import Catalog, Merchant, Product

UPLOAD_MERCHANT_NAME = "Workspace Merchant"

REQUIRED_FIELDS = ("id", "title", "price_inr", "description")
CSV_HEADERS = ["id", "title", "price_inr", "description", "image_url", "page_url"]


@dataclass
class RowError:
    row: int  # 1-based position in the payload
    code: str
    message: str


@dataclass
class ValidationResult:
    valid: list[dict] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)


class PayloadError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def check_payload_size(raw: bytes) -> None:
    if len(raw) > UPLOAD_MAX_PAYLOAD_MB * 1024 * 1024:
        raise PayloadError("E102", f"payload exceeds {UPLOAD_MAX_PAYLOAD_MB} MB")


def _validate_row(item: object, row_no: int, seen_ids: set[str], result: ValidationResult) -> None:
    if not isinstance(item, dict):
        result.errors.append(RowError(row_no, "E103", "row must be a JSON object"))
        return

    stripped = {k: v for k, v in item.items() if k in REQUIRED_FIELDS or k in ("image_url", "page_url", "structured_data")}
    unknown = sorted(set(item) - set(stripped))

    missing = [f for f in REQUIRED_FIELDS if f not in stripped or stripped[f] is None]
    if missing:
        result.errors.append(RowError(row_no, "E103", f"missing required field(s): {', '.join(missing)}"))
        return

    sku = stripped["id"]
    if not isinstance(sku, str) or not (1 <= len(sku) <= 30):
        result.errors.append(RowError(row_no, "E103", "id must be a string of 1-30 chars"))
        return
    if sku != sku.lower():
        result.errors.append(RowError(row_no, "E103", "sku ids must be lowercase (SCHEMA §1)"))
        return
    if sku in seen_ids:
        result.errors.append(RowError(row_no, "E106", f"duplicate product id: {sku}"))
        return

    title = stripped["title"]
    if not isinstance(title, str) or not (1 <= len(title) <= TITLE_MAX_CHARS):
        result.errors.append(RowError(row_no, "E103", f"title must be 1-{TITLE_MAX_CHARS} chars"))
        return

    price = stripped["price_inr"]
    if isinstance(price, bool) or not isinstance(price, int) or not (PRICE_MIN_INR <= price <= PRICE_MAX_INR):
        result.errors.append(
            RowError(row_no, "E104", f"price_inr must be an integer between {PRICE_MIN_INR} and {PRICE_MAX_INR}")
        )
        return

    description = stripped["description"]
    if not isinstance(description, str) or len(description) > DESCRIPTION_MAX_CHARS:
        result.errors.append(RowError(row_no, "E105", f"description exceeds {DESCRIPTION_MAX_CHARS} chars"))
        return

    sd = stripped.get("structured_data")
    if sd is not None and not isinstance(sd, dict):
        result.errors.append(RowError(row_no, "E103", "structured_data must be an object"))
        return

    seen_ids.add(sku)
    if unknown:
        result.errors.append(RowError(row_no, "W101", f"unknown field(s) stripped: {', '.join(unknown)}"))
    result.valid.append({
        "id": sku,
        "title": title,
        "price_inr": price,
        "description": description,
        "image_url": stripped.get("image_url"),
        "page_url": stripped.get("page_url"),
        "structured_data": sd or {},
    })


def validate_product_list(items: list) -> ValidationResult:
    if len(items) > UPLOAD_MAX_PRODUCTS:
        raise PayloadError("E101", f"more than {UPLOAD_MAX_PRODUCTS} products")
    result = ValidationResult()
    seen: set[str] = set()
    for i, item in enumerate(items, start=1):
        _validate_row(item, i, seen, result)
    if len(result.valid) < UPLOAD_MIN_PRODUCTS:
        raise PayloadError("E107", f"at least {UPLOAD_MIN_PRODUCTS} valid products required")
    return result


def parse_csv(raw: bytes) -> list[dict]:
    """RFC 4180 CSV, UTF-8 (BOM tolerated). Headers per SCHEMA §3.1.4."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PayloadError("E102", f"CSV must be UTF-8: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not set(CSV_HEADERS) <= set(reader.fieldnames):
        raise PayloadError("E103", f"CSV headers must include: {','.join(CSV_HEADERS)}")
    items: list[dict] = []
    for rec in reader:
        item: dict = {}
        for key in CSV_HEADERS:
            val = (rec.get(key) or "").strip()
            if key == "price_inr":
                try:
                    item[key] = int(val)
                except ValueError:
                    item[key] = val  # let E104 fire with a clear message
            elif val != "":
                item[key] = val
        # structured_data unsupported in CSV (computed by legibility pass later)
        items.append(item)
    return items


async def create_upload_catalog(session: AsyncSession, valid: list[dict],
                                merchant_name: str | None = None) -> str:
    """Store-connector imports pass their own merchant_name (the store host);
    file uploads keep the shared workspace merchant."""
    name = merchant_name or UPLOAD_MERCHANT_NAME
    merchant = await session.scalar(select(Merchant).where(Merchant.name == name))
    if merchant is None:
        merchant = Merchant(name=name)
        session.add(merchant)
        await session.flush()

    catalog = Catalog(merchant_id=merchant.id, source="upload", version=1)
    session.add(catalog)
    await session.flush()

    for item in valid:
        session.add(Product(
            catalog_id=catalog.id,
            sku=item["id"],
            title=item["title"],
            price_inr=item["price_inr"],
            description=item["description"],
            image_url=item.get("image_url"),
            page_url=item.get("page_url"),
            tier="unknown",
            structured_data=item.get("structured_data") or {},
        ))
    await session.commit()
    return catalog.id


# --- Purge job (TECHSPEC §6.3: uploaded catalogs auto-purge after 7 days) ---
async def purge_expired_uploads(session: AsyncSession, days: int = UPLOAD_PURGE_DAYS,
                                dry_run: bool = False) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    expired = (
        (await session.execute(
            select(Catalog.id).where(Catalog.source == "upload", Catalog.created_at < cutoff)
        ))
        .scalars()
        .all()
    )
    if dry_run or not expired:
        return list(expired)

    from app.db.models import Metric, Remediation, Run, Trial

    for catalog_id in expired:
        run_ids = (await session.execute(select(Run.id).where(Run.catalog_id == catalog_id))).scalars().all()
        if run_ids:
            await session.execute(delete(Trial).where(Trial.run_id.in_(run_ids)))
            await session.execute(delete(Metric).where(Metric.run_id.in_(run_ids)))
            await session.execute(delete(Remediation).where(Remediation.run_id.in_(run_ids)))
            await session.execute(delete(Run).where(Run.id.in_(run_ids)))
        await session.execute(delete(Product).where(Product.catalog_id == catalog_id))
        await session.execute(delete(Catalog).where(Catalog.id == catalog_id))
    await session.commit()
    return list(expired)


def parse_upload_body(raw: bytes, kind: str) -> list[dict]:
    """Parse an upload payload. `kind` is 'json' or 'csv' (endpoint routes by content-type)."""
    check_payload_size(raw)
    if kind == "csv":
        return parse_csv(raw)
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadError("E103", "body must be a JSON array of products") from exc
    if isinstance(data, dict) and "products" in data:
        data = data["products"]
    if not isinstance(data, list):
        raise PayloadError("E103", "upload must be a JSON array of products")
    return data
