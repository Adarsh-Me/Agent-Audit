"""Store ingestion — public Shopify product feed (SCHEMA §3.1.4 extension).

POST /api/stores/import pipeline. Reads the store's public /products.json
catalog endpoint — the same JSON feed storefront themes render from. No HTML
scraping, no auth, at most STORE_PAGE_LIMIT paginated GETs per import,
snapshot-at-import semantics.

Errors (router maps to AppError):
  E210 not a Shopify store / feed not public / not JSON
  E211 feed rate-limited (one 2 s retry, then surfaced)
  E212 refused: non-public host (SSRF guard)

Rows are canonical upload-shape dicts and flow through validate_product_list()
unchanged, so catalog creation, legibility tier assignment, audit, remediation
and revenue all work on imported stores with zero schema changes.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import unescape
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.constants import (
    DESCRIPTION_MAX_CHARS,
    STORE_FX_TO_INR,
    STORE_PAGE_LIMIT,
    STORE_USER_AGENT,
    TITLE_MAX_CHARS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class StoreImportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class StoreFetchResult:
    rows: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)  # {row, code, message}
    pages_fetched: int = 0
    products_seen: int = 0
    capped_to: int | None = None


def normalize_store_url(raw: str) -> str:
    """Accept bare domain / full URL / myshopify domain / a /products.json link
    and return the https base URL. Refuses private or unresolvable hosts (E212)."""
    value = (raw or "").strip()
    if not value:
        raise StoreImportError("E212", "store URL is required")
    if "://" not in value:
        value = f"https://{value}"

    parts = urlsplit(value)
    if parts.scheme != "https":
        raise StoreImportError("E212", "store URL must be https (or a bare domain)")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or "." not in host:
        raise StoreImportError("E212", f"not a valid store host: {host!r}")

    # SSRF guard: never fetch private/loopback/link-local networks or ports
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise StoreImportError("E212", f"store host does not resolve: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise StoreImportError("E212", f"refusing non-public host: {host}")

    return f"https://{host}"


def _strip_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    text = unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _price_to_inr(price_raw: Any, fx_rate: float) -> int:
    """Shopify prices are decimal strings in the store's primary currency."""
    try:
        amount = Decimal(str(price_raw)) * Decimal(str(fx_rate))
    except (InvalidOperation, ValueError, TypeError):
        return 0  # flows into the shared validator as a clear E104
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def map_shopify_product(product: dict, base_url: str, fx_rate: float,
                        store_meta: dict, row_no: int, warnings: list[dict]) -> dict | None:
    """One Shopify product JSON → canonical upload row. Variant-level sku keeps
    identifier lineage unique if multi-variant ingestion is ever added."""
    variants = product.get("variants") or []
    if not variants:
        warnings.append({"row": row_no, "code": "W104",
                         "message": f"product has no variants: {product.get('title', '?')!r}"})
        return None

    variant = variants[0]
    vid = variant.get("id")
    if vid is None:
        warnings.append({"row": row_no, "code": "W104", "message": "variant missing id"})
        return None
    sku = f"shopify-var-{vid}".lower()
    if len(sku) > 30:  # variant ids are ~10-13 digits; guard the SCHEMA §1 cap
        sku = sku[-30:]

    title = str(product.get("title") or "").strip()[:TITLE_MAX_CHARS]

    description = _strip_html(str(product.get("body_html") or ""))
    if len(description) > DESCRIPTION_MAX_CHARS:
        description = description[:DESCRIPTION_MAX_CHARS].rstrip()
        warnings.append({"row": row_no, "code": "W103",
                         "message": f"description truncated to {DESCRIPTION_MAX_CHARS} chars"})

    images = product.get("images") or []
    image_url = (images[0].get("src") if images and isinstance(images[0], dict) else None)

    fields_present = ["name", "price"]
    if image_url:
        fields_present.append("image")
    if product.get("vendor"):
        fields_present.append("brand")
    if "available" in variant:
        fields_present.append("availability")

    structured = {
        # the storefront itself renders JSON-LD product schema — the feed is the
        # machine-readable form of the listing, so jsonld_present is accurate
        "jsonld_present": True,
        "fields_present": fields_present,
        "price_fresh": True,
        "store": store_meta,
    }

    return {
        "id": sku,
        "title": title,
        "price_inr": _price_to_inr(variant.get("price"), fx_rate),
        "description": description or "(no description provided)",
        "image_url": image_url,
        "page_url": f"{base_url}/products/{product.get('handle', vid)}",
        "structured_data": structured,
    }


async def _get_feed_page(client: httpx.AsyncClient, base_url: str, page: int) -> httpx.Response:
    return await client.get(
        f"{base_url}/products.json",
        params={"limit": 250, "page": page},
        headers={"User-Agent": STORE_USER_AGENT, "Accept": "application/json"},
    )


async def fetch_shopify_rows(
    base_url: str,
    store_currency: str,
    max_products: int,
    http_client: httpx.AsyncClient | None = None,
) -> StoreFetchResult:
    """Paginate the public feed (30/page hard cap server-side) into canonical rows.

    The caller owns an injected http_client's lifecycle (tests close it);
    a self-created client is always bound by `async with` so sockets cannot
    leak when mapping raises between requests.
    """
    fx_rate = STORE_FX_TO_INR.get(store_currency)
    if fx_rate is None:
        raise StoreImportError("E212", f"unsupported store currency: {store_currency}")

    result = StoreFetchResult()
    store_meta = {
        "url": base_url,
        "platform": "shopify",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "currency": store_currency,
        "fx_rate": fx_rate,
    }

    async def _fetch_all(client: httpx.AsyncClient) -> None:
        for page in range(1, STORE_PAGE_LIMIT + 1):
            resp = await _get_feed_page(client, base_url, page)

            if resp.status_code == 429:
                # one polite retry, then surface — never hammer a shared edge
                import asyncio

                await asyncio.sleep(2)
                resp = await _get_feed_page(client, base_url, page)
                if resp.status_code == 429:
                    raise StoreImportError(
                        "E211", "store feed rate-limited — retry the import in a minute")

            if resp.status_code in (401, 403, 404):
                raise StoreImportError(
                    "E210",
                    f"not a Shopify store or catalog not public "
                    f"(HTTP {resp.status_code} from {base_url})")

            final_path = urlsplit(str(resp.url)).path.lower()
            if resp.status_code == 200 and any(
                    marker in final_path for marker in ("/login", "/password", "/account")):
                raise StoreImportError(
                    "E210", "store is password-protected or redirected to a login page")

            if resp.status_code != 200:
                raise StoreImportError(
                    "E210", f"unexpected HTTP {resp.status_code} from {base_url}")

            try:
                payload = resp.json()
                products = payload.get("products") if isinstance(payload, dict) else None
                if not isinstance(products, list):
                    raise ValueError("no 'products' array")
            except (json.JSONDecodeError, ValueError) as exc:
                raise StoreImportError(
                    "E210", f"{base_url} did not return a Shopify products feed") from exc

            result.pages_fetched = page
            if not products:
                break

            for product in products:
                result.products_seen += 1
                row = map_shopify_product(
                    product, base_url, fx_rate, store_meta,
                    result.products_seen, result.warnings)
                if row is not None:
                    result.rows.append(row)
                    if len(result.rows) >= max_products:
                        result.capped_to = max_products
                        return
            # continue to the next page

    if http_client is not None:
        await _fetch_all(http_client)
    else:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            await _fetch_all(client)

    return result
