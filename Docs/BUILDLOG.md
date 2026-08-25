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

## Day 15 — External review response: provenance truthing + money bounds + design tokens (Aug 23)

- **Shipped:** v2 external-review critical path executed. Docs/SUMMARY.md rewritten against ground truth: full 640-trial matrix table from `constants.py`/`conditions.py` (C1×3 replicate seeds was the doc gap — 180+180+240+40 closes the arithmetic), single-pick elicitation stated explicitly (reviewer's "top-3" premise was wrong; prompts request exactly one product, `top3_capture` = chosen item lands in slots 1–3 vs 3/N), all three arXiv citations verified resolving (AgenticShop WWW'26 DOI 10.1145/3774904.3792724 · ACES v3 · WebMall SIGIR'26) with verbatim abstract quotes stamped, ~12 minor fixes (ΔF defined once as task-failure pp delta, selection-share movers named separately, ₹ standardized, temp-1.0 rationale, real OpenRouter slugs, V-suite = 6 planted validations + 2 property tests, HHI/framing-not-scored rationale, flagship-C1 probe rationale). Track-01 bar mapped clause-by-clause to mechanisms.
- **Broke (found by querying, not reading):** the frozen headline constants (score 48.0→71.2, ΔF 11.4 [7.6–15.3], F_before 25.6%) matched NO run in the DB, NO manifest, NO doc section — unsourced illustrative numbers in a provenance-bragged doc. Removed and replaced with a DB-stamped provenance table: live chain 8db28ce8→81ff47fc (70.5 [57.9–76.6], F_task 9.0% [5.2–15.0], parse_ok 234/640 and 220/640 — effective n now published), mock chain labeled plumbing-proof-only. Also found rerun 81ff47fc has zero metric rows because the invisible_skus tuple crash (fixed e86df90) killed compute_and_store_metrics on the first live catalog that produced flagged SKUs — recompute rescheduled with the clean rerun.
- **Shipped (money bounds):** SAFETY.md + policy layer in payments router — per-link cap ₹2,000 (E503), purchasable-SKU whitelist w/ env override (E504), test-mode-only guard firing before any network call (E505); enforcement reads the DB-stored price so agents can't influence amount; 5 new policy tests.
- **Shipped (design):** frontend aligned to DESIGN §2/§3 — bg #0A0A0A, surfaces #141414/#1A1A1A, single accent #4F8CFF, data-state colors flag #FF6B5C / pos #3DD68C only on values, amber removed to neutral muted, Geist + Geist Mono self-hosted via next/font/local (Next 14.2 google-font dataset predates Geist); build green, 0 stale tokens.
- **Spent:** $0 (OpenRouter key probed: free tier, usage 0 across all windows).
- **Decided:** docs claim nothing a recorded run doesn't back; illustrative revenue arithmetic stays but is explicitly labeled placeholder pending the clean pinned-model rerun; replayed payment links bypass cap/whitelist deliberately (no new money moves) while test-mode guard still gates them.
- **Still open before submission:** clean pinned-model live rerun ×2–3 → regenerate demo/manifest.json from live → restate constants with {run_id, manifest_hash, parse_ok_n} provenance; live Razorpay test-mode capture (needs RAZORPAY_* keys) incl. payer mechanics + webhook-timeout→poll fallback; prompt-injection sanitization for uploaded catalogs.

## Day 15b — First complete-matrix LIVE audit recorded (Aug 23)

- **Shipped:** run `6ee157a7` — all 640 trials executed against OpenRouter and flushed, $0.00, 111 s wall-clock: **parse_ok 234/640**, every non-parsed trial an honestly-counted provider failure. Headlines with CI: score **70.5 [57.9–76.6]**, HHI_norm 0.110 [0.088–0.262], top‑3 capture 22.8% [13.0–35.1] (lift 3.04×, p=1e‑4), framing Δ +2.1 pp [+1.4, +8.3], F_task 9.0% [5.2–15.0], stability 0.75 moderate; invisible SKUs flagged (sku_003/030/037, upper CI < 1/N) — matches the Day‑15 provenance table, now stamped to a specific run id. Full JSON+MD at demo/live_report_6ee157a7.{json,md}.
- **Provenance:** ox-alpha bulk 200/200 + flagship 20/20 measured live Aug 21–22, replayed from response_cache at zero marginal cost (prompt-hash keyed); nemotron 14/200 cached; nemotron bulk 186 + flagship 20 failed on daily free-pool cap (`429 free-models-per-day`); gpt-oss 200/200 failed — `openai/gpt-oss-20b:free` delisted upstream (404, paid slug only). Per-model parse rates published in models_meta.
- **Broke → fixed:** the original freeze post-mortem (commit e7e81f9): a proxied connection's cancellation never completed, defeating the per-attempt wait_for cap and silently killing the worker (status stuck `running`, 0 outcomes in ~10 h). Runner now wraps each trial in an unbreakable 300 s shielded-task cap (abandon-on-timeout → counted failure) plus a broad engine-error guard — proven live: zero stalls across three subsequent full-matrix executions.
- **Ops honesty:** two overnight runs (a840125c, 6ee157a7) were fired manually at ~02:18 IST; the backend died again with machine sleep mid-first-run — orphan closed as `failed` (400 rows kept), second run completed. Monitor cron auto-restarts uvicorn and escalates stalls; gap-fill run `6b3fd1ea` fired post-quota-reset to measure nemotron's remaining trials against the refreshed pool.
- **Spent:** $0.

## Day 15c — Nemotron gap-fill live completion (Aug 23)

- **Shipped:** run `6b3fd1ea` — post-quota-reset refire, all 640 trials executed and flushed, $0.00: **parse_ok 239/640**. Headlines with CI: score **67.1 [55.9–74.6]**, top‑3 capture 22.8% [13.0–35.1] (lift 3.04×, p=1e‑4), framing Δ +2.1 pp [+1.4, +8.3], F_task 10.1% [6.1–16.2], stability 0.58 moderate; invisible SKUs sku_003/030/037/040. Full JSON+MD at demo/live_report_6b3fd1ea.{json,md}.
- **Honest delta vs 15b:** nemotron bulk 14/200 → **19/200** — the UTC-midnight reset opened the free pool just long enough for ~5 live successes before congestion re-closed it; further attempts hung past the unbreakable ≤300 s trial cap or returned 429, all counted as failures (parse rate 0.93 → 0.905). Cached successes replay free on any future refire, so accumulation continues across days without redoing work. gpt-oss stayed delisted (404 ×200 → counted); nemotron flagship 20/20 counted failures (no cache coverage).
- **Observation:** score 70.5 → 67.1 and stability 0.75 → 0.58 moved purely because five more nemotron rows entered the pool — cross-model numbers are honestly sensitive to measured coverage per model; both runs publish their exact parse_ok n.
- **Spent:** $0.

## Day 16 — First live Razorpay capture chain closed (Aug 24)

- **Shipped:** reviewer priority 3 proven end-to-end on real test-mode rails: audit `6b3fd1ea` (640/640 live) → agent-created link `plink_TTM8L1vq0TeYsr` (₹999, sku_007, 40-char hashed reference `aa:b516fb…` round-tripped by Razorpay) → human UPI payment 17:26 IST → **captured** — verified both sides: Razorpay API (`status=paid`, `method=upi`) and DB (`payments.status=captured`, row c8050fe6).
- **Honest path note:** `webhook_events` stayed empty — the dashboard webhook still points at a rotated tunnel URL — so the capture was adopted by the webhook-timeout→poll fallback (bff2e36): the status endpoint asked Razorpay directly for pending links and flipped local state from provider truth. The documented SAFETY.md fallback doing its job, and proof that local testing needs no public URL.
- **Broke → fixed:** every mid-run poll of GET /api/audit/{id} 500'd (ecf787b): SQLite returns started_at naive, ETA branch subtracted it from aware utcnow() → TypeError; completed runs never take the branch, which is why it survived three live-fire days. Regression test drives a running run through the branch; suite 127/127. Also fixed scripts/rzp_attempt_check.py — attempts ride on the link-fetch payload (GET /v1/payments rejects plink_* ids).
- **Ops honesty:** two fresh full-matrix demo audits were fired concurrently during this window; both ground through nemotron's re-congested pool with hangs bounded by the 300 s trial cap (counted failures), exactly as designed.
- **Spent:** $0 (test mode — the ₹999 is simulated money).

## Day 17 — Multi-provider engine; third slot lands on OpenCode Zen (Aug 25)

- **Shipped:** engine now routes per-model across providers — ModelEntry gains `base_url`/`endpoint`/`api_key_env`; Anthropic-style `/v1/messages` support (x-api-key headers, content-block parsing, input/output token mapping); base URLs ending in `/v1` are not doubled; circuit-breaker keys namespaced by provider origin. glm engine id retired: AiHubMix removed entirely after its unrecharged-account cap (refusal-text delivered as HTTP 200) produced 0/200 parse_ok on run d593113f.
- **New pin:** third bulk slot = `mimo` (mimo-v2.5-free @ https://opencode.ai/zen/v1, OpenAI format). Probed before wiring: key + model + `response_format: json_object` all accepted at $0 — json_object fully suppresses the reasoning model's CoT detour (63 tok → 6 tok answers). Client end-to-end returned exact JSON.
- **Proven live:** run 428bc860 logged the first productive third-slot trial in project history (mimo 1 parse_ok, real choice, $0). Score 49.0, parse_ok 223/640.
- **Discovered (honest):** OpenCode Zen free quota is hard-gated — trial #1 succeeded, then 9× 429 and the circuit breaker fail-fast opened for the remaining 189 (by design; docs indicate ~100–200 req/day free tier, likely already exhausted that day). Wiring is correct; throughput is quota-bound.
- **Decided:** pin stays. Cached mimo successes replay free on every future refire (same accumulation play as nemotron) — each UTC-day reset adds rows without re-billing. Suite 131 green.
- **Spent:** $0.



## Day 18 — Production deploy on antideploy.com (Aug 25)

Both apps public: API https://agentaudit-api.antideploy.com · Web https://agentaudit-web.antideploy.com

Deploy journey — 9 attempts, 3 failure classes, all diagnosed from first principles (platform exposes no build logs over its API; only step status/spec/warnings/hazards):

1. Buildpack builds died ~40s installing pinned deps. Local wheel audit (`pip download --only-binary --python-version 314`) proved asyncpg 0.30 has no cp314 distribution — the platform's 2026-default Python predates our pins' wheels. `runtime.txt` hint ignored. Fix: explicit `Dockerfile` pinning python:3.12-slim; docs confirm root Dockerfile overrides buildpacks (build went fail@42s → pass@197s).
2. Boot crash #1: platform injects `DATABASE_URL=postgresql+psycopg2://…`; SQLAlchemy reached for psycopg2 (absent) inside lifespan. session.py now forces every postgres-family drivername onto asyncpg, translates libpq `sslmode`, runs create_all on Postgres (platform runs no migrations), and falls back to ephemeral SQLite loudly if the primary is unusable.
3. Boot crash #2: demo-store/ + fixtures/ resolve via parents[3] outside a container whose archive root IS backend/. New app/paths.resolve_dir() checks monorepo/archive/cwd layouts; deploys bundle both dirs.
4. Web buildpack failed on Next 16 app with TS/Tailwind as devDeps; custom multi-stage node:22-slim Dockerfile bakes NEXT_PUBLIC_* at build time (runtime-only env injection would inline nothing). npm ci then rejected the stale package-lock.json; regenerated it; npm10-in-container still stricter than local npm11 → `npm ci || npm install` fallback.

Verified end-to-end through public URLs: /catalog serves the auto-seeded demo catalog (40 SKUs) from managed PostgreSQL; deployed web catalog page renders all rows client-side against the deployed API.

Known quirks: platform edge 404s /healthz before it reaches the app (Cloudflare route rule; app-side health passed during release — frontend never calls it). Secrets live in antideploy's store: OPENROUTER/OPENCODE_ZEN/RAZORPAY_* + CORS_ORIGINS="*".


## Day 19 — Catalog follows the store you ran (Aug 25)

- **Shipped:** /catalog no longer hardcodes the demo seed. New `GET /catalogs` lists every catalog (merchant, source, product count) newest-first; `GET /catalog` and `GET /catalog/{sku}` accept `?catalog_id=`. The default view flips to the newest non-demo catalog — imported store / CSV upload / mirror — with the demo seed as fallback on fresh deployments.
- **Why:** the first real test (suta.in import → 100 SKUs → audit run 4d94c4ce) exposed that the catalog page could never display an imported store: `_latest_catalog()` filtered `source == "demo"`.
- **Frontend:** Store switcher on /catalog (appears once ≥2 catalogs exist; degrades silently against older APIs); subtitle names the merchant; null-safe price/description rendering for scraped feeds.
- **Tests:** multi-catalog suite covers listing, pinning, cross-catalog scoping and the default flip — 132 passing, ruff clean, tsc clean.
- **Ops note:** discovered mid-feature that the suta run lived entirely in local SQLite (the deployed DB has zero runs) — the "wait for the run before API redeploy" constraint evaporated.
- **Spent:** $0.
- **Addendum (Aug 26, 00:00 IST):** temporary re-pin per owner call — bulk slot order is now (`mimo`, `ox-alpha`, `nemotron-flash`) so OpenCode Zen schedules first. Matrix unchanged at 640 trials; flagship untouched; revert = restore the tuple and yaml list order.
- **Addendum 2 (Aug 26, ~00:20 IST):** the mimo-reorder deploy came up on ephemeral SQLite — a release-window race where a single failed Postgres connect at boot permanently degraded that container (imported catalogs wiped; demo re-seeded fresh). `init_db` now retries the primary 4× over ~17s before falling back, logging each attempt. Suta was re-imported post-incident. Suite 133 green.
- **Addendum 3 (Aug 26, ~01:00 IST) — true root cause of the catalog resets:** production was NEVER on the managed Postgres. The new `/api/dbstatus` probe showed every boot degrading to ephemeral SQLite because `create_all` died on Neon with `operator does not exist: boolean = integer`: the trials table's choice-semantics CHECK was written SQLite-style (`parse_ok = 0 ... null_allowed = 1`) over Boolean columns. Rewritten portable (`NOT parse_ok ... null_allowed`). `init_db` now also retries the primary 4x over ~17s before falling back, and `/api/dbstatus` exposes on_primary / driver / sanitized error so degraded boots are detectable from outside. Correcting the Day-18 record: its "verified against managed PostgreSQL" claim described a container that was actually serving throwaway SQLite. Suite 134 green.
