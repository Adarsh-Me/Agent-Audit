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

---

## Day 7+8 — Legibility, score wiring, revenue, SSE (Aug 21)

- **Shipped:** legibility composite (structured checklist 0.4 + title 0.3 + description 0.3) with deterministic heuristic fallback behind an LLM-judge slot; C-4 tier assignment for uploads; data_completeness now feeds the real mean composite into score computation; `POST /api/legibility/{catalog_id}`; `GET /api/report/{run_id}`; revenue model (RaR = GMV × s_agent × F_task, Recoverable = GMV × s_agent × ΔF) with per-input source labels and CI bounds from Wilson/bootstrap; SSE event bus + `/api/stream/{run_id}` with 15s heartbeat.
- **Broke:** first SSE generator fell into the heartbeat loop for finished runs — infinite stream, hung the test suite. Terminal events now return immediately.
- **Spent:** $0.
- **Decided:** heuristic quality scorer is documented as fallback, never silently mixed with LLM mode; UI will label which produced the numbers.
- **Tomorrow's risk:** remediation loop gating correctness.

## Day 9+10 — Remediation loop + delta (Aug 21)

- **Shipped:** fix proposals — curated afters for the demo's 10 starved SKUs (sku_023 matches APPFLOW verbatim), honest `[seller to confirm]` templates for uploads; generate/list/review/mirror endpoints; mirror catalog v=n+1 with SC-2 parentage; E401 rerun gate (no mirror while rows pending); verified re-run endpoint flow; delta endpoint (per-SKU share changes, ΔF with paired bootstrap CI B=800, Recoverable at slider, verdict string); manifest recorder (`scripts/record_manifest.py` → demo/manifest.json) + G12 `make demo-check` verifier.
- **Broke:** m2_position crashed on perms=0 inside bootstrap resamples — added explicit skip returning p_value=None.
- **Spent:** $0.
- **Decided:** identical-prompt reruns legitimately serve from cache ($0 marginal); a remediated rerun changes every listing line so it re-bills by construction (SC-3) — integration test asserts >600 fresh of 640.
- **Tomorrow's risk:** frontend fidelity to APPFLOW copy.

## Day 13 — Razorpay + agent checkout + MCP (Aug 21)

- **Shipped:** Razorpay test-mode client (payment links, idempotency keys, injectable transport); payments endpoints — idempotent link creation keyed "agentaudit:{run}:{sku}", status polling for the F8 badge; HMAC-SHA256 webhook verification with E501 on mismatch and webhook_events dedupe (SC-1 entity_key); payment_link.captured flips Payment.status → badge closes; `scripts/agent_checkout.py` (prefers mirror catalog, explainable value pick); stdio MCP server (zero-dep Node) exposing audit_status / get_report / create_payment_link.
- **Broke:** nothing — HMAC math tested against hand-computed digests before any live call.
- **Spent:** $0 (all Razorpay traffic mocked).
- **Decided:** secrets stay server-side; frontend/MCP/agents only ever see short_url.
- **Tomorrow's risk:** e2e smoke + final polish.

## Day 14 — Frontend, payments reconciliation, e2e smoke (Aug 22)

- **Shipped:** full frontend src/ committed — home, audit flow, results/revenue/fixes, delta, agent checkout; api.ts typed against the real router shapes; Ci/Dial/Bits components. Payments contract reconciled on both sides: new `RazorpayClient.fetch_payment_link` (GET /v1/payment_links/{id}) so idempotent replays always return a fresh short_url (frozen DDL has no short_url column); unreachable Razorpay degrades replay to `short_url:""` instead of a 500; FE checkout polls the real status shape (`{payments[], captured}`) and the stale "payments API not implemented" branch is gone. HTTP-level e2e smoke vs production builds: catalog (+baseline order), 404 envelopes (audit/report/delta/payments), uploads E103/E107 gates, webhook E501 HMAC rejection, empty-status shape `{run_id, payments:[], captured:false}`, FE `/` and `/checkout/[runId]` render 200.
- **Broke:** nothing in the product — two smoke probes were harness bugs (PowerShell quote-mangling the JSON body; CSV header named `sku` where the spec says `id`). Retested correctly, both green.
- **Spent:** $0.
- **Decided:** `make e2e` wired for real (user approved the install): `@playwright/test` + Chromium in frontend/, `playwright.config.ts` boots backend (seed+uvicorn) and `next start` itself; 7-route smoke spec is read-only — no audit or payment is ever started by e2e. Ruff lint debt in scripts/tests cleaned (74 backend tests green).
- **Still open before submission:** OPENROUTER_API_KEY (live 640-trial run + model re-pin) and Razorpay test keys + webhook secret (live link→webhook→capture proof).
