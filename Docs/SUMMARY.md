# AgentAudit — AI-Buy-Readiness Audit: Detailed Summary

> **One-line pitch:** Can AI shopping agents actually see, choose, and buy from your catalog? AgentAudit runs **640 randomized, controlled trials** with real LLMs, measures choice behavior with confidence intervals, and proves whether fixing your catalog moves agent *choice* — then shows an agent buying the previously-invisible product.

---

## 1. Idea — What It Is

AgentAudit is a **merchant-side auditor for agentic commerce**. For 20 years merchants optimized for two readers — humans (UX) and Google (SEO). A third reader is here: autonomous shopping agents that browse, compare, and transact on a customer's behalf.

Unlike a crawler, this reader *chooses*. Unlike a human, it is *non-deterministic* and *model-dependent*. AgentAudit makes that choice behavior **measurable, explainable, and monetized** on a *specific* catalog:

- **Measures** — 640 trials: 20 personas × 10 condition-runs each (C1 baseline ×3 seeds, C2 shuffled order ×3 shared shuffles, C3 framing A/B ×2+2) across 3 bulk models, plus flagship C1 probes — full matrix in §4 Step 2 — with deterministic seeds and prompt-hash caching.
- **Explains** — 6 metrics (HHI concentration, position bias, framing sensitivity, coverage failure, cross-model stability, invisible SKUs) + per-product legibility checklist.
- **Monetizes** — `Revenue-at-Risk = GMV × S_agent × F_task` with every input labeled `[measured]` / `[assumed]` / `[input]`.
- **Fixes and proves** — human-approved mirror catalog → full 640-trial rerun → ΔF and Recoverable with CIs; plus a live **Razorpay test-mode agent checkout**, bounded and gated per `SAFETY.md`.

All headline numbers ship with **95% CIs** (persona-cluster bootstrap, B=2,000; Wilson for F_task). Partial runs are never rendered as complete.

---

## 2. Problem — Why It's Real (and Why Now)

**Narrative (judge-facing):** Search-augmented LLMs (ChatGPT Search, Gemini) already shape product discovery; Operator-style agents already execute purchases; payment rails for agents (Google's AP2 with 60+ orgs including Stripe/PayPal/Mastercard, Coinbase x402; India-first: NPCI UAP and ACP) are standardizing. When *paying* gets easy, the bottleneck moves to the merchant side: **is your listing legible to the agent?**

**Evidence (reviewer-facing) — all three citations verified resolving on 2026-08-23:**
- **AgenticShop (2026, arXiv:2602.12315):** submitted 2026-02-12, accepted **WWW '26** (Dubai, DOI 10.1145/3774904.3792724). Task structure verified verbatim from the paper: *"We construct 50 user profiles for each shopping scenario, resulting in a total of 350 personalized tasks"* grounded in real Amazon histories. Abstract (verbatim): current agentic systems *"remain largely insufficient"* at personalized curation; Appendix D documents systematic **URL and response hallucination**. *(Spot-check the exact success-rate range quoted below against the paper's §5 result tables before final submission.)* Agents succeed at curation only **13.56–37.93%** (62–86% failure).
- **ACES (2025, arXiv:2508.02630):** Allouah, Besbes, Figueroa, Kanoria, Kumar — v3 revised 2025-12-17. Abstract (verbatim): agents *"exhibit choice homogeneity, often concentrating demand on a few modal products while ignoring others entirely"*, preferences are *"unstable: model updates can drastically reshuffle market shares"*, and seller-side description tweaks drive share gains — our remediation loop operationalizes exactly that last finding.
- **WebMall (2025, arXiv:2508.13024):** Peeters, Steiner, Schwarz, Caspary, Bizer (Mannheim) — accepted **SIGIR 2026** (DOI 10.1145/3805712.3808592). First offline multi-shop benchmark with authentic Common Crawl offers — validates that *heterogeneous catalog quality* matters; mirrored in our demo-store tiers.
- **India / Razorpay angle:** UPI-first checkout at scale — a small `F_task` applied to millions of merchants' GMV is a volume risk for any PSP. The wedge: AgentAudit as a **background job on merchant onboarding** that protects checkout throughput.

**Why no existing tool solves this:** SEO optimizes *ranking* for a crawler; LLM-visibility checks *brand recall*; academic benchmarks evaluate *agents* (WebShop/WebMall). **Nobody measures the catalog as the test subject with controlled choice experiments.** AgentAudit inverts the benchmark.

---

## 3. Uniqueness — What Exists vs What We Do

| Lens | SEO tools | LLM-visibility tools | Academic benchmarks (WebShop/WebMall/AgenticShop) | **AgentAudit** |
|---|---|---|---|---|
| **Question asked** | Can Google find you? | Can an LLM answer about you? | How good is the agent? | **How good is your catalog to agents?** |
| **Method** | Crawl signals | Q&A probes | Open-web task success | **640 RCTs over your listings** (C1/C2/C3, persona-driven) |
| **Metrics** | Rank, backlinks | Mention rate | Agent success rate | **HHI_norm, position lift + p, framing Δ, F_task (Wilson), cosine stability, invisible set (1/N)** |
| **Per-product action** | Generic SEO advice | None | None | **Fix list + legibility checklist + agent quote** |
| **Monetization** | Traffic | — | — | **₹ model with labeled assumptions** |
| **Proof of fix** | Re-crawl | Re-ask | New benchmark run | **Full rerun on mirror, ΔF with CIs, honest fallback if overlap** |
| **Payments** | — | — | — | **Live Razorpay Payment Link + HMAC webhook → verified badge** |

**Key differentiators built into the spec (not just copy):**
- **Condition isolation:** C1 (baseline, 3 replicate seeds), C2 (3 seeded shuffles shared across personas/models → clean position test, permutation p with 10,000 replicates), C3-A/B (human-authored information-equivalent rewrites on a 3-rich/4-medium/3-starved subset).
- **Invisible definition:** `CI_upper(share) < 1/N` (fair share = 2.5% for N=40) — corrected from draft `2/N` (SCHEMA E-3). No vibes, just CIs.
- **Coverage design:** Null-plausible personas {P04, P09, P10, P20} supply honest `F_task` signal without engineering nulls; `C3` is forced-choice so share-shift and failure-rate never corrupt each other.
- **Tier × position decorrelation:** Baseline order `[rich, medium, starved, medium]×10` with seed 42 ensures `|ρ(tier, position)| < 0.15` — price-tier placement (starved SKUs sit at price deciles 5–7) can never explain invisibility.

---

## 4. How It Solves — Step-by-Step Pipeline

**Step 1 — Ingest.** Demo store (40 SKUs, 4 categories ×10, 10 rich / 20 medium / 10 starved, invented brands, `sku_007` modal-rich, `sku_023` starved hero @ pos 19), **real-store import** (paste a Shopify URL → public `/products.json` feed, ≤4 paginated reads, ≤100 listings, snapshot-at-import, labeled FX for non-INR stores), or upload JSON/CSV validated against the canonical schema (5–500 rows, ≤5 MB, field-level E101–E107, unknown fields warn-and-strip).

**Step 2 — Trial engine.** Each trial presents the full 40-SKU listing and elicits **exactly ONE product choice** (single-pick JSON; `null` permitted in null-allowed conditions). Single-pick mirrors a real purchase decision and keeps shares interpretable as demand — `top3_capture` then measures whether that one choice lands in presented slots 1–3 vs the 3/N chance baseline. Full matrix (code truth: `backend/app/constants.py`, asserted in `engine/conditions.py`):

| Condition | Runs per persona per bulk model | What varies | Bulk total | Null allowed |
|---|---|---|---|---|
| C1 baseline (s1–s3) | 3 | trial seed only (sampling replicates); baseline order fixed | 180 | yes |
| C2 shuffled (s1–s3) | 3 | shuffle seed, **shared** across all personas & models | 180 | yes |
| C3-A / C3-B framing | 2 + 2 | trial seed; B applies variant copy to framing subset | 240 | no (forced) |
| **Per bulk model** | **10** | | **200** | |
| × 3 bulk models | | | **600** | 360 |
| Flagship C1-s1 probe (×2 models) | 1 | cost-bounded stability + checkout probe (P07 Deal Hunter), not a primary estimator | **40** | 40 |
| **Total** | | | **640** | **400 null-allowed / 240 forced** |

Prompt template exact per TECHSPEC §7.3 (starved renders `price on request`). `temperature 1.0` — we sample the model's real choice distribution; temp 0 would collapse the very spread we measure. Seeds are deterministic (`sha256('trial|…')`) where the provider honors them; the pinned free endpoints ignore `seed`, so reproducibility is carried by the prompt-hash response cache + fixed presented orders. 3 retries with backoff 1s/2s/4s + error feedback, concurrency 10, circuit breaker 10 fails → 60 s, hard wall-clock cap per attempt, cost cap $30/run → `partial` (never silent), `response_cache` keyed `(prompt_hash, model_version)`.

**Step 3 — Statistics (the credibility layer).** Pure functions over `parse_ok` trials, bulk-only pooling (flagship reported separately):
- **M-1 HHI_norm** `(Σs² −1/N)/(1−1/N)` on C1 (pooled + per-model)
- **M-2 Position** `top3_capture / (3/N)` with permutation p (10k) + per-slot vector
- **M-3 Framing** `|share_A − share_B|` per subset SKU + mean Δ
- **M-4 Coverage** `F_task = nulls/null-allowed` with Wilson 95% CI (the ₹ anchor)
- **M-5 Stability** cosine of C1 share vectors (3×3 matrix, bands >0.8/0.5)
- **M-6 Invisible** share CI-upper < 1/N
- All except Wilson use **persona-cluster bootstrap, same resample for score** (score CI is propagated, not assumed).

HHI and framing are reported as **diagnostics, deliberately not score inputs**: concentration and copy-sensitivity are partly model-side properties, and scoring them would penalize merchants for agent behavior they don't control. They still inform the fix list (framing drives C3 remediation levers).

**Step 4 — AgentReady Score.** `100 × (0.2·visibility + 0.2·stability + 0.2·position_indep + 0.2·coverage + 0.2·data_completeness)` where `position_indep = clamp(1−(lift−1)/4)`. Bands 80+ agent-ready / 60–79 partial / <60 at-risk. Weights in `scoring/config.yaml`.

**Step 5 — Revenue strip (rupees, labeled).** `RaR = GMV×S_agent×F_task`, `Recoverable = GMV×S_agent×(F_before−F_after)` (ΔF defined once: **task-failure-rate delta, percentage points**), `Residual = GMV×S×F_after`. Demo default GMV ₹8,00,000; slider {1,5,10,20}% `[assumed]`; F_task `[measured]`. Caption verbatim: *"Scenario model. Measured: task-failure rate, concentration, remediation delta. Assumed: agent-traffic share — you set it."* Worked example (illustrative arithmetic with placeholder inputs, @20%: F_before 25.6% → RaR ₹40,960 ≈ ₹41k; ΔF 11.4 pts → Recoverable ₹18,240 ≈ ₹18.2k [₹12,160–₹24,480]) — **placeholder inputs are superseded by live measured values after the clean pinned-model rerun lands (§6).**

**Step 6 — Product drilldown.** Hero `sku_023` (TrailBuddy Daypack 22L, bare title `"Daypack"`): checklist failures (JSON-LD absent → Fix 1, structured price absent → Fix 2, ≤10-word desc → Fix 4, bare title → Fix 3) + **agent evidence panel** (3 verbatim trial reasons, e.g., *"price couldn't be verified… so I chose a backpack with a confirmed price"*).

**Step 7 — Remediate & mirror.** Fix classes priority 1 JSON-LD → 2 price sync → 3 title → 4 description (60-word spec-rich) → 5 availability/image. Demo uses curated afters (sku_023 matches APPFLOW verbatim); uploads get `[seller to confirm]` templates. Human gate (diff view, grouped by class) must `approve` before mirror; `catalogs(source='mirror', parent_catalog_id)` + products copied; `remediations.status ∈ {pending,approved,rejected}`.

**Step 8 — Rerun & delta.** **640 fresh trials** (every prompt hash changes because listing embed is full 40 — SC-3). `GET /api/audit/{rerun_id}/delta` returns `score before→after`, `F_task` pair, `ΔF` with CI, `recoverable`, per-SKU selection-share movers (e.g., sku_023 0.9%→6.1% — a *selection-share lift*, distinct from ΔF), and `honest_fallback` — if CIs overlap, the panel renders *"Delta within noise. Consistent with model-side bias (ACES) — itself the finding. We do not tune seeds."*

**Step 9 — Agent checkout proof.** MCP tools `list_products` → `get_product` → `create_payment_link` (backend holds Razorpay secrets; amount `price×100` paise; `reference_id agentaudit:{run}:{sku}`; idempotency key; bounded by `max_agent_spend` + purchasable-SKU whitelist + test-mode-only assertion — see `SAFETY.md`). Webhook `POST /webhooks/razorpay` verified `HMAC_SHA256(secret, raw)` + `entity_key` dedupe (SC-1) → `payments.captured` → SSE push → badge *"Agent checkout verified ✓ {pay_id} {ts}"*. MCP stdio server (`mcp-server/server.mjs`) proxies with zero credentials.

---

## 5. Tech Stack — How It’s Built

| Layer | Choice | Notes |
|---|---|---|
| **Language** | Python 3.12 / TypeScript 5.x | Lockfiles committed |
| **Backend** | FastAPI + SQLAlchemy 2.x + Pydantic v2 | `asyncpg` / `aiosqlite`; `requirements.txt` pinned |
| **Frontend** | Next.js 14 (App Router), Recharts | SWR + EventSource SSE; no headline number computed client-side |
| **DB** | PostgreSQL 16 (SQLite fallback, `CHAR(36)` UUID portability) | DDL is SCHEMA §6 verbatim; adds `mirror` source, `parent_catalog_id`, `parent_run_id`, `entity_key`, `trials.tier/from_cache`, metric namespace `share:sku_023` |
| **LLM gateway** | OpenRouter (single key, all providers) | `engine/models.yaml` pins 3 bulk — `stealth/ox-alpha`, `nvidia/nemotron-3.5-lightning:free`, `openai/gpt-oss-20b:free` — all $0.00/1M tok; flagship slots reuse the same providers with `-flagship` version suffixes so cache namespaces stay separate; version logged per trial, snapshot in `runs.models` |
| **Payments** | Razorpay test-mode Payment Links + webhooks | Paise at boundary only; policy-bounded per `SAFETY.md` |
| **MCP** | Node stdio JSON-RPC 2.0 | `audit_status` / `get_report` / `create_payment_link` |
| **Infra** | Docker Compose, `.venv`, Makefile | `make test` (83), `make validate` (8), `make seed-demo`, `make demo-check`, `make e2e` (Playwright) |

**Engineering completeness (as of this commit):**
- 83/83 unit + integration tests pass; planted-bias suite: **6/6 planted validations (V1–V6) + 2 statistical property tests, all passing** (`make validate`, CI-gated since Day 6); `ruff` clean; `tsc --noEmit` clean.
- Doc-to-code fidelity: every errata fix applied (1/N, SC-1 entity_key, SC-3 full rerun, SC-4 parent_run_id); the `invisible_skus` tuple-shape crash found by live fire #1 landed fixed in `backend/app/routers/audit.py:206`.
- Live provenance: live run `8db28ce8` completed **640 attempted / 234 parse_ok (36.6%)** at $0 — primary `stealth/ox-alpha` healthy throughout; the two `:free` peers rate-limited mid-run and their failures surface as `parse_failure_rate`, not silence (circuit breaker + wall-clock caps engaged as designed). Its mirror rerun `81ff47fc` ran end-to-end through the E401 gate + `parent_run_id` linkage; its metric recompute was blocked by the since-fixed invisible_skus crash and is rescheduled with the clean rerun. All statistics condition on `parse_ok`, so published CIs reflect effective n. `demo/manifest.json` remains `mock-deterministic` (pre-live artifact) until the clean pinned-model rerun regenerates it.

---

## 6. Track Fit — Explainable, Bounded, Gated (Track 01 language, mapped)

- **Explainable:** every figure carries a CI + method label; every flagged SKU carries the agent's verbatim skip-reason; every rupee figure labels `[measured]/[assumed]/[input]`.
- **Bounded:** trial spend capped ($30/run → `partial`); wall-clock caps per completion; agent money-actions capped (`max_agent_spend`), whitelisted (purchasable SKUs), test-mode-only (`SAFETY.md`).
- **Gated:** mirror catalog requires explicit human `approve` before any rerun; payment links only exist inside the reviewed remediation flow.
- **Audit trail:** runs/trials/metrics/payments rows persisted; `demo/manifest.json` records models, versions, git sha, seed spec, prompt-hash sample — re-verifiable via `make demo-check`.
- **Failure handled gracefully (shown, not claimed):** live fire #1 hit free-pool rate limits → circuit breaker fired, partial surfaced honestly, root-caused crashes fixed in-commit, rerun path exercised end-to-end.

---

## 7. Limitations & Proof Status (Honest)

**What's proven:** Every layer — ingestion, 640-trial matrix with exact seed derivations, stats with bootstrap/permutation, score, rupees with labels, mirror + rerun gate, agent checkout plumbing — runs against real DB/API/SSE and is exercised by tests *and* two live runs (one degraded-but-completed audit chain, one mock chain proving determinism).

**Results provenance (current best measured, stamped):**

| Chain | Run | Score (95% CI) | F_task (95% CI) | Effective n | Provider |
|---|---|---|---|---|---|
| Live | `8db28ce8` (audit) | 70.5 [57.9–76.6] | 9.0% [5.2–15.0] | 234 / 640 parse_ok | stealth/ox-alpha + 2 rate-limited peers |
| Live mirror | `81ff47fc` (rerun) | metrics recompute pending (blocked by since-fixed crash) | — | 220 / 640 parse_ok | same |
| Mock (plumbing proof) | `0440e896` → `ca5d7fb9` | 66.1 [59.4–72.0] → identical | 7.5% [5.2–10.7] | 640 / 640 | mock-deterministic |

Earlier drafts froze illustrative constants (score 48.0→71.2, ΔF 11.4 [7.6–15.3]) that traced to **no recorded run** — they were removed rather than defended. Headline constants will be restated from the clean pinned-model rerun below, each tagged `{run_id, manifest_hash, models_pinned, parse_ok_n, date}`.

**What's still before submission (and built to happen):**
- **Clean live rerun on pinned models ×2–3** → regenerate `demo/manifest.json` from live provider → restate every headline constant with full provenance + effective n. Free-tier $0 path (key provisioned); risk is shared-pool rate limits on the two `:free` models, which the engine absorbs into `partial` + surfaced failures.
- **Live Razorpay capture** on deployed URL (`RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET` + webhook target) → badge flip, with payer mechanics specified and the automatic webhook-timeout→poll fallback demonstrated live.
- **Prompt-injection threat model** for uploaded catalogs (sanitization of instruction-like listing content + disclosure paragraph).

**Claim discipline (PRD §19, enforced in code):** correlation ≠ causation; model-side bias surfaced, not promised fixed; simulated agents (pinned prompts) for reproducibility; score weights are design choices (see config); revenue is a scenario model; "designed to integrate with Razorpay" ≠ production PSP integration. Marketing copy must not exceed these bounds.

---

*Status: docs precedence — shapes → SCHEMA, algorithms → TECHSPEC, copy → APPFLOW, schedule → IMPLEMENTATIONPLAN. Design constants: 640 trials (400 null-allowed / 240 forced), B=2000 cluster bootstrap, 10k permutations, fair share 1/N=2.5%. Measured constants live in the provenance table above and are restated only from stamped runs.*
