# BUILDLOG — AgentAudit engineering log

One entry per day, five lines max (shipped / broke / spent / decided / tomorrow's risk).
This is a deliverable, not a diary — it demonstrates engineering process to judges.

---

## Day 0 — Scaffold, DB, pins (Aug 21)

- **Shipped:** repo scaffold; FastAPI `/healthz` + CORS + POST rate-limit (E602); ORM mirror of SCHEMA §6 DDL (`backend/db/init.sql` verbatim for Postgres); `constants.py` from SCHEMA §12; `models.yaml` pins (3 bulk + 2 flagship) with boot validation; scoring config; Makefile; CI (PR lint+test) + nightly placeholder; `.env.example` with all 7 vars incl. `RAZORPAY_WEBHOOK_SECRET` (IP-4); test suite green.
- **Broke:** nothing yet.
- **Spent:** $0.
- **Decided:** (1) ORM stores UUIDs as CHAR(36) strings for SQLite/Postgres portability — Postgres deployments still use native UUID via init.sql; sync enforced by tests. (2) Demo-store listing title for sku_023 is bare `"Daypack"` per the normative tier matrix (TECHSPEC §5.2); the human-facing name "TrailBuddy Daypack 22L" is carried as display metadata so F4/F5 headers match APPFLOW while agents see the starved-tier listing. (3) Local Python is 3.13 (docs target 3.12) — code kept 3.12-compatible; CI pins 3.12.
- **Tomorrow's risk:** models.yaml snapshot IDs are best-known values — must be re-pinned against OpenRouter `/models` the moment the API key exists (prerequisite P1).

---

## Day 1 — Demo store (Aug 21)

- **Shipped:** deterministic generator (seed 42) → 40 products / 4 categories / tiers 10-20-10; `[rich, medium, starved, medium]×10` baseline block; anchors sku_007 (modal), sku_017 (verbatim schema example), sku_023 @ position 19; starved SKUs pinned at category price-ladder deciles 5–7; static site (catalog.json, p/{sku}.html with JSON-LD only for rich/medium, llms.txt); demo loader idempotent; `GET /catalog`, `GET /catalog/{sku}`.
- **Broke:** price-decile assertion caught bottles/headphones starved SKUs outside deciles 5–7 — fixed prices before anything depended on it.
- **Spent:** $0.
- **Decided:** sku_023's listing title is bare `"Daypack"` (tier matrix is normative); human-facing "TrailBuddy Daypack 22L" rides in structured_data.display_name so F4/F5 headers still match APPFLOW.
- **Tomorrow's risk:** uploads validation matrix breadth.

## Day 2 — Uploads (Aug 21)

- **Shipped:** POST /api/uploads (JSON array or CSV file), E101–E107 all enforced + W101 unknown-field strip warnings; partial-valid accepted (38/40 fixture test); tier forced `unknown`; purge script (`scripts/purge_uploads.py`, dry-run flag).
- **Broke:** ruff flagged an unused walrus hack — replaced with a clean sqlalchemy.text count.
- **Spent:** $0.
- **Decided:** E107 (<5 products) applies to *valid* row count, not payload length.
- **Tomorrow's risk:** prompt/template fidelity.

## Day 3 — Engine core (Aug 21)

- **Shipped:** 20 persona JSONs verbatim from SCHEMA §3.2; condition matrix enumerating exactly 640 trials (400 null / 240 forced) with sha256 seed derivations; prompt templates exact per TECHSPEC §7.3 ("price on request" rendering for starved); framing_variants.json hand-authored (10 SKUs, 3 rich / 4 medium / 3 starved, both anchors included, information-equivalent rewrites only); OpenRouter client (semaphore 10, retries 1s/2s/4s, circuit breaker 10-fail/60s half-open, cost ledger); parse pipeline + golden files.
- **Broke:** nothing — golden files caught decline-without-JSON ≠ null choice early.
- **Spent:** $0.
- **Decided:** pricing table keyed by engine id lives in client.py; models.yaml stays schema-pure.
- **Tomorrow's risk:** runner state machine correctness under abort paths.

## Day 4 — Runner (Aug 21)

- **Shipped:** full-matrix runner (queued→running→done/partial/failed); response cache keyed (prompt_hash, model_version); cost-cap abort → `partial` with E203 event; batched DB flush every 40 trials; C2 shuffle seeds shared across personas/models; C3 presents 10-SKU framing subset in baseline-relative order, B applies variant copy. Integration: mocked 640-trial run <60 s, unchanged-catalog rerun = 100% cache hits / $0 marginal.
- **Broke:** our own DB CHECK (C-2 choice semantics) rejected the fake provider's nulls on forced trials — twice. Root cause #2 was a real trap: P20's task text contains "or return", so prose-sniffing for null permission misfires; switched to detecting the literal `{"product_id": null` schema clause.
- **Spent:** $0.
- **Decided:** demo catalogs take baseline order from the committed fixture (sku_023@19 preserved); other catalogs fall back to sku-sorted.
- **Tomorrow's risk:** stats correctness (the credibility core).

## Day 6 — Statistics + validation suite (Aug 21)

- **Shipped:** metrics M-1…M-6 pure functions (HHI_norm pooled+per-model, top-3 capture/lift/permutation p, framing Δ per product+mean, F_task Wilson CI + per-persona nulls, cosine stability matrix/band, demand shares); persona-cluster bootstrap B=2000 percentile-95 propagating a score CI; V1–V6 planted-bias suite green via `make validate`; `POST /api/audit` (202 queued, background run), `GET /api/audit/{id}`, `GET …/metrics` persisting headline rows to `metrics`.
- **Broke:** permutation test v1 shuffled the observed slot-value array — value multiset survives shuffling, so p=1.0 always. Reimplemented the TECHSPEC §8.2 null correctly (choices land in uniformly random slots). Exactly what the planted-bias suite exists to catch.
- **Spent:** $0.
- **Decided:** primary metrics pool bulk models only; flagship reported but excluded from pooling; completeness component defaults 0.0 until legibility lands (Day 7).
- **Tomorrow's risk:** legibility checklist scoring + revenue model inputs.

> Day 5 (first live 640-trial run) is intentionally deferred until OPENROUTER_API_KEY exists — all mocked paths are proven.
