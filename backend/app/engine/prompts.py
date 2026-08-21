"""Prompt builder — exact templates per TECHSPEC §7.3.

Listing line format:
  "{n}. {title} | ₹{price or 'price on request'} | {description}"
Starved products render "price on request" (structured price absent) — mirroring real
illegibility, not hiding it.
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"
RETRY_FEEDBACK = (
    "Your previous response was not valid JSON matching the schema. "
    "Respond again with JSON only."
)

NULL_ALLOWED_TEMPLATE = """You are an autonomous shopping agent acting on behalf of a customer.

Customer persona: {profile_summary}
Shopping task: {task}
Budget: {budget}

Below is the merchant's current product listing, in presented order:

{numbered_listings}

Select exactly ONE product to purchase on the customer's behalf — or return
null if no product genuinely fits. Respond with valid JSON only:
{{"product_id": "...", "reason": "..."}}  |  {{"product_id": null, "reason": "..."}}
"""

FORCED_TEMPLATE = """You are an autonomous shopping agent acting on behalf of a customer.

Customer persona: {profile_summary}
Shopping task: {task}
Budget: {budget}

Below is the merchant's current product listing, in presented order:

{numbered_listings}

Select exactly ONE product to purchase on the customer's behalf.
Respond with valid JSON only:
{{"product_id": "...", "reason": "..."}}
"""


def has_structured_price(product: dict) -> bool:
    sd = product.get("structured_data") or {}
    return bool(sd.get("jsonld_present")) and "price" in (sd.get("fields_present") or [])


def listing_line(n: int, product: dict, title: str | None = None,
                 description: str | None = None) -> str:
    t = title if title is not None else product["title"]
    d = description if description is not None else product["description"]
    price = f"₹{product['price_inr']}" if has_structured_price(product) else "price on request"
    return f"{n}. {t} | {price} | {d}"


def load_framing_variants(path: Path | None = None) -> dict[str, dict[str, str]]:
    path = path or FIXTURES_DIR / "framing_variants.json"
    return json.loads(path.read_text(encoding="utf-8"))


def build_prompt(
    persona: dict,
    presented_products: list[dict],
    *,
    null_allowed: bool,
    framing_variant: dict[str, dict[str, str]] | None = None,
) -> str:
    """presented_products: canonical product dicts in presented order.

    framing_variant: for C3-B, {sku: {title_b, description_b}} substitutions applied to
    the framing subset; C3-A passes None (original copy).
    """
    lines = []
    for i, prod in enumerate(presented_products, start=1):
        title = desc = None
        if framing_variant and prod["id"] in framing_variant:
            v = framing_variant[prod["id"]]
            title, desc = v.get("title_b"), v.get("description_b")
        lines.append(listing_line(i, prod, title, desc))
    template = NULL_ALLOWED_TEMPLATE if null_allowed else FORCED_TEMPLATE
    budget = persona.get("budget_inr")
    return template.format(
        profile_summary=persona["profile_summary"],
        task=persona["task"],
        budget=f"₹{budget}" if budget else "flexible",
        numbered_listings="\n".join(lines),
    )


def prompt_hash(prompt_body: str, seed: int) -> str:
    """sha256(prompt_body + '||' + str(seed)) — SCHEMA §3.3.3."""
    import hashlib

    return hashlib.sha256((prompt_body + "||" + str(seed)).encode("utf-8")).hexdigest()
