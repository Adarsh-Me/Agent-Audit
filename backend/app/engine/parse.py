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
_PID_RE = re.compile(r'"product_id"\s*:\s*(null|"[^"]*")')


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


def parse_response(raw: str, valid_skus: set[str],
                   ordinal_map: dict[str, str] | None = None,
                   null_allowed: bool = True) -> ParsedChoice:
    """Parse a trial response into a catalog choice.

    ordinal_map: {"1": sku, ..., "40": sku} for the presented order — models that
    ignore the bracket-id instruction and answer with the line number still get
    measured instead of discarded (live-fire fix 2026-08-22).

    null_allowed=False (forced-choice C3 conditions): a "product_id": null answer
    is a PARSE FAILURE that feeds the retry loop, not a valid decline — a silent
    ok-null here poisoned run ba545a33 (2026-08-23 post-mortem).
    """
    if not isinstance(raw, str):
        return ParsedChoice(None, None, False, "empty response")
    blob = extract_json(raw)
    data: object | None = None
    if blob is not None:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            data = None  # fall through to salvage
    pid: object = "<unset>"
    reason: str | None = None
    if isinstance(data, dict) and "product_id" in data:
        pid = data["product_id"]
        r = data.get("reason")
        reason = r if isinstance(r, str) else None
    else:
        # Salvage: JSON malformed (e.g. unescaped quote inside the reason string)
        # but the product_id field itself is intact. Choice is what's scored;
        # the reason is dropped rather than losing the trial.
        m = _PID_RE.search(raw)
        if m is None:
            return ParsedChoice(None, None, False, "no JSON object found")
        tok = m.group(1)
        pid = None if tok == "null" else tok.strip('"')
        reason = None

    def finish(choice: object) -> ParsedChoice:
        if choice is None:
            if not null_allowed:
                return ParsedChoice(
                    None, reason, False, "declined although choice was forced")
            return ParsedChoice(None, reason, True)
        if isinstance(choice, str) and choice in valid_skus:
            return ParsedChoice(choice, reason, True)
        if ordinal_map and isinstance(choice, str) and choice in ordinal_map:
            return ParsedChoice(ordinal_map[choice], reason, True)
        return ParsedChoice(
            None, None, False, f"product_id not in catalog: {choice!r}")

    return finish(pid)
