"""Response parse pipeline — TECHSPEC §7.4 / golden-file outcomes.

Pipeline: strip code fences → extract first JSON object → json.loads →
validate product_id ∈ catalog ∪ {None}. Violations retry; after 3 → parse_ok=false,
excluded from metrics, counted in per-model parse-rate.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class ParsedChoice:
    choice: str | None  # sku or None (decline) — meaningful only when parse_ok
    reason: str | None
    parse_ok: bool
    error: str | None = None


def strip_fences(text: str) -> str:
    m = _FENCE_RE.search(text)
    return m.group(1) if m else text


def extract_json(text: str) -> str | None:
    m = _OBJ_RE.search(strip_fences(text))
    return m.group(0) if m else None


def parse_response(raw: str, valid_skus: set[str]) -> ParsedChoice:
    blob = extract_json(raw)
    if blob is None:
        return ParsedChoice(None, None, False, "no JSON object found")
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        return ParsedChoice(None, None, False, f"invalid JSON: {exc}")
    if not isinstance(data, dict) or "product_id" not in data:
        return ParsedChoice(None, None, False, "missing product_id key")
    pid = data["product_id"]
    reason = data.get("reason")
    if pid is None:
        return ParsedChoice(None, reason if isinstance(reason, str) else None, True)
    if not isinstance(pid, str) or pid not in valid_skus:
        return ParsedChoice(None, None, False, f"product_id not in catalog: {pid!r}")
    return ParsedChoice(pid, reason if isinstance(reason, str) else None, True)
