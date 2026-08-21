


# APPFLOW — AgentAudit

| Field | Value |
|---|---|
| Document | Application Flow Specification (screen, state & interaction contract) |
| Version | 1.0 |
| Status | Frozen for build |
| Product | AgentAudit — AI-Buy-Readiness Audit |
| Companion docs | `PRD.md` (what/why) · `TECHSPEC.md` (engineering contract) · `IMPLEMENTATION.md` (schedule) · this doc (UX flow) |
| Precedence | UI copy and numbers in this doc are **derived from TECHSPEC §9.3 engineered targets and §10.3 canonical scenario**. Recorded runs in `demo/manifest.json` remain authoritative; if they differ, the delta rule (TECHSPEC §14) applies. |

---

## 0. Errata — reconciliations against the doc set

Apply these one-line fixes before build:

| # | Location | Was | Corrected | Why |
|---|---|---|---|---|
| AF-1 | PRD §15 step 2–3; IMPLEMENTATION §12 steps 2–3 | "product #17 / SKU #17 (starved tier)" | **"sku_023 (starved tier, baseline position 19)"** | TECHSPEC's canonical schema example `sku_017` is a **rich**-tier product; the demo narrative's invisible hero must be a **starved** SKU. Hero is now `sku_023 — TrailBuddy Daypack 22L` (defined in §2.3). Also, under the §2.2 baseline block order `[rich, medium, starved, medium]×10`, position 17 is rich and position 19 is starved — so the hero sits at position 19 |
| AF-2 | PRD §15 step 2; IMPLEMENTATION §12 step 2 | "3 of 40 SKUs captured 68% of agent demand" | **"One SKU alone captured 74% of agent demand"** | HHI_norm 0.54 (TECHSPEC §9.3) implies a ~74%-share modal SKU; if one SKU holds 74%, three SKUs must capture ≥ 74%, not 68%. The "74% monopoly" line is also the stronger demo beat |
| AF-3 | PRD §5.2 P7 names | (none) | `P07 = "Deal Hunter"` is also the fixed checkout persona (TECHSPEC §12.3) | Naming locked so ticker copy in F2 and agent console copy in F7 read consistently |

---

## 1. Purpose & Conventions

### 1.1 What this doc covers

Every screen, every interactive state, every error state, and the exact copy for each — plus the demo click-path (§10). Engineering contracts (API shapes, DDL, metric formulas) live in TECHSPEC and are **referenced, not restated**.

### 1.2 Global conventions (apply to every screen)

**App shell:**

```
┌──────────────────────────────────────────────────────────────┐
│ ◆ AgentAudit      [Track 01 · Agentic Commerce]   Docs  GitHub │  ← sticky header
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                      <screen content>                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Metrics: persona-cluster bootstrap 95% CI · Research: ACES '25, │  ← sticky footer
│ AgenticShop '26, WebMall '25 · Runs recorded in manifest.json   │
└──────────────────────────────────────────────────────────────┘
```

**CI display convention (everywhere, no exceptions):**

- Format: `value [lo – hi]` → e.g. `48.0 [44.1 – 52.3]`
- Hover on any CI → tooltip: *"95% confidence interval, persona-cluster bootstrap, B = 2,000"*

**Label convention (revenue numbers only):** every revenue figure carries a tag chip — `[measured]` (teal), `[assumed]` (amber), `[input]` (gray) — per PRD §8.6.

**Number formatting:** Indian digit grouping (`₹8,00,000`), no decimals for rupees, one decimal for scores/shares (`74.2%`).

**Citation chips:** inline superscript pills `[ACES '25]`, `[AgenticShop '26]` next to any research-derived claim; click → citation popover with arXiv link.

**Loading:** skeletons shaped like final content (no spinners except global route transitions).
**Empty/error:** per §9 edge-case table; errors show humanized message + code (`E201 Provider timeout — retrying (2/3)…`).

**Frontend number rule (normative):** the client **never computes a headline number**. Every figure renders from `/api/audit/{id}/metrics` fields. Chart footers show the metric key (e.g. `metric: hhi_norm`).

### 1.3 Route map

| Route | Flow | Screen |
|---|---|---|
| `/` | F1 | Setup |
| `/audit/[id]` | F2 → F3 | Progress → Results (same route, state-driven) |
| `/audit/[id]/product/[sku]` | F4 | Product drilldown |
| `/audit/[id]/remediate` | F5 | Remediation review |
| `/audit/[id]/compare` | F6 | Before/after |
| `/checkout` | F7 | Agent checkout |
| `/onboarding-demo` | F8 | Onboarding webhook demo |

```mermaid
flowchart TD
    A[F1 /] -->|POST /api/audit| B[F2 progress]
    B -->|run done| C[F3 results]
    C -->|click SKU row| D[F4 drilldown]
    C -->|CTA "Fix what's broken"| E[F5 remediate]
    E -->|approve mirror → rerun| F[F6 compare]
    F -->|CTA "Watch an agent buy"| G[F7 checkout]
    H[F8 /onboarding-demo] -->|auto-trigger| B
```

---

## 2. Demo Cast (fixed entities referenced throughout)

### 2.1 The run

- `run_before` — 640 trials, 3 bulk models + 2 flagship, demo store v1
- `run_after` — same matrix against mirrored (remediated) catalog

### 2.2 Headline numbers (engineered targets; manifest authoritative)

| Metric | Before | After |
|---|---|---|
| AgentReady Score | `48.0 [44.1 – 52.3]` | `71.2 [67.8 – 74.9]` |
| Modal SKU share | 74.2% (sku_007) | 41.5% |
| HHI_norm | 0.54 | 0.22 |
| Position lift | 4.2× (p < 0.001) | 3.3× |
| Stability (mean cosine) | 0.48 | 0.62 |
| Coverage F_task | 25.6% [20.8 – 29.3] | 14.2% [10.8 – 18.4] |
| Invisible SKUs | 5 | 1 |
| RaR @ 20% | ₹40,960 ≈ ₹41,000/mo | — |
| Recoverable @ 20% | — | ₹18,240 ≈ ₹18,200/mo [₹12,100 – ₹24,500] |

### 2.3 Hero SKUs (named once, used everywhere)

| SKU | Identity | Role |
|---|---|---|
| `sku_007` | HydroMax Elite 750ml — rich tier, bottles | The modal product (74% share) |
| `sku_023` | TrailBuddy Daypack 22L, ₹1,899 — **starved tier**, baseline position 19 | The invisible hero (drilldown + remediation story) |
| `sku_017` | AquaSteel Pro 1L — rich tier | TECHSPEC canonical example; checkout target is chosen live by the P07 agent |

---

## 3. F1 — Setup (`/`)

### 3.1 Layout (top → bottom)

1. **Hero block**
   - H1: `Your next customer might not be human.`
   - Sub: `Merchants have SEO for Google's crawler. Nothing for the AI agents now choosing products on your customers' behalf. AgentAudit measures how 640 real agent decisions distribute across your catalog.` + chip `[AgenticShop '26: agents fail 62–86% of curation tasks]`

2. **Catalog source cards** (radio behavior, one active)
   - **Card A — Demo Store** (preselected, `RECOMMENDED` badge): "40 products · 4 categories · controlled data-quality tiers"
   - **Card B — Upload catalog**: drag-drop `.json` / `.csv`; on file: inline validation, per-row errors (`Row 7: E104 — price must be between ₹1 and ₹1,00,00,000`); success state: "38 of 40 rows valid — continue with valid rows?" 

3. **Merchant inputs**
   - **Monthly GMV**: text input, default `₹8,00,000`, Indian formatting, validation `≥ ₹10,000` else `E110 — enter a GMV above ₹10,000`
   - **Agent-traffic share slider**: snap points `1% · 5% · 10% · 20%`, default 20%. Live preview line under slider, recomputed on snap:
     - @1%: "₹8,000/mo of your GMV flows through agent checkout."
     - @20%: "₹1,60,000/mo of your GMV flows through agent checkout."
     - Chip: `[assumed — you set this; agent traffic is still ramping]`

4. **CTA button (primary)**
   - Label: `Run audit → 640 agent trials`
   - Sub-label (always visible): `~2–15 min · est. $12 · hard cap $30/run`
   - On click → `POST /api/audit` → redirect `/audit/{id}`

5. **Footer card — "Runs automatically on merchant onboarding"**
   - Copy: "In production, this audit fires the moment a merchant onboards to the payments platform." + link `See it →` → `/onboarding-demo`

### 3.2 States & errors

| State | UI |
|---|---|
| Idle | as above |
| Uploading | Card B shows per-row progress |
| Validation error | field-level red text + code; CTA disabled until resolved |
| 429 rate-limited | toast: "Too many requests — retry in 60s" (60 req/min/IP, TECHSPEC §16) |
| POST success | button → "Queued ✓" → route change |

---

## 4. F2 — Progress (`/audit/[id]`, `status ∈ {queued, running}`)

### 4.1 Layout

1. **Status header:** pill `● Running` · run id (monospace, copyable) · elapsed timer
2. **Progress bar:** `214 / 640 trials` · percentage · running cost `$4.31` (from SSE `progress`) · ETA
3. **Live trial ticker** (monospace, last 6 rows, fade-out):

```
gpt4o-mini   P07  C2-s2   → sku_007   812ms
gemini-flash P04  C1-s3   → null      943ms
claude-haiku P12  C1-s1   → sku_023   677ms   ← tick as they land
```

   Null rows render in amber — visible evidence of coverage failure building in real time.
4. **"What's happening" panel** (collapsible): the three conditions explained in two lines each (C1 baseline · C2 shuffled order → position bias · C3 rewritten copy → framing bias) + "1 in 3 trials may return 'nothing fits' — that's the coverage metric."
5. **Cancel** (secondary, confirms first): run → `failed`; no charge beyond completed trials.

### 4.2 State transitions

| From | Event | To |
|---|---|---|
| queued | runner picks up | running |
| running | `complete` SSE | **auto-redirect → F3** after 1.5 s (with "View results now →" link to skip) |
| running | cost cap hit | `partial` → amber banner: "Cost cap reached at N/640 trials. Metrics computed on N completed trials and labeled as partial." → F3 with partial badge |
| running | circuit breaker open ≥ 60 s | `partial` (same banner, provider named) |
| any | provider hard-fail | `failed` → red panel + `Retry failed providers` button |

**SSE reconnection:** `EventSource` auto-retries; after 3 failures, fall back to 5 s polling of `GET /api/audit/{id}` (progress data still updates; ticker pauses with note "reconnecting…").

---

## 5. F3 — Results (`/audit/[id]`, `status ∈ {done, partial}`)

### 5.1 The three-number strip (sticky top, always visible)

```
┌──────────────────────────┬───────────────────────────────┬────────────────────────────┐
│ AgentReady Score         │ Revenue at Risk               │ Recoverable                │
│ 48.0 [44.1 – 52.3]       │ ₹41,000/mo  @ 20% scenario    │ —                          │
│ [48 → 71 after fixes]    │ F_task 25.6% [20.8–29.3]      │ (after remediation re-run) │
│                          │ [measured]  S=20% [assumed]   │                            │
└──────────────────────────┴───────────────────────────────┴────────────────────────────┘
        Scenario model. Measured: task-failure rate, concentration, remediation delta.
        Assumed: agent-traffic share — you set it.                    [slider 1% · 5% · 10% · 20%]
```

- Slider changes RaR/Recoverable instantly (client recomputes only the **multiplication** — allowed; it is not a measured quantity).
- If `run_after` exists, Score cell becomes `48.0 → 71.2` and Recoverable fills with `₹18,200/mo [₹12,100 – ₹24,500] [measured ΔF]`.
- `partial` badge (amber) renders above the strip when applicable.

### 5.2 Section order (scroll)

**S1 — Choice heat map** *(primary visual)*
- Grid: 40 product rows × 4 columns (3 bulk models + pooled). Cell intensity = choice share; value label on hover with CI.
- Modal row `sku_007` highlighted with caption: `One SKU alone captured 74.2% of agent demand. [ACES '25: modal concentration]`
- Invisible rows (CI-upper < 2.5%): hatched + `⚠` prefix. Legend explains hatch.
- Click any row → F4 drilldown.

**S2 — Position curve**
- Bar chart, per-slot choice %, slots 1–40; dashed chance line at 2.5%/slot; badge: `Top-3 capture 31.5% — 4.2× chance (permutation p < 0.001)`.
- Caption: `Agents favor what's listed first. Randomized order isolates this (condition C2).`

**S3 — Stability matrix**
- 3×3 cosine matrix, band-colored (aligned >0.8 / moderate 0.5–0.8 / divergent <0.5). Demo values: gpt–gemini `0.41` · gpt–claude `0.52` · gemini–claude `0.51` · mean `0.48`.
- Caption: `GPT and Gemini built different bestsellers from the same catalog. Agent-channel revenue depends on which AI your customer uses — and shifts with model updates. [ACES '25]`
- Link: `→ Set up model-version re-audit alerts (roadmap)`.

**S4 — Coverage dial**
- Dial: `25.6% [20.8 – 29.3]` · copy: `1 in 4 agent tasks on this catalog ends with "nothing fits." This measured failure rate drives the Revenue-at-Risk model.`
- Sub-row: null rate by persona archetype — top null-returning personas listed (P04, P09, P10, P20 expected).

**S5 — Framing dumbbell**
- 10 framing-subset products; dumbbell = share_A ↔ share_B; mean Δ with paired CI; displacement callout for the biggest mover.

**S6 — Product table**
- Columns: SKU · Title · Tier badge (rich/medium/starved) · Share `[CI]` · Legibility · Status (`Modal` / `Visible` / `⚠ Invisible`).
- Default sort: share desc. Filter chips: `⚠ Invisible (5)` · `Starved tier` · `Low legibility`.
- Row click → F4.

**S7 — Run footer**
- Models + pinned versions · seeds policy link · cost · parse-failure rate per model (a finding, e.g. `claude-haiku: 2.1% parse failures`) · `manifest.json` link · `Download report` (stretch FR-17).

### 5.3 Results CTA

Sticky bottom-right: `Fix what's broken →` (primary) → F5. Secondary: `Watch an agent buy →` → F7.

---

## 6. F4 — Product Drilldown (`/audit/[id]/product/[sku]`)

Hero case `sku_023` (the demo path):

1. **Header:** `sku_023 — TrailBuddy Daypack 22L` · tier chip `starved` · price `₹1,899 (page-only — absent from structured data)` · status `⚠ Agent-invisible`.
2. **Visibility card:** `Share of agent demand: 0.9% [0.0 – 2.1]` with fair-share line at 2.5% and the gap shaded red. Verdict line: `95% CI upper bound below fair share → invisible.`
3. **"Why agents can't see it" diagnosis** — checklist with failures:
   - ❌ JSON-LD absent → *Fix class 1*
   - ❌ Price missing from structured data → *Fix class 2*
   - ❌ Description: 8 words ("Durable daypack for daily use.") → *Fix class 4*
   - ❌ Title: bare category ("Daypack") → *Fix class 3*
   - ✅ Product page exists and renders
4. **Agent evidence panel** (the credibility moment): 3 verbatim sampled trial reasons mentioning or skipping the product, e.g.:
   > claude-haiku · P12: *"The daypack's price couldn't be verified from the listing data, so I chose a backpack with a confirmed price."*
5. **Fix preview** → `Add to remediation plan →` (goes to F5 with this product expanded).

Back link → F3. If SKU is not invisible, sections 2–4 render the positive equivalents (no red states).

---

## 7. F5 — Remediation Review (`/audit/[id]/remediate`)

1. **Header:** `Remediation plan — 14 products, 41 fixes` + gate status pill `Pending review`.
2. **Fix queue grouped by class** (priority order per TECHSPEC §11): JSON-LD injection (10) · price sync (10) · title rewrites (10) · description expansion (10) · availability/image (1).
3. **Diff view per product** (expandable, `sku_023` pre-expanded in demo):

```
┌─ sku_023 · TrailBuddy Daypack 22L ────────────────────────────────┐
│ ORIGINAL                              │ FIXED (proposed)           │
│ Title:   Daypack                      │ TrailBuddy Daypack 22L —   │
│                                       │ water-resistant, laptop-   │
│                                       │ sleeve, 980g               │
│ Desc:    Durable daypack for daily    │ Ripstop nylon daypack with │
│          use.                         │ 22L capacity, padded 15"   │
│                                       │ laptop sleeve, air-mesh    │
│                                       │ back, rain cover, 980g.    │
│ JSON-LD: (absent)                     │ Product schema: name,      │
│                                       │ price ₹1,899, availability │
│ Structured price: (absent)            │ in stock ✓                 │
└───────────────────────────────────────┴────────────────────────────┘
   ⓘ LLM proposed · human approves · deterministic layer commits
```

4. **Human gate:** checkbox `I have reviewed the proposed rewrites` → enables `Approve & build mirror →`. On approval: mirrored catalog created (`pending_review` → `approved`), triggers `POST /api/audit/{id}/rerun`.
5. **Error states:** rerun before approval → `409 E401 — approve the mirror first`; generation failure → per-product retry.

---

## 8. F6 — Before/After Compare (`/audit/[id]/compare`)

1. **Score delta hero:** `48.0 [44.1 – 52.3] → 71.2 [67.8 – 74.9]` with a CI-overlap indicator; if CIs **overlap**, the honest-fallback panel renders instead (§9.4).
2. **Component deltas:** five mini progress-bar pairs (visibility 0.46→0.78 · stability 0.48→0.62 · position-indep 0.20→0.42 · coverage 0.744→0.858 · completeness 0.518→0.878).
3. **Coverage pair:** two dials, `F_task 25.6% → 14.2%`, with `ΔF = 11.4 pts [7.6 – 15.3] [measured]`. *(Corrected from 15.2 — SCHEMA SC-7: this must match its own rupee-based CI, ₹24,500 / ₹1,60,000 = 15.3%.)*
4. **Per-product visibility delta table:** biggest gainers (sku_023: `0.9% → 6.1%`) and any regressions (flagged amber, investigated before demo).
5. **Rupee delta card:** `Recoverable ₹18,240/mo [₹12,100 – ₹24,500] @ 20%` + slider (same behavior as F3 strip) + caption from TECHSPEC §10.3.
6. **CTA:** `Watch an agent buy →` → F7.

---

## 9. F7 — Agent Checkout (`/checkout`)

### 9.1 Layout

1. **Console** (monospace, SSE `agent_step` stream, typewriter reveal):

```
step 1  tool: list_products        → 40 products received
step 2  reasoning (P07 · Deal Hunter): "Best value-for-money item…"
        comparing price vs. described specs across catalog…
step 3  tool: get_product          → id: "sku_0XX" (agent's live choice)
step 4  tool: create_payment_link  → https://rzp.io/i/xxxxx  ✓
```

2. **Payment card:** agent's chosen product + price + `Open payment page →` (Razorpay test-mode link).
3. **Trust note (always visible):** `The agent never saw a Razorpay key. The backend created this link; the agent only received a URL.`
4. **Capture state:** webhook `payment.captured` → full-width teal banner: `✓ Agent checkout verified — payment {razorpay_payment_id} · {timestamp}` (target < 5 s after payment).

### 9.2 States

| State | UI |
|---|---|
| idle | `Start agent →` button |
| running | steps stream; each tool call shows spinner → result |
| link created | payment card active |
| awaiting payment | pulse on card; note "complete the test payment" |
| captured | teal banner; confetti (once) |
| E5xx link failure | red inline + `Retry link` (idempotency key preserved) |
| webhook > 60 s late | amber: "Verifying via API poll…" (fallback poll of payment status) |

---

## 10. F8 — Onboarding Demo (`/onboarding-demo`)

1. Copy: `In production, this fires when a merchant onboards. Simulate it:`
2. curl block (copy button):
   `curl -X POST /webhooks/merchant-onboarded -d '{"merchant_name":"Acme Store","gmv_inr":800000}'`
3. On trigger → routes to `/audit/{new_id}` (F2) with toast `Audit auto-triggered for Acme Store — the onboarding background-job pattern.`
4. `Last triggered audits` list (merchant, time, score).

---

## 11. Edge Cases & Empty States (global table)

| Condition | Screen | Behavior |
|---|---|---|
| `partial` run | F3 | amber badge above strip; every chart footer appends `computed on N/640 trials` |
| All-null model (provider outage) | F3 S1 | column grayed, `provider unavailable at run time` |
| Parse failures | F3 S7 | per-model rate; excluded trials counted transparently |
| Remediation rerun | F6 | banner: `Mirror copy changes every listing → 640 new trials ($10–15, 2–4 min)` *(corrected from an earlier "168 new trials, cached" draft — SCHEMA SC-3: every trial prompt embeds the full 40-product listing, so any product change invalidates every prompt hash; there is no partial-cache path here)* |
| Cached-only rerun (unchanged catalog) | F2/F6 | banner: `Re-running an unchanged catalog — served from cache, <60 s` — this is the only case the response cache actually shortcuts |
| CI overlap on delta | F6 | honest-fallback panel (§9.4 below) replaces delta hero |
| Deep-link to running audit | F2 | resume live (SSE) |
| Deep-link to unknown id | all | `404 — run not found` + link home |
| Slider at 1% | F3 strip | RaR shows `₹2,048/mo` — precision kept, caption unchanged |

### 9.4 (normative) Honest-fallback panel copy — F6

> **Delta within statistical noise.**
> The before/after confidence intervals overlap, so we cannot claim this remediation moved agent demand on this catalog. The persistent gap is consistent with model-side bias documented in ACES (2025) — which is itself the finding. We do not tune seeds to manufacture a bigger number.

---

## 12. Demo Click-Path (rehearsal script — maps to PRD §15 timing)

| Time | Screen | Action | Spoken line (anchor) |
|---|---|---|---|
| 0:00 | `/` | land | "AI agents are becoming the buyers… agents succeed at curation only 13–38% of the time [AgenticShop]." |
| 0:30 | F1 | (settings pre-filled) click `Run audit` → F2 | "640 real agent decisions…" (ticker runs ~20 s, nulls visible) |
| 0:50 | F2→F3 | auto-redirect | — |
| 0:55 | F3 S1 | heat map; point at sku_007 row | "One SKU alone captured 74% of agent demand. Five SKUs are agent-invisible." |
| 1:30 | F3 S3 | stability matrix | "GPT and Gemini built different bestsellers from the same catalog." |
| 2:00 | F4 | click `sku_023` row | drilldown: "price couldn't be verified…"; read one agent reason aloud |
| 2:30 | F5 | click `Fix what's broken`; diff pre-expanded; approve → rerun | "LLM proposes, human approves…" |
| 3:00 | F6 | delta view | "Score 48 → 71. Recoverable ₹18,200 a month at a 20% agent-share scenario — failure rates measured, traffic share you set." |
| 3:30 | F7 | `Start agent` | watch tool calls → open link → pay (test card) → **banner** |
| 3:50 | F7 | close | "We don't just measure readiness — we prove an agent can buy from you." |

Rules: primary path is the cached manifest run (F2 ticker replays recorded events); live API calls are additive only; if live drifts — *"variance is within our reported CIs."*

---

## 13. Microcopy Appendix (verbatim strings)

| Key | String |
|---|---|
| `setup.h1` | Your next customer might not be human. |
| `setup.cta` | Run audit → 640 agent trials |
| `progress.ticker.null` | → null (nothing fits) |
| `results.strip.caption` | Scenario model. Measured: task-failure rate, concentration, remediation delta. Assumed: agent-traffic share — you set it. |
| `results.invisible.legend` | Hatched = agent-invisible (95% CI upper bound below 2.5% fair share) |
| `drill.verdict.invisible` | 95% CI upper bound below fair share → invisible. |
| `remediate.gate.note` | LLM proposed · human approves · deterministic layer commits |
| `compare.overlap.title` | Delta within statistical noise. |
| `checkout.trust` | The agent never saw a Razorpay key. The backend created this link; the agent only received a URL. |
| `checkout.captured` | ✓ Agent checkout verified |
| `global.ci.tooltip` | 95% confidence interval, persona-cluster bootstrap, B = 2,000 |

*End of APPFLOW v1.0. Changes require version bump + commit referencing affected flows.*
````

**Save:** copy the block → `APPFLOW.md` in repo root → commit: `git add APPFLOW.md && git commit -m "docs: app flow spec v1.0"`.

**Errata action items — Status: Applied** in `PRD.md` §15 (`IMPLEMENTATION.md` wasn't part of this doc set's upload — same fix should be mirrored there if that file resurfaces): "product #17 / SKU #17 (starved tier)" → "sku_023 (starved tier, position 19)", and "3 of 40 SKUs captured 68% of agent demand" → "One SKU alone captured 74% of agent demand". The doc set (PRD → TECHSPEC → APPFLOW → SCHEMA → IMPLEMENTATIONPLAN) is now numerically consistent end to end: 640 trials, sku_023 as the invisible hero, 48→71 with CIs, ₹41,000 RaR @ 20%, ₹18,200 recoverable, ΔF 15.3.

Doc set is complete. The next artifacts in build order are the content fixtures this flow depends on: the 20 persona JSON files + `fixtures/framing_variants.json` (F1/F2 need them Day 3), or `stats/metrics.py` with the V1–V6 validation cases (F3's numbers and `make validate` gate, Day 6). Which one?