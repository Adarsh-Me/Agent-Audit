
# PRD — AgentAudit: AI-Buy-Readiness Audit for Agentic Commerce

| Field | Value |
|---|---|
| Document | Product Requirements Document |
| Version | 1.0 |
| Status | Approved for build |
| Product | AgentAudit |
| Event | Razorpay AI Buildathon — Track 01: AI Growth & Agentic Commerce |
| Submission deadline | September 3 |
| Companion docs | `IMPLEMENTATION.md` (engineering plan), `DEMO.md` (pitch script), `PITCH.md` (narrative) |
| Owners | [you / team] |

---

## 1. Executive Summary

**AgentAudit** is a B2B SaaS tool that answers one question for merchants: **can AI shopping agents actually see, choose, and buy from your catalog?**

The agent-buyer channel is arriving (ChatGPT, Gemini, Operator-style agents, AP2/x402 payment protocols), and published research shows it is already broken: agents succeed at personalized product curation only 13–38% of the time, hallucinate product references, concentrate demand on a handful of "modal" products, are biased by listing position and framing, and change preferences abruptly across model versions.

AgentAudit operationalizes this research into a product. It runs **randomized, controlled shopping trials** with real LLM agents against a merchant's catalog, measures **choice behavior** (concentration, position bias, framing sensitivity, coverage failure, cross-model stability), and converts findings into:

1. An **AgentReady Score (0–100)** with sub-metric breakdown and confidence intervals,
2. A **Revenue-at-Risk scenario model in rupees** with every input labeled measured vs. assumed,
3. A **per-product remediation report** and a before/after re-run loop, and
4. An end-to-end proof point: **an autonomous agent completing a real Razorpay test-mode payment.**

The wedge for Razorpay: as agent-mediated payments scale, illegible merchants are invisible in that channel. AgentAudit is the readiness layer designed to run as a background job on merchant onboarding — protecting checkout volume that flows through Razorpay.

---

## 2. Background & Problem Statement

### 2.1 The third reader

For 20 years merchants optimized their catalogs for two readers: human eyes (UX, merchandising) and Google's crawler (SEO, structured data). A third reader is arriving — autonomous shopping agents that browse, compare, and transact on a customer's behalf. This reader is unlike both predecessors: it *chooses* (so ranking isn't enough — the full listing must persuade), it is *nondeterministic* (so stability must be measured, not assumed), and it *transacts* (so checkout must be agent-legible).

### 2.2 The measurement gap

No tool exists that measures agent choice behavior against a specific merchant's catalog:

- **SEO tools** optimize ranking signals for crawlers. They say nothing about how an autonomous buyer *chooses among* products.
- **LLM-visibility tools** (emerging) check "can an LLM answer questions about your brand." They don't run controlled choice experiments, don't measure position/framing bias, and don't produce an actionable per-product fix list.
- **Academic benchmarks** (WebShop, WebMall, AgenticShop) evaluate *agents*, not *catalogs*. They measure how good the agent is. Nobody measures how good the catalog is. AgentAudit inverts the benchmark: the catalog is the test subject; agents are the measurement instrument.

### 2.3 Why now

1. **Agent shopping is live at scale.** Search-augmented LLMs (ChatGPT Search, Gemini with grounding, Perplexity) already influence product discovery; Operator-style agents already execute purchases.
2. **Payment rails for agents are being laid.** The Agent Payments Protocol (AP2) — an open protocol from Google with 60+ payments/tech organizations including Stripe, PayPal, Mastercard, Coinbase, Adyen — plus Coinbase's x402 define how agents will transact. When the payment side standardizes, the bottleneck moves to the merchant side: catalog legibility.
3. **The failure is documented, not speculative.** AgenticShop (2026) measured 62–86% task failure rates for open-web curation; ACES (2025) measured systematic choice concentration, position bias, and model-version instability.
4. **For India specifically**, UPI-first checkout and a merchant base of millions make the readiness gap a volume problem for any PSP — including Razorpay.

### 2.4 Problem statements (formal)

| # | Problem | Whose problem | Today's workaround |
|---|---|---|---|
| PS-1 | Merchants cannot see how AI agents choose among their products | Merchant | None — invisible failure mode |
| PS-2 | Merchants cannot tell which products are agent-invisible and why | Merchant | Guesswork, SEO heuristics |
| PS-3 | Merchants cannot quantify the rupee exposure of agent-channel illegibility | Merchant / PSP | None |
| PS-4 | Fixes are applied blind — no way to verify a metadata fix actually moved agent demand | Merchant / agency | Re-run ads and pray |
| PS-5 | Agent-channel revenue depends on which model a customer uses, and shifts when providers ship model updates | Merchant / PSP | None — undetectable without measurement |
| PS-6 | No proof an agent can complete checkout end-to-end on a given merchant | PSP | Manual testing |

AgentAudit addresses PS-1 through PS-6 directly.

---

## 3. Research Foundation

This section documents every research input, precisely what is borrowed, and — equally important — what is **deliberately not claimed**. This discipline is a product feature: every number in the UI traces to either a measured trial or a labeled assumption.

### 3.1 ACES — "What Is Your AI Agent Buying? Evaluation, Biases, Model Dependence, & Emerging Implications for Agentic E-Commerce"

- **Citation:** Allouah, A., Besbes, O., Figueroa, J.D., Kanoria, Y., Kumar, A. — arXiv:2508.02630 (2025, revised through 2025-12).
- **What it is:** A provider-agnostic auditing framework (ACES) that runs randomized, dialog-driven purchase trials with commercial shopping agents across multiple providers and models, and measures their decision behavior.
- **Core findings (as reported):**
  1. **Modal concentration:** agents cluster demand on a small set of "modal" products rather than spreading demand the way a fully-informed rational shopper might.
  2. **Model dependence:** which products become modal can shift drastically after a routine model update — agent-channel market share is version-fragile.
  3. **Position and framing bias:** agents exhibit measurable position bias (preference by listing order) and framing bias (sensitivity to how products are described), varying by provider and model version.
- **What AgentAudit borrows (mapped to requirements):**
  - **The core experimental paradigm** (randomized controlled trials against product listings) → FR-3 Trial Engine.
  - **Choice-concentration measurement** → M-1 HHI (§8.4).
  - **Position-bias measurement via order randomization** → Condition C2 → M-2.
  - **Framing measurement via listing-variant comparison** → Condition C3 → M-3.
  - **Cross-model stability comparison** → M-5 stability matrix; motivates FR-15 scheduled re-audit in the production roadmap.
- **What we explicitly do NOT take:** ACES documents *model-side* bias — it does **not** establish that merchant-side metadata fixes change agent choices. Therefore AgentAudit's remediation claims are scoped to the levers ACES implicates as merchant-controllable (framing, titles, position, data completeness), the legibility-visibility correlation is labeled **diagnostic, not causal**, and cross-model instability is surfaced as a *finding*, not promised as fixable. This is Limitation L-1/L-2 (§19) and Judge-Q&A item 1 (§20).
- **Where it appears in-product:** cited in report footer; the stability matrix page carries the line "agent-channel bestsellers can shift with model updates (ACES, 2025)."

### 3.2 AgenticShop — "Benchmarking Agentic Product Curation for Personalized Web Shopping"

- **Citation:** Kim, S., et al. — arXiv:2602.12315 (Feb 2026).
- **What it is:** The first benchmark for evaluating agentic systems on **personalized product curation** in an open-web environment: 350 personalized shopping tasks across 50 user profiles and 7 scenarios, grounded in real Amazon purchase histories; evaluated across search-augmented LLMs (ChatGPT Search, Claude, others) and agent types.
- **Core findings (as reported):**
  1. Current agentic systems achieve only **13.56–37.93%** curation success — i.e., 62–86% task failure.
  2. **ChatGPT Search hallucinates approximately 20% of product references.**
  3. Failure modes are disaggregated (invalid page, irrelevant page, etc.) — failure is structured, not random.
- **What AgentAudit borrows:**
  - **Motivation statistics** for the pitch and report header ("agents fail 62–86% at curation — is your catalog part of that failure?").
  - **Persona-driven task design** (their 50 profiles → our 20 persona files, FR-3.1).
  - **The coverage-failure framing**: their headline number is a *task failure rate*; our null-choice trials (FR-4) measure the merchant-side analog — the fraction of agent tasks a given catalog cannot serve. This is what makes our Revenue-at-Risk model (FR-9) measured rather than invented.
- **What we do NOT take:** their open-web benchmark harness (we run closed-catalog trials for control and reproducibility); their success definition (we invert it — catalog-side coverage, not agent-side success).
- **Where it appears in-product:** the intro slide, the report header stat, and the Revenue-at-Risk context line.

### 3.3 WebMall — "A Multi-Shop Benchmark for Evaluating Web Agents"

- **Citation:** Peeters, R., Steiner, A., Schwarz, L., et al. (University of Mannheim) — arXiv:2508.13024 (2025).
- **What it is:** The first offline **multi-shop** benchmark for web agents: four simulated shops populated with authentic product offers extracted from Common Crawl (hundreds of distinct real-world shops), with 91 cross-shop tasks — finding products, price comparison, cart, checkout, plus advanced tasks (vague requirements, substitutes, compatible products).
- **What AgentAudit borrows:**
  - **Design precedent that catalog evaluation environments belong in research** — positions us as the applied/productized sibling of this line of work.
  - **Heterogeneous listing data**: their shops deliberately vary description quality/format — mirrored in our demo-store quality tiers (FR-2.2).
  - **Related-work framing** in the PRD/pitch: single-shop benchmarks (WebShop) → multi-shop (WebMall) → merchant-side audit (AgentAudit).
- **What we do NOT take:** multi-shop comparison is out of MVP scope; it is roadmap item R-4.
- **Where it appears in-product:** README related work; future "compare your catalog's agent-legibility vs. category benchmarks."

### 3.4 Agent Payments Protocol (AP2) — specification (not a paper)

- **Citation:** AP2, ap2-protocol.org, v0.2; announced by Google with 60+ collaborating organizations (Adyen, American Express, Coinbase, Etsy, Mastercard, PayPal, Stripe, and others); an open extension of the Agent2Agent (A2A) protocol, designed to work alongside MCP; uses signed mandates / verifiable credentials for agent-led payment authorization.
- **What AgentAudit borrows:**
  - **Directional framing** for the Razorpay pitch: the payment rails for agent commerce are standardizing; the merchant-readiness layer is the missing complement. AgentAudit tests agent-legibility of *checkout* today (Razorpay Payment Links) and is architecturally ready for mandate-style flows (roadmap R-3).
- **What we do NOT claim:** AP2 conformance. We say "designed to integrate" — never "AP2-compatible" — until tested against a stable spec. Claim discipline is codified in §19.

### 3.5 EzyBuyy — "An Agentic AI-Based Multi-Agent Framework for Conversational Product Discovery and Price Negotiation"

- **Citation:** Roy, K., Sotiya, A., Najish, M., Alam, S., Walia, A. — IJFMR, v8 i2 (2026), DOI 10.36948/ijfmr.2026.v08i02.76075.
- **What it is:** A supervisor-orchestrated multi-agent conversational commerce system: product-search agent (semantic interpretation), negotiation agent (constrained dynamic bargaining), order agent (post-purchase support), plus an AI copilot for automated product onboarding via computer vision + generative AI.
- **What AgentAudit borrows:**
  - **Evidence of demand** for agentic shopping flows (their reported engagement/discovery-time improvements) — supports "the buyer side is coming."
  - **The catalog-copilot pattern**: their product-onboarding copilot is the spiritual ancestor of our Remediation Engine (FR-10) — LLM-assisted catalog improvement, bounded by rules and human review.
  - **Constrained-agent discipline**: their negotiation agent operates under predefined constraints; analogously, our trial agents operate under a forced JSON schema, and our checkout agent can only execute policy-bounded tool calls.
- **Where it appears in-product:** references; the remediation-review UI notes its lineage ("LLM proposes, human approves, deterministic layer commits").

### 3.6 Papers evaluated and intentionally not used

| Paper | Why not used |
|---|---|
| *Autonomous Decision Systems for Dynamic Pricing* (Shrivastava, 2025) | Prices the catalog; we measure how agents choose. Different problem; adjacent future work (elasticity-measurement angle). |
| Track-02 fraud papers (TGN, FraudGraph-X, SAGE, SHERLOCK, Co-Investigator AML) | Fraud/risk domain — different track; none inform choice-behavior measurement. |
| Track-03 recovery papers (Offline CQL, retention off-policy, NBA) | Recovery-after-failure domain; not used in this product. |
| SAFEFLOW / MemTX (Track 05) | Execution-trust middleware; our trial engine is read-only and side-effect-free by design, so transactional memory guarantees are out of scope. Noted as roadmap consideration if AgentAudit grows tool-executing agents. |

### 3.7 Research-to-requirement synthesis matrix

| Research input | Finding borrowed | Requirement it drives |
|---|---|---|
| ACES | RCT-over-listings paradigm | FR-3 Trial Engine |
| ACES | Choice concentration | M-1 HHI; FR-8 score component |
| ACES | Position bias | C2 shuffles; M-2; FR-8 component |
| ACES | Framing bias | C3 A/B; M-3; FR-10 remediation levers |
| ACES | Model-version instability | M-5 stability matrix; R-2 scheduled re-audit |
| AgenticShop | 62–86% task failure | Pitch stat; FR-4 null-choice coverage |
| AgenticShop | Persona-driven tasks | FR-3.1 persona files |
| WebMall | Heterogeneous listing data | FR-2.2 demo-store tiers |
| WebMall | Multi-shop evaluation gap | R-4 roadmap |
| AP2 | Agent payment rails standardizing | FR-13 checkout proof; R-3 mandate testing |
| EzyBuyy | Catalog copilot pattern; constrained agents | FR-10 remediation engine; agent schema discipline |

---

## 4. Goals, Non-Goals, Success Metrics

### 4.1 Product goals

1. **G1 — Measure:** produce reproducible, CI-bearing measurements of agent choice behavior against a specific catalog.
2. **G2 — Explain:** attribute invisibility to per-product, merchant-actionable causes.
3. **G3 — Quantify:** translate measurements into a rupee-denominated scenario model with labeled inputs.
4. **G4 — Fix and verify:** apply remediations to a mirrored catalog and *prove* the delta by re-running trials.
5. **G5 — Prove end-to-end:** demonstrate an agent completing a Razorpay test-mode payment.
6. **G6 — Earn trust:** every number in the UI traces to a measured trial, a cited paper, or a labeled assumption. No exceptions.

### 4.2 Non-goals (explicit)

- **NG-1** HTML scraping of live storefronts (amended 2026-08-23: the Shopify public-product-feed
  import in `app/ingest/store.py` is *authorized catalog reads* — JSON feed, no HTML parsing, no
  auth, ≤4 paginated GETs, snapshot-at-import — not scraping; generic site crawling remains a
  non-goal).
- **NG-2** Optimizing merchant sites for any specific model provider ("we don't do SEO for GPT").
- **NG-3** Building a shopping agent for consumers (we build the *auditor*, not the buyer).
- **NG-4** Causal claims that metadata fixes drive agent revenue (diagnostic correlation only, until A/B data exists).
- **NG-5** Production multi-tenancy, billing, auth (hackathon scope: single-workspace demo).
- **NG-6** AP2 conformance claims.

### 4.3 Success metrics

**Hackathon (must hit all):**

| Metric | Target |
|---|---|
| Full audit on 40-product demo store | completes end-to-end |
| `make validate` (6 planted-bias cases) | green |
| Before/after remediation delta | non-overlapping 95% CIs |
| Razorpay test payment via agent | succeeds live |
| Demo rehearsal | 3 consecutive clean runs ≤ 4:30 |
| Total LLM spend | ≤ $35 |

**Product (post-event validation):**

| Metric | Target |
|---|---|
| Audit wall-clock time (40 SKUs, ~640 trials) | < 15 min |
| Trial parse-failure rate | < 5% per model |
| Cache hit rate on re-runs | > 90% |
| Dashboard p95 read latency | < 300 ms |

---

## 5. Users & Use Cases

### 5.1 Target users

| Persona | Description | Primary job-to-be-done |
|---|---|---|
| **U1 — D2C merchant founder** (primary) | Runs a Shopify/D2C store, ₹5–50L monthly GMV | "Will AI agents selling for my customers find my products?" |
| **U2 — PSP platform/product manager** (Razorpay judge archetype) | Owns merchant-facing value-adds at a payments company | "Does this protect/grow checkout volume for our merchants?" |
| **U3 — Agency/growth operator** | Manages catalogs/SEO for multiple merchants | "A defensible, measurable audit deliverable per client" |

### 5.2 User stories

- **US-1 (U1):** "Run an audit on my catalog and tell me which products AI agents can't see, in under 15 minutes."
- **US-2 (U1):** "Show me hard numbers, not vibes — with confidence intervals I can show my cofounder."
- **US-3 (U1):** "Tell me what this costs me in rupees, and what's measured vs. assumed."
- **US-4 (U1):** "Give me a fix list I can hand to my catalog team, and re-run to prove it worked."
- **US-5 (U2):** "Show me this running automatically when a merchant onboards."
- **US-6 (U2):** "Prove an agent can complete checkout on a merchant using your stack."
- **US-7 (U3):** "Export a per-client report with citations I can put my logo on."

---

## 6. Core Concepts & Definitions

| Term | Definition |
|---|---|
| **Trial** | One agent shopping decision: (model, persona, condition, seed, presented order) → choice or null |
| **Run** | A full battery of trials over one catalog version (~640 trials) |
| **Condition** | Experimental manipulation of the listing presentation: C1 baseline, C2 shuffle, C3 framing A/B |
| **Persona** | Structured buyer profile + shopping task driving a trial |
| **Null choice** | Agent returns `product_id: null` = "no suitable product" |
| **Coverage failure (F_task)** | Null-choice rate across null-allowed trials — the merchant-side analog of AgenticShop's task-failure rate |
| **Agent-invisible product** | Product whose 95% share CI upper bound is below fair-share (1/N) — corrected from an earlier 2/N draft; fair share for N=40 is 2.5% (TECHSPEC errata E-3) |
| **AgentReady Score** | Weighted 0–100 composite: visibility, stability, position-independence, coverage, data completeness |
| **Revenue at Risk** | `GMV × S_agent × F_task` — scenario model; F_task measured, S_agent user-assumed |
| **Mirrored catalog** | Copy of catalog with remediations applied; trials re-run against it |
| **Legibility** | Per-product structured-data completeness + content quality (checklist composite) |

---

## 7. Functional Requirements

Priorities: **M** = must (hackathon-blocking), **S** = should, **C** = could (stretch).

### FR-1 Catalog ingestion (M)
Accepts (a) the built-in demo store, (b) JSON/CSV upload validated against the canonical schema. Normalizes to canonical `Product` records. Rejects with field-level errors.
*AC:* uploading a 40-row CSV yields 40 canonical products; malformed rows return precise error messages; no scraping code paths exist in MVP.

### FR-2 Demo store (M)
40 products, 4 categories × 10 (bottles, headphones, backpacks, fitness gear), 3 deliberate quality tiers (10 rich / 20 medium / 10 starved), served as static site with `/catalog.json` and `llms.txt`. **Tier and position are decorrelated in baseline order** (tiers distributed across positions 1–40 via balanced assignment) so position bias and quality effects are separable.
*AC:* `GET /catalog` returns 40 valid records; tier distribution verified by test; baseline-order tier/position correlation |ρ| < 0.15.

### FR-3 Trial engine (M)
Executes the run matrix: 20 personas × 3 bulk models × conditions × seeds ≈ 600 trials, plus a flagship pass (~40 trials, 2 flagship models, C1 only).
*AC:* full run completes < 15 min; every trial logged with model **version**, seed, presented order, choice, reason, latency, prompt hash; parse failures retried ≤ 3 with error feedback and reported per model.

### FR-4 Null-choice coverage trials (M)
The response schema permits `{"product_id": null}` in **all C1 and C2 trials**; **C3 framing trials force choice** (share-shift measurement requires a decision). Coverage failure F_task computed from C1+C2.
*Rationale (design decision, documented in-product):* forced-choice trials measure *where demand goes when it goes somewhere*; null-allowed trials measure *whether it goes anywhere*. Both are needed; conflating them corrupts both numbers.
*AC:* F_task reported with Wilson 95% CI; C3 contains zero null responses by construction.

### FR-5 Statistics layer (M)
Computes M-1…M-6 (§8.4) with bootstrap CIs (cluster bootstrap by persona, B = 2,000).
*AC:* all headline metrics ship with CI; CIs present in API payload and dashboard.

### FR-6 Validation suite (M)
Six planted-bias cases (§8.4.8) run in CI via `make validate`.
*AC:* all six pass; suite is a first-class repo artifact referenced from the README.

### FR-7 Legibility audit (M)
Per-product checklist: JSON-LD present, price present in structured data, price freshness, availability, image, description quality, title quality (last two via LLM-as-judge, mini tier, rubric-pinned prompt).
*AC:* every product has a legibility composite ∈ [0,1] with per-item pass/fail visible in drilldown.

### FR-8 AgentReady Score (M)
Five components, 20% each (§8.5). Weights in `scoring/config.yaml`. Reported with CI and full sub-metric breakdown — **never as a bare number.**
*AC:* score bounds [0,100]; changing weights in config changes score accordingly (tested); CI shown.

### FR-9 Revenue-at-Risk module (M)
Scenario model (§8.6): `RaR = GMV × S_agent × F_task`; `Recoverable = GMV × S_agent × (F_before − F_after)`. GMV user input (default ₹8L), S_agent slider (1/5/10/20%), F measured. Every input labeled **[measured]** / **[assumed]** / **[input]** in the UI.
*AC:* strip renders three numbers + slider; labels visible; F CIs propagate to rupee CIs.

### FR-10 Remediation engine (M)
Generates mirrored catalog: injects JSON-LD, refreshes price fields, rewrites starved-tier titles/descriptions (LLM-generated, one-time human review gate). Levers prioritized by what ACES implicates as merchant-controllable.
*AC:* mirrored catalog passes schema validation; diff view shows original vs. fixed per product; human-review gate exists before re-run.

### FR-11 Re-run loop (M)
Re-executes the trial battery against the mirrored catalog; outputs score delta, per-product visibility delta, rupee delta — all with CIs. **Delta rule:** if before/after CIs overlap, we strengthen remediation levers or present the honest model-side-bias narrative. We never tune seeds to inflate deltas (§17).
*AC:* delta view renders; overlapping-CI case triggers the fallback narrative state in UI.

### FR-12 Dashboard (M)
Pages: Audit setup → live progress (SSE trial ticker) → results (three-number strip, heat map, position curve, stability matrix, coverage dial, framing chart, product table) → product drilldown → remediation review (diff) → before/after. Full copy spec in §11.
*AC:* every number on screen traces to API metric payload with CI; no hardcoded values in frontend.

### FR-13 Agent checkout — Razorpay (M)
Function-calling agent with MCP tools: `list_products`, `get_product`, `create_payment_link` (backend → Razorpay Payment Link API, test mode). Razorpay webhook `payment.captured` → "Agent checkout verified ✓" badge.
*AC:* live payment succeeds end-to-end; webhook updates dashboard in < 5 s.

### FR-14 MCP server (S)
Exposes the three tools over MCP. If Razorpay ships an official MCP server pre-deadline, integrate theirs and keep `create_payment_link` as ours.
*AC:* a third-party MCP client can drive a purchase.

### FR-15 Onboarding webhook (S)
`POST /webhooks/merchant-onboarded` (simulated Razorpay onboarding event) auto-triggers an audit and returns the report — the background-job-on-onboarding pattern.
*AC:* single curl triggers full audit; result lands in dashboard.

### FR-16 Response cache (M)
Key = `sha256(model_version + prompt + seed)`. Identical trials are never re-billed.
*Correction (SCHEMA errata SC-3):* an earlier draft of this requirement assumed only remediated products' trials re-execute on rerun. That's wrong — every trial prompt embeds the **full 40-product listing**, so changing *any* product's copy changes *every* prompt hash. A **post-remediation rerun is therefore a full fresh 640-trial run (~$10–15, 2–4 min)**, not a partial cache hit. The cache still does its job for the case it actually covers: an **unchanged-catalog** re-run (e.g. re-running the same audit for reproducibility, or a scheduled model-version watch re-audit where the catalog hasn't changed).
*AC:* re-run of an **unchanged** catalog is ~100% cache-served and completes < 60 s. A remediation rerun (mirrored catalog) is a full run and is budgeted/timed as such (see §9 Budget Ledger equivalent in IMPLEMENTATIONPLAN §7).

### FR-17 Export (C)
PDF/markdown report export with citations, for U3 (agencies).
*AC:* exported report matches dashboard numbers.

### FR-18 Model-version watch (C — roadmap R-2, surfaced in UI as "coming")
Banner concept: "Model versions changed since your last audit — re-audit recommended (per ACES model-instability findings)."

---

## 8. Detailed Specifications

### 8.1 Canonical product schema

```json
{
  "id": "sku_017",
  "title": "AquaSteel Pro 1L Insulated Bottle — Matte Black",
  "price_inr": 749,
  "description": "Double-walled 18/8 steel; 24h cold, 12h hot; 290g; leak-proof cap; BPA-free.",
  "image_url": "https://demo.agentaudit.dev/img/sku_017.png",
  "page_url": "https://demo.agentaudit.dev/p/sku_017",
  "tier": "rich",
  "structured_data": {
    "jsonld_present": true,
    "fields_present": ["name", "price", "availability", "image", "brand", "aggregateRating"],
    "price_fresh": true,
    "title_quality": 0.9,
    "description_quality": 0.85
  }
}
```

Tier definitions:

| Field | Rich (10) | Medium (20) | Starved (10) |
|---|---|---|---|
| JSON-LD fields | 6+ incl. brand, rating | name + price only | absent |
| Price in structured data | present, fresh | present, possibly stale | **absent (page-only)** |
| Description | 60 words, spec-rich | ~25 words, generic | ≤ 10 words ("Good quality bottle.") |
| Title | benefit + spec + variant | category + variant | bare category ("Water Bottle") |
| Availability / image | present | partial | absent |

### 8.2 Personas (all 20)

| ID | Archetype | Task (verbatim given to agent) | Budget | Category pull |
|---|---|---|---|---|
| P01 | Budget student | "cheapest decent water bottle for daily college use" | ₹300 | bottles |
| P02 | Gift buyer | "gift for a runner friend" | ₹2,000 | fitness/bottles |
| P03 | Spec hound | "best battery-life earbuds" | ₹3,500 | headphones |
| P04 | Eco buyer | "most sustainably made bottle; price secondary" | — | bottles |
| P05 | Commuter | "backpack fitting 15\" laptop + gym gear" | ₹3,000 | backpacks |
| P06 | Premium seeker | "best headphones in the store, budget flexible" | ₹15,000 | headphones |
| P07 | Deal hunter | "best value-for-money item in this store" | — | cross |
| P08 | Urgent buyer | "any reasonable water bottle, fastest delivery" | ₹1,000 | bottles |
| P09 | Brand loyalist | "prefer well-known brands" | ₹5,000 | cross |
| P10 | Minimalist | "plain, understated design, nothing flashy" | ₹2,500 | cross |
| P11 | Fitness newcomer | "starter fitness gear" | ₹1,500 | fitness |
| P12 | Parent | "durable backpack for a 12-year-old" | ₹1,200 | backpacks |
| P13 | Podcast listener | "comfortable headphones for 4h+ listening sessions" | ₹4,000 | headphones |
| P14 | Gym regular | "shaker/gym bottle for daily use" | ₹800 | bottles/fitness |
| P15 | Trekker | "hydration setup for day hikes" | ₹2,000 | bottles/fitness |
| P16 | WFH professional | "headphones for long video calls" | ₹5,000 | headphones |
| P17 | Gift-card spender | "spend a ₹1,000 gift card well" | ₹1,000 | cross |
| P18 | Comparison shopper | "single best overall value across all categories" | — | cross |
| P19 | Trend follower | "whatever's most popular / best-rated" | ₹3,000 | cross |
| P20 | Skeptic | "only products with clear warranty or return info" | ₹4,000 | cross |

Each persona file: `{id, name, profile_summary (2 lines), task, budget_inr, null_plausible: bool}`. P04, P09, P10, P20 are null-plausible by design (requirements the starved tier cannot satisfy) — this gives the coverage metric signal without engineering nulls.

### 8.3 Trial engine

**Run matrix (bulk tier, per model):**

| Condition | Trials | Null allowed? |
|---|---|---|
| C1 baseline × 3 seeds | 60 | yes |
| C2 shuffle × 3 orders (seeded) | 60 | yes |
| C3-A / C3-B framing variants × 2 seeds | 80 | no (forced choice) |
| **Per model** | **200** | |
| × 3 bulk models | **600** | |
| Flagship pass (2 models × 20 personas × C1 × 1 seed) | 40 | yes |
| **Total per full audit** | **≈ 640** | |

**Prompt template:**

```
You are an autonomous shopping agent acting on behalf of a customer.

Customer persona: {persona.profile_summary}
Shopping task: {persona.task}
Budget: {persona.budget or "flexible"}

Below is the merchant's current product listing, in presented order:

{numbered_listings}   # "1. {title} | ₹{price or 'price on request'} | {description}"

Select exactly ONE product to purchase on the customer's behalf — or return
null if no product genuinely fits. Respond with valid JSON only:
{"product_id": "...", "reason": "..."}  |  {"product_id": null, "reason": "..."}
```

(C3-B trials substitute variant titles/descriptions for the 10 framing-subset products; C3-A uses originals.)

**Execution parameters:**

- Bulk models: `gpt-4o-mini`, `gemini-flash-1.5`, `claude-haiku` (exact version IDs pinned in `engine/models.yaml`; version logged per trial).
- `temperature: 1.0`; seed recorded where the provider accepts one.
- JSON mode enforced where available; parse pipeline: strip fences → JSON parse → validate `product_id ∈ catalog ∪ {null}`.
- Retries: 3× exponential backoff (1s/2s/4s) with error feedback appended; parse-failure rate reported per model (itself a finding).
- Concurrency: 10 parallel; per-provider rate-limit guard; circuit breaker after 10 consecutive failures.
- **Hard cost cap: $30/run** (config) — run aborts gracefully with partials marked.

### 8.4 Statistics layer (exact definitions)

**8.4.1 M-1 Choice concentration.** `HHI = Σᵢ sᵢ²` over non-null choices (sᵢ = share of product i). Normalized: `HHI_norm = (HHI − 1/N) / (1 − 1/N)`, N = catalog size (40). Range [0,1]; 0 = uniform, 1 = monopoly. Reported per model (C1) and pooled.

**8.4.2 M-2 Position bias.** From C2 non-null trials: top-3 capture rate = share of trials whose chosen product sat in presented slots 1–3. Chance = 3/40 = 7.5%. `Lift = capture / 0.075`. Significance: permutation test — permute slot assignments 10,000×, p = fraction of permutations with capture ≥ observed. Also plot per-slot choice distribution (position curve).

**8.4.3 M-3 Framing sensitivity.** For each framing-subset product p: `Δp = |share_A(p) − share_B(p)|` (C3-A vs C3-B, per model, pooled across models with model-stratified reporting). Report mean Δ with paired bootstrap CI, plus displacement map (which products gained/lost share between variants).

**8.4.4 M-4 Coverage failure.** `F_task = nulls / trials` over null-allowed trials (C1+C2). Wilson score 95% CI. This is the measured anchor for FR-9.
*Scope note (added for clarity — resolves an ambiguity against TECHSPEC §22's trial-count appendix, which buckets flagship trials as "null-allowed" too):* **flagship trials are excluded from the F_task calculation**, consistent with M-5's exclusion of flagship from the stability matrix for the same reason — 40 flagship trials is too thin a sample to pool cleanly with the 400-trial bulk denominator without needing a stratified estimator. Flagship nulls are still logged and shown separately as narrative color, never folded into the headline F_task number.

**8.4.5 M-5 Cross-model stability.** Choice-share vectors per model (C1, non-null). Pairwise cosine similarity; report full 3×3 matrix + mean. Bands: >0.8 aligned · 0.5–0.8 moderate · <0.5 divergent. Caption: "low similarity = your agent-channel bestsellers depend on the customer's AI provider."

**8.4.6 M-6 Agent-invisibility.** Product i is *agent-invisible* if the upper bound of its 95% share CI < 1/N (significantly below fair-share — corrected from an earlier 2/N draft; fair share for N=40 is 2.5%, TECHSPEC errata E-3). The invisible set is a headline ("5 of 40 SKUs are agent-invisible").

**8.4.7 Confidence intervals.** Nonparametric cluster bootstrap: resample personas with replacement (B = 2,000), recompute metric, percentile CI. Cluster level = persona because trials within a persona correlate. Every headline number carries its CI end-to-end (API → dashboard → export).

**8.4.8 Validation suite (planted-bias ground truth).** Synthetic trial generators with known parameters:

| # | Planted truth | Must recover |
|---|---|---|
| V1 | Monopoly (one product takes all choices) | HHI_norm ∈ [0.95, 1.0]; N−1 invisible products |
| V2 | Uniform | HHI_norm ∈ [0, 0.05] |
| V3 | 80% slot-1 preference | Lift detected; permutation p < 0.001 |
| V4 | Two models, disjoint preferences | Mean pairwise cosine < 0.1 |
| V5 | Known A/B share swap (±25 points on 2 products) | Framing sensitivity ≈ planted delta within CI |
| V6 | 30% null rate | Wilson CI contains 0.30 |

`make validate` runs all six in CI. **A metric that fails its planted case does not ship.**

### 8.5 AgentReady Score

```
score = 100 × ( 0.20·visibility          # 1 − HHI_norm
              + 0.20·stability           # mean pairwise cosine (clamped [0,1])
              + 0.20·position_indep      # clamp(1 − (Lift − 1)/4, 0, 1)
              + 0.20·coverage            # 1 − F_task
              + 0.20·data_completeness ) # mean legibility composite
```

- Weights in `scoring/config.yaml`; documented; sensitivity note in UI ("weights are a design choice — see README").
- Score CI propagated through the persona-cluster bootstrap (resample → recompute all five components → recompute score).
- Interpretation bands (UI copy): 80+ agent-ready · 60–79 partially visible · <60 significant agent-channel leakage.

### 8.6 Revenue-at-Risk model

```
Revenue at Risk (₹/mo)     = GMV_m × S_agent × F_task
Recoverable GMV (₹/mo)     = GMV_m × S_agent × (F_before − F_after)
```

| Input | Source | Label |
|---|---|---|
| GMV_m | User input; demo default ₹8,00,000 | [input] |
| S_agent | UI slider: 1 / 5 / 10 / 20% | **[assumed]** |
| F_task | Measured null rate (Wilson CI) | **[measured]** |
| F_before − F_after | Before/after runs (bootstrap CIs) | **[measured]** |

UI caption (verbatim): *"Scenario model. Measured: task-failure rate, concentration, remediation delta. Assumed: agent-traffic share — you set it."*
Context line: *"AgenticShop (2026) reports 62–86% task failure for open-web agent shopping; your number is measured on your catalog."*
Concentration and stability are displayed as supporting findings but deliberately **excluded from the rupee formula** — we only monetize the failure mode we can measure cleanly.

### 8.7 Remediation engine

- Input: audit report. Output: mirrored catalog + per-product fix list.
- Fix classes, in priority order: (1) inject/complete JSON-LD; (2) sync price into structured data; (3) rewrite starved-tier title (benefit + spec + variant); (4) expand description to spec-rich 40–60 words; (5) add availability/image.
- Classes 3–4 are LLM-generated from a pinned rubric prompt; **one-time human review gate** (diff UI) before the mirrored catalog is finalized — the EzyBuyy-copilot lineage: *LLM proposes, human approves, deterministic layer commits.*
- Framing-variant fixtures (`fixtures/framing_variants.json`) are human-authored ahead of time for the demo store so C3-B and remediation text are stable, reviewable artifacts — not live-generated moving parts in the demo path.

### 8.8 Agent checkout

Flow: MCP client → `list_products` (persona-driven reasoning, demo persona fixed: P07) → `get_product` → `create_payment_link` → backend calls Razorpay Payment Links API (test mode) → short URL returned → agent surfaces link → payment page → `payment.captured` webhook → dashboard badge "Agent checkout verified ✓" with timestamp and payment id.
Security notes: backend holds Razorpay secrets; MCP tool never sees them; link creation is idempotent per (run, product) with a stored idempotency key.

---

## 9. Data Model

*This section is an illustrative summary. `SCHEMA.md` §6 is the authoritative DDL — it adds several columns this summary omits (`entity_key`, `parent_catalog_id`, `parent_run_id`, `remediations.status`, `trials.tier`, `trials.from_cache`) that the remediation and webhook flows depend on. Where they differ, SCHEMA.md governs.*

```
merchants(id, name, gmv_monthly_inr, aov_inr, created_at)
catalogs(id, merchant_id, source ENUM(demo,upload,mirror), parent_catalog_id UUID NULL, version, created_at)
products(id, catalog_id, sku, title, price_inr, description, image_url,
         page_url, tier ENUM(rich,medium,starved), structured_data JSONB,
         legibility_composite FLOAT)
runs(id, catalog_id, type ENUM(audit,rerun), status ENUM(queued,running,
     done,failed,partial), models JSONB, seeds JSONB, cost_usd FLOAT,
     started_at, completed_at)
trials(id, run_id, model TEXT, model_version TEXT, persona_id TEXT,
       condition TEXT, seed INT, presented_order JSONB, choice TEXT NULL,
       reason TEXT, latency_ms INT, prompt_hash TEXT,
       null_allowed BOOL, parse_ok BOOL, created_at)
response_cache(prompt_hash TEXT, model_version TEXT, response JSONB,
               created_at, PRIMARY KEY(prompt_hash, model_version))
metrics(id, run_id, key TEXT, value FLOAT, ci_low FLOAT, ci_high FLOAT,
        payload JSONB)   -- one row per metric per run
remediations(id, run_id, product_id, fixes JSONB, reviewed_by TEXT,
             applied_at)
payments(id, run_id, razorpay_link_id, amount_inr, status,
         captured_at, idempotency_key)
webhook_events(id, source ENUM(razorpay,merchant_onboarding), type TEXT,
               payload JSONB, processed_at)
```

Indexes: `trials(run_id)`, `trials(prompt_hash)`, `response_cache(PK)`, `metrics(run_id, key)`.

---

## 10. API Specification

| Method | Path | Request | Response (abridged) |
|---|---|---|---|
| POST | `/api/audit` | `{catalog_source: "demo"\|"upload", upload_id?, gmv_inr}` | `{audit_id, status: "queued", trials_total: 640}` |
| GET | `/api/audit/{id}` | — | `{status, trials_done, trials_total, cost_usd, eta_s}` |
| GET | `/api/audit/{id}/metrics` | — | `{hhi_norm: {value, ci_low, ci_high}, position_lift: {..., p_value}, framing_sensitivity: {...}, coverage: {f_task, ci_low, ci_high}, stability: {matrix, mean}, invisible_skus: [...], score: {value, ci_low, ci_high, components: {...}}}` |
| GET | `/api/audit/{id}/report` | — | per-product findings, legibility checklists, remediation list, revenue model with labels |
| POST | `/api/audit/{id}/remediate` | — | `{mirror_catalog_id, fixes: [{sku, fix_classes[], diff}]}` (status `pending_review`) |
| POST | `/api/audit/{id}/rerun` | `{mirror_catalog_id}` | `{rerun_id, delta: {score: {...}, f_task: {...}, recoverable_inr: {...}}}` |
| GET | `/catalog` · `/catalog/{sku}` | — | canonical product JSON |
| POST | `/webhooks/razorpay` | Razorpay signature headers | `payment.captured` → payments row + dashboard badge |
| POST | `/webhooks/merchant-onboarded` | `{merchant_name, gmv_inr}` | triggers audit; returns `{audit_id}` |
| GET | `/api/audit/{id}/stream` | — | SSE: trial ticker events |

All responses carry CIs where a measured quantity exists. Frontend never computes a headline number.

---

## 11. UX Specification

**P1 Setup.** Headline: *"Your next customer might not be human."* Two source cards (demo store / upload). GMV input. Agent-share slider with live preview of what 5% means.

**P2 Live progress.** SSE ticker of trials (model · persona · condition → choice), progress bar, running cost. Copy: *"640 real agent decisions in progress."*

**P3 Results.** Top strip (always visible):

```
AgentReady  48 → 71            Revenue at Risk ₹41,000/mo @20%       Recoverable ₹18,200/mo
[measured, CI ±4]              [scenario: F=25.6% measured, S=20% you set]  [measured ΔF, CI]
```
*(Corrected from an earlier "@5%" draft — TECHSPEC errata E-2: ₹41,000/mo is arithmetically impossible at 5% of ₹8L GMV since the max possible at F_task=100% is ₹40,000; the figure reconciles at S_agent=20%, F_before=25.6%.)*

Below: (a) choice heat map (products × models, share intensity); (b) position curve with chance line; (c) stability matrix with band coloring; (d) coverage dial; (e) framing displacement chart; (f) product table sortable by visibility (invisible products flagged ⚠).

**P4 Product drilldown.** Legibility checklist with pass/fail per item; visibility CI; suggested fixes; link to diff.

**P5 Remediation review.** Side-by-side original vs. fixed (JSON-LD diff + copy diff). Approve button (human gate).

**P6 Before/after.** Score delta with CIs; per-product visibility deltas; rupee delta; if CIs overlap, the honest-fallback state renders: *"Delta within noise. Persistent gap likely model-side bias — itself a finding (ACES 2025)."*

**P7 Agent checkout.** Live console of the agent's tool calls; payment link; captured badge.

Every chart footer: source metric key + CI. Every stat that cites research shows the citation inline.

---

## 12. Non-Functional Requirements

| NFR | Requirement |
|---|---|
| Performance | Full audit < 15 min (40 SKUs); dashboard p95 reads < 300 ms; webhook → badge < 5 s |
| Cost | Hard cap $30/run; total project LLM spend ≤ $35 |
| Reproducibility | Model versions pinned + logged; seeds recorded; recorded runs referenced by `demo/manifest.json` |
| Privacy | No PII processed; uploaded catalogs auto-purged after 7 days (demo); trials contain only synthetic personas |
| Security | Razorpay secrets server-side only; webhook signature verification; MCP tools expose no credentials |
| Reliability | Circuit breaker on provider failures; partial runs marked `partial` and never silently presented as complete |
| Accessibility | Keyboard-navigable dashboard; color-safe charts (bias indicators never color-only) |

---

## 13. Testing Strategy

| Layer | Tests |
|---|---|
| Unit | Metric functions vs. hand-computed fixtures; schema validation; score bounds/weights; revenue formula bounds |
| Validation suite | V1–V6 planted-bias cases (CI-gated via `make validate`) |
| Integration | API contract tests per endpoint; webhook signature handling; cache behavior (re-run ≈ free) |
| E2E | Playwright: setup → audit → remediate → rerun → checkout on demo store |
| Demo | 3 rehearsals ≤ 4:30; recorded backup; `make demo-check` nightly (30-trial subset must stay within reported CIs) |

---

## 14. Reproducibility Policy (normative)

1. Pin exact model version IDs; log per trial.
2. Record seeds and temperature per trial.
3. Demo references recorded run IDs in `demo/manifest.json`; cached real runs are primary; live re-run is the flourish. If live drifts: presenter says *"variance is within our reported CIs."*
4. `make demo-check` alerts on CI-drift nightly.
5. **Never tune seeds, prompts, or fixtures to inflate a demo delta.** If the delta is weak, fix the remediation levers or present the honest fallback. (This rule is in the PRD deliberately: it is the project's integrity invariant, and violating it would contradict every credibility claim the product makes.)

---

## 15. Demo Specification (4 minutes)

1. **(0:00–0:30)** Hook: "AI agents are becoming the buyers. Merchants have SEO for Google — nothing for agent buyers. AgenticShop: agents succeed at curation only 13–38% of the time."
2. **(0:30–1:30)** Run audit (cached primary) on demo store: heat map; *"One SKU alone captured 74% of agent demand; 5 SKUs are agent-invisible."* *(Corrected from an earlier "3 of 40 SKUs captured 68%" draft — APPFLOW AF-2: HHI_norm 0.54 implies a single ~74%-share modal SKU, so a 3-SKU/68% framing understates it.)*
3. **(1:30–2:30)** Drill into invisible hero **`sku_023` — TrailBuddy Daypack 22L** (starved tier, baseline position 19: price absent from structured data, ~10-word description) + stability matrix: *"GPT and Gemini built different bestsellers from the same catalog."* *(Corrected from an earlier "SKU #17" draft — APPFLOW AF-1: TECHSPEC's canonical schema example `sku_017` is a rich-tier product; the demo's invisible hero must be a starved-tier SKU, which is `sku_023`.)*
4. **(2:30–3:30)** Remediate (diff view, human gate) → re-run → **Score 48 → 71 · Recoverable ₹18,200/mo @20%** with CIs; one line on the slider: *"Failure rates are measured today; when agent traffic scales through AP2-style rails, this is already running."* *(Corrected @5% → @20%, TECHSPEC E-2.)*
5. **(3:30–4:00)** Agent completes Razorpay test-mode checkout. Close: *"We don't just measure readiness — we prove an agent can buy from you."*

Backup: pre-recorded video; failure protocol: cached results always render; live calls are additive only.

---

## 16. Business Model & GTM

- **Freemium:** one free audit/catalog/quarter; branded report export.
- **Monitoring subscription:** scheduled re-audits (model-version watch — ACES-motivated), alerting on score drops, trend dashboards.
- **White-label / API for PSPs:** audit-on-onboarding as a value-add layer (the demonstrated webhook pattern); rupee model powered by the merchant's real GMV/AOV from processor data.
- **Agency tier:** multi-client workspaces, benchmarked comparisons.
- **GTM:** hackathon → Razorpay internship conversation → design-partner merchants (D2C, agencies) → PSP partnerships.
- **Moat:** the *measured* dataset — per-category, per-model choice-behavior baselines compound with every audit run; quarterly published "Agent Legibility Index" (PR + data flywheel).

---

## 17. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Remediation delta within noise (CIs overlap) | Med | Demo climax weakens | Pre-test week 1; strengthen framing/title levers; honest-fallback narrative is designed, not improvised |
| R2 | Provider schema-compliance failures (parse errors) | Med | Trial loss | Retry with feedback; report per-model parse rate (a finding, not a bug); flagship models as backup path |
| R3 | Live API flakiness during demo | Med | Demo stalls | Cached runs primary; live is additive; recorded backup |
| R4 | Cost overrun | Low | Budget | Hard $30 cap; mini-tier bulk; aggressive caching |
| R5 | Judge challenges causality of metadata→revenue | High | Credibility | Labels everywhere; Limitations section; Q&A prep (§20) |
| R6 | Model version deprecation mid-build | Low | Re-pinning churn | models.yaml is the single pin point; manifest records versions |
| R7 | Scope creep (scraping!) | High | Timeline death | NG-1 is written down; PRD is the contract |

---

## 18. Development Plan (summary — full detail in IMPLEMENTATION.md §11)

| Days | Milestone |
|---|---|
| 0 | Skeletons, keys, demo-store seed |
| 1–2 | Demo store + upload ingestion |
| 3–5 | Trial engine (personas, conditions, cache, pins) |
| 6 | Stats layer + validation suite green |
| 7 | Legibility + score |
| 8 | Revenue module + dashboard strip |
| 9–10 | Remediation + before/after (pre-tested) |
| 11–12 | Dashboard + onboarding webhook |
| 13 | Agent checkout + `make demo-check` |
| 14 | Rehearsals ×3, video, submit |

Never cut: trial engine, core metrics, score, before/after loop, revenue strip.

---

## 19. Limitations & Claim Discipline (product-copy normative)

1. **L-1 Correlation ≠ causation.** Legibility↔visibility is diagnostic over N=40, reported with CIs, labeled as such.
2. **L-2 Model-side bias exists** (ACES). Surfaced as a finding; remediation targets merchant-controllable levers only.
3. **L-3 Simulated agents, not production traffic.** API-driven agents with pinned prompts — the tradeoff is reproducibility.
4. **L-4 Score weights are design choices**, configurable, sensitivity-noted.
5. **L-5 Revenue-at-Risk is a scenario model.** F_task and ΔF measured; S_agent user-assumed; labels in UI.
6. **L-6 "Designed to integrate with Razorpay" ≠ "integrates."** The onboarding webhook is a *simulated* demonstration of the production pattern.

Marketing copy, README, and dashboard must not make any claim outside these bounds.

---

## 20. Judge Q&A (prepared)

1. **"Isn't agent bias model-side, per ACES?"** — Partly, yes; that's why stability is a headline finding and why our fixes target only merchant-controllable levers (framing, titles, position, data completeness).
2. **"How is this different from SEO?"** — SEO optimizes ranking for a crawler; we measure *choice behavior* of autonomous buyers — different metrics (HHI, position lift, stability), different fixes, different endpoint (agent checkout, not search rank).
3. **"Sample size?"** — ~640 trials/audit; persona-cluster bootstrap CIs on everything; the validation suite proves metrics recover planted ground truth.
4. **"Where does the revenue number come from?"** — Labeled scenario model: F_task and ΔF measured; traffic share is your slider. No hidden inputs.
5. **"Why should Razorpay care?"** — Agent payments rails (AP2, x402) standardize the *paying* side; illegible merchants lose the channel. This is the readiness layer for Razorpay's merchant base, designed to run on onboarding.
6. **"Business model?"** — Freemium audit → monitoring subscription → white-label for PSPs; compounding measured dataset as moat.
7. **"Can you prove fixes work?"** — Live before/after with CIs; and where we can't, we say so (L-1/L-2).

---

## 21. Post-Hackathon Roadmap

| Item | Description | Research hook |
|---|---|---|
| R-1 Scrape CLI | `agentaudit scan <url>` — same pipeline, live sites | WebMall heterogeneity patterns |
| R-2 Model-version watch | Auto re-audit on model release events; drift alerts | ACES model-instability |
| R-3 AP2 mandate testing | Verify agent-legibility of mandate-style checkout flows end-to-end | AP2 spec |
| R-4 Multi-shop audit | Comparative legibility across competitor catalogs | WebMall tasks |
| R-5 Agent Legibility Index | Quarterly published category benchmarks (data flywheel) | AgenticShop/ACES lineage |

---

## 22. Glossary

**Agent-invisible** · product significantly below fair-share choice. **AgentReady Score** · 5-component 0–100 composite. **Coverage failure (F_task)** · measured null-choice rate. **HHI** · Herfindahl–Hirschman Index of choice shares. **Lift (position)** · top-3 capture over chance. **Mirrored catalog** · remediated copy for re-run. **Modal product** · disproportionately chosen SKU (ACES term). **Null choice** · agent declines all products. **Persona-cluster bootstrap** · CI method resampling personas. **Stability** · mean pairwise cosine of model choice-share vectors.

---

## 23. References

1. Allouah, A., Besbes, O., Figueroa, J.D., Kanoria, Y., Kumar, A. — *What Is Your AI Agent Buying? Evaluation, Biases, Model Dependence, & Emerging Implications for Agentic E-Commerce.* arXiv:2508.02630 (2025).
2. Kim, S., et al. — *AgenticShop: Benchmarking Agentic Product Curation for Personalized Web Shopping.* arXiv:2602.12315 (2026).
3. Peeters, R., Steiner, A., Schwarz, L., et al. — *WebMall: A Multi-Shop Benchmark for Evaluating Web Agents.* arXiv:2508.13024 (2025).
4. Agent Payments Protocol (AP2) — ap2-protocol.org, v0.2 (specification; not peer-reviewed).
5. Roy, K., Sotiya, A., Najish, M., Alam, S., Walia, A. — *EzyBuyy: An Agentic AI-Based Multi-Agent Framework for Conversational Product Discovery and Price Negotiation.* IJFMR v8 i2 (2026). DOI 10.36948/ijfmr.2026.v08i02.76075.
6. Yao, S., et al. — *WebShop: Towards Scalable Real-World Web Interaction with Grounded Language Agents.* NeurIPS 2022. (Context: prior benchmark lineage.)

---

## 24. Open Questions

| # | Question | Owner | Resolution path |
|---|---|---|---|
| Q1 | Will Razorpay ship an official MCP server before Sept 3? | You | Check weekly; integrate if yes |
| Q2 | Do all three providers honor seed parameters uniformly? | Eng | Day-3 spike; if not, seeds recorded anyway, CI widened |
| Q3 | Are 20% equal score weights right? | Eng (post-event) | v0.2 sensitivity analysis; weights stay config-driven |
| Q4 | Minimum catalog size for stable metrics? | Eng (post-event) | Power analysis on simulation; document N floor |

---

*End of PRD v1.0. Changes require a version bump and a commit referencing the FRs affected.*
````

**Save:** copy the block → `PRD.md` in repo root → commit: `git add PRD.md && git commit -m "docs: PRD v1.0"`.

Two notes on what this PRD adds beyond the implementation doc, since a judge may read both: (1) **§3 is your research-defense layer** — every paper has a "what we do NOT take" entry, which is the section that makes you look like a researcher rather than a paper-name-dropper; rehearse those lines specifically. (2) **§8.2 lists all 20 personas verbatim** — that's now a build artifact: each row becomes a JSON file on Day 3, and the "null-plausible" flags (P04, P09, P10, P20) are what guarantee your coverage metric has signal without being engineered.

