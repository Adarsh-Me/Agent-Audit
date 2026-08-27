"""Canonical constants — cross-document registry mirroring SCHEMA §12.

Rule (SCHEMA §13.4): these values must never appear as magic numbers elsewhere.
Import from here (or scoring/config.yaml, which tests keep in sync with this file).
"""
from typing import Final

# --- Run matrix (TECHSPEC §22 / §7.2) ---
# SINGLE-MODEL MODE 2026-08-26 (owner call): audit runs use ONLY ONE provider+
# model — see models.yaml for the current pin. Matrix: 1 bulk × 200 +
# 1 flagship × 20 = 220 trials. Revert path documented in git history.
TRIALS_PER_FULL_RUN: Final = 220  # 200 bulk + 20 flagship
BULK_MODEL_COUNT: Final = 1
FLAGSHIP_MODEL_COUNT: Final = 1
TRIALS_PER_BULK_MODEL: Final = 200  # C1 60 + C2 60 + C3 80
NULL_ALLOWED_TRIALS: Final = 140  # C1 60 + C2 60 + flagship 20
FORCED_TRIALS: Final = 80  # C3
CATALOG_SIZE_DEMO: Final = 40
PERSONA_COUNT: Final = 20
NULL_PLAUSIBLE_PERSONAS: Final = ("P04", "P09", "P10", "P20")
FLAGSHIP_CHECKOUT_PERSONA: Final = "P07"  # Deal Hunter (TECHSPEC §12.3)

# --- Condition codes (SCHEMA §2.2, exhaustive) ---
CONDITION_CODES: Final = (
    "C1-s1", "C1-s2", "C1-s3",
    "C2-s1", "C2-s2", "C2-s3",
    "C3-A-s1", "C3-A-s2",
    "C3-B-s1", "C3-B-s2",
)
NULL_ALLOWED_CONDITIONS: Final = ("C1-s1", "C1-s2", "C1-s3", "C2-s1", "C2-s2", "C2-s3")
FORCED_CONDITIONS: Final = ("C3-A-s1", "C3-A-s2", "C3-B-s1", "C3-B-s2")

# --- Model ids (engine ids; provider strings live only in models.yaml) ---
# SINGLE-MODEL MODE 2026-08-26 (owner call): one provider+model only — OpenCode
# Zen x-preview-f-free (same-day chain: mimo → tokenbom deepseek → xpreview).
# Keep models.yaml lists identical (test_model_registry asserts it).
BULK_MODEL_IDS: Final = ("sarvam-105b",)
FLAGSHIP_MODEL_IDS: Final = ("sarvam-105b-flagship",)

# --- Statistics (TECHSPEC §8) ---
BOOTSTRAP_REPLICATES: Final = 2000
BOOTSTRAP_CLUSTER: Final = "persona"
CI_PERCENTILE: Final = 95
PERMUTATION_REPLICATES: Final = 10000
WILSON_Z: Final = 1.96
# Invisibility rule (errata E-3): flagged iff CI_upper95(share_i) < 1/N
FAIR_SHARE_RULE: Final = "ci_upper_below_1_over_n"

# --- AgentReady Score (TECHSPEC §9.1) ---
SCORE_WEIGHTS: Final = {
    "visibility": 0.20,
    "stability": 0.20,
    "position_indep": 0.20,
    "coverage": 0.20,
    "data_completeness": 0.20,
}
SCORE_BANDS: Final = ((80, "agent-ready"), (60, "partially visible"), (0, "significant leakage"))

# --- Revenue model (PRD §8.6 / TECHSPEC §10) ---
GMV_DEFAULT_INR: Final = 800_000
GMV_MIN_INR: Final = 10_000
S_AGENT_SLIDER: Final = (0.01, 0.05, 0.10, 0.20)
S_AGENT_DEFAULT: Final = 0.20

# --- Cost guards ---
COST_CAP_USD: Final = 30.0
PROJECT_COST_CAP_USD: Final = 35.0

# --- Agent money-policy (SAFETY.md) — what the shopping agent may purchase ---
# Per-payment-link ceiling. Rationale: the demo catalog's median price is ~₹1,199
# and its "rich" anchors top out at ₹999, so ₹2,000 covers every realistic demo
# checkout while blocking high-ticket SKUs (₹2,499+) from autonomous purchase.
AGENT_SPEND_CAP_INR: Final = 2_000
# Default purchasable allowlist: exactly the demo-store catalog ids (sku_001 …
# sku_040, matching demo-store/generate.py). Closed list — uploaded-catalog or
# arbitrary skus need an explicit merchant override via AGENT_ALLOWED_SKUS.
AGENT_DEFAULT_ALLOWED_SKUS: Final = tuple(
    f"sku_{i:03d}" for i in range(1, CATALOG_SIZE_DEMO + 1)
)

# --- Upload validation (SCHEMA §3.1.4) ---
UPLOAD_MAX_PRODUCTS: Final = 500   # E101
UPLOAD_MIN_PRODUCTS: Final = 5     # E107
UPLOAD_MAX_PAYLOAD_MB: Final = 5   # E102
PRICE_MIN_INR: Final = 1           # E104
PRICE_MAX_INR: Final = 10_000_000  # E104
DESCRIPTION_MAX_CHARS: Final = 2_000  # E105
TITLE_MAX_CHARS: Final = 200
UPLOAD_PURGE_DAYS: Final = 7

# --- Store import (public Shopify /products.json; SCHEMA §3.1.4 extension) ---
# The public feed hard-caps at 30 products per request regardless of ?limit=,
# so importers paginate ?page=1..4 until the cap or an empty page.
STORE_PAGE_SIZE: Final = 30
STORE_PAGE_LIMIT: Final = 4
STORE_MAX_PRODUCTS: Final = 100
# FX is a labeled assumption, never a measured quantity: every affected rupee
# figure renders with an [assumed FX] chip in the UI (PRD §19 claim discipline).
STORE_FX_TO_INR: Final = {"INR": 1.0, "USD": 83.0, "EUR": 90.0, "GBP": 105.0}
# Identified client UA — bare httpx defaults are refused by Shopify's edge (403).
STORE_USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AgentAudit/1.0 "
    "(+https://github.com/Adarsh-Me/Agent-Audit)"
)

# --- Engine execution semantics (TECHSPEC §7.4) ---
PARSE_RETRIES: Final = 3
RETRY_BACKOFF_S: Final = (1, 2, 4)
ENGINE_CONCURRENCY: Final = 10
CIRCUIT_BREAKER_THRESHOLD: Final = 10
CIRCUIT_BREAKER_COOLDOWN_S: Final = 60
TEMPERATURE: Final = 1.0
# Unbreakable wall-clock ceiling for ONE TRIAL's whole live-call phase (all
# attempts, backoffs and pacing included). The per-attempt cap in client.py can
# be defeated when a proxied connection's cancellation never completes — the
# 2026-08-22 nemotron block froze for hours exactly that way. The trial-level
# cap runs the call as a shielded task and ABANDONS it on timeout, so the run
# always makes forward progress (degraded to a counted provider failure).
TRIAL_WALL_CAP_S: Final = 300.0

# --- API / SSE ---
RATE_LIMIT_POST_RPM: Final = 60  # E602
SSE_HEARTBEAT_S: Final = 15
WEBHOOK_BADGE_TARGET_S: Final = 5

# --- Demo store fixture (TECHSPEC §5 / SCHEMA §5.3) ---
DEMO_SEED: Final = 42
TIER_BLOCK: Final = ("rich", "medium", "starved", "medium")  # ×10 baseline order
DECORRELATION_RHO_MAX: Final = 0.15
FRAMING_SUBSET_SIZE: Final = 10
FRAMING_STRATIFICATION: Final = {"rich": 3, "medium": 4, "starved": 3}
DEMO_ANCHORS: Final = {
    "sku_007": {"name": "HydroMax Elite 750ml", "tier": "rich", "category": "bottles"},
    "sku_017": {"name": "AquaSteel Pro 1L", "tier": "rich", "category": "bottles"},
    "sku_023": {
        "name": "TrailBuddy Daypack 22L",
        "tier": "starved",
        "category": "backpacks",
        "baseline_position": 19,
        "price_inr": 1899,
    },
}

# --- Error taxonomy (SCHEMA §11, exhaustive) ---
ERROR_CODES: Final = {
    "E101": ("ingestion", 400, "> 500 products"),
    "E102": ("ingestion", 400, "payload > 5 MB"),
    "E103": ("ingestion", 400, "missing required field"),
    "E104": ("ingestion", 400, "price out of range"),
    "E105": ("ingestion", 400, "description > 2,000 chars"),
    "E106": ("ingestion", 400, "duplicate product id"),
    "E107": ("ingestion", 400, "< 5 products"),
    "E110": ("setup", 400, "GMV < ₹10,000"),
    "E201": ("engine", 502, "provider timeout"),
    "E202": ("engine", 502, "circuit breaker open"),
    "E203": ("engine", None, "cost cap reached (run → partial; not an HTTP error)"),
    "E301": ("stats", 500, "metric computation failure"),
    "E401": ("remediation", 409, "rerun before mirror approval"),
    "E402": ("scoring", 422, "config invalid (weights ≠ 1.0)"),
    "E501": ("razorpay", 400, "webhook signature mismatch"),
    "E502": ("razorpay", 502, "payment link creation failed"),
    "E503": ("razorpay", 403, "agent spend cap exceeded (SAFETY.md)"),
    "E504": ("razorpay", 403, "sku not on agent purchasable whitelist (SAFETY.md)"),
    "E505": ("razorpay", 403, "live Razorpay keys refused — test mode only (SAFETY.md)"),
    "E601": ("api", 404, "run/catalog not found"),
    "E602": ("api", 429, "rate limited"),
}

# --- Run lifecycle (SCHEMA §2.5) ---
RUN_STATUSES: Final = ("queued", "running", "done", "partial", "failed")
TERMINAL_RUN_STATUSES: Final = ("done", "partial", "failed")


def validate_score_weights(weights: dict[str, float]) -> None:
    """Boot-check per SCHEMA §4.2 — weights must sum to 1.0 else E402."""
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"E402: score weights must sum to 1.0 (got {total})")
    if set(weights) != set(SCORE_WEIGHTS):
        raise ValueError(f"E402: unexpected score components: {sorted(weights)}")
