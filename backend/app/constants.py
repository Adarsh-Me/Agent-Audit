"""Canonical constants — cross-document registry mirroring SCHEMA §12.

Rule (SCHEMA §13.4): these values must never appear as magic numbers elsewhere.
Import from here (or scoring/config.yaml, which tests keep in sync with this file).
"""
from typing import Final

# --- Run matrix (TECHSPEC §22 / §7.2) ---
TRIALS_PER_FULL_RUN: Final = 640  # 600 bulk + 40 flagship
BULK_MODEL_COUNT: Final = 3
FLAGSHIP_MODEL_COUNT: Final = 2
TRIALS_PER_BULK_MODEL: Final = 200  # C1 60 + C2 60 + C3 80
NULL_ALLOWED_TRIALS: Final = 400  # C1 180 + C2 180 + flagship 40
FORCED_TRIALS: Final = 240  # C3
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
BULK_MODEL_IDS: Final = ("gpt4o-mini", "gemini-flash", "claude-haiku")
FLAGSHIP_MODEL_IDS: Final = ("gpt4o", "gemini-pro")

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

# --- Upload validation (SCHEMA §3.1.4) ---
UPLOAD_MAX_PRODUCTS: Final = 500   # E101
UPLOAD_MIN_PRODUCTS: Final = 5     # E107
UPLOAD_MAX_PAYLOAD_MB: Final = 5   # E102
PRICE_MIN_INR: Final = 1           # E104
PRICE_MAX_INR: Final = 10_000_000  # E104
DESCRIPTION_MAX_CHARS: Final = 2_000  # E105
TITLE_MAX_CHARS: Final = 200
UPLOAD_PURGE_DAYS: Final = 7

# --- Engine execution semantics (TECHSPEC §7.4) ---
PARSE_RETRIES: Final = 3
RETRY_BACKOFF_S: Final = (1, 2, 4)
ENGINE_CONCURRENCY: Final = 10
CIRCUIT_BREAKER_THRESHOLD: Final = 10
CIRCUIT_BREAKER_COOLDOWN_S: Final = 60
TEMPERATURE: Final = 1.0

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
