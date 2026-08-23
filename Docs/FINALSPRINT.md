# FINALSPRINT.md — AgentAudit: Build → Proof → Submit

*Reconciled 2026-08-23 against actual repo state. The original plan assumed a code-complete-but-unproven baseline; the night of Aug 22–23 closed several blocking items early (money-policy layer, design tokens, trial-matrix table, provenance truthing, two completed live runs). Checkboxes reflect reality as of this commit — do not redo what is checked.*

**Track 01 bar (verbatim):** *"every money action explainable, bounded and gated. Show the audit trail and one failure handled gracefully."*

---

## 0. Setup gate

- [x] `OPENROUTER_API_KEY` provisioned (`backend/.env`, free tier, usage 0/0/0 verified via `/api/v1/auth/key`)
- [ ] **Razorpay test-mode `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`** ← still missing; blocks Day 3 entirely
- [ ] Webhook created in dashboard + `RAZORPAY_WEBHOOK_SECRET` into `.env` (needs ngrok/tunnel URL at setup time)
- [x] `.env` filled where keys exist; `COST_CAP_USD=30` ceiling confirmed
- [x] Green baseline re-verified today: **90/90 tests pass, ruff clean** (suite grew past the plan's 83 — policy tests added)

## Tier 1 — Prove the core claim

### Day 1 — Live trial engine *(substantially done)*
- [x] Live audit fired via real API: run `8db28ce8` (Aug 22) and `6ee157a7` (Aug 23) — **two consecutive completed 640-trial live runs**, trials populate with real SKUs, circuit breaker + wall-clock caps engaged under saturation, failures surfaced as per-model `parse_failure_rate` (nothing silent).
- ⚠️ **Gate met on completion, not on health:** both runs degraded by shared free-pool saturation (parse_ok 234/640 ≈ 37%; `gpt-oss` fully rate-limited). A *clean*-health pair still requires either paid-tier models or off-peak free-window luck.

### Day 2 — Remediation → rerun → manifest *(open)*
- [ ] Approve mirror via human gate → full 640-trial live rerun → delta endpoint on real data.
- [ ] Honest read of whether the score moves (non-overlapping CIs), else use the built-in `honest_fallback` narrative verbatim.
- [ ] Regenerate `demo/manifest.json` from the live pair — kill `mock-deterministic`. *(Deferred until the clean-run decision resolves; regenerating from a degraded pair wastes the artifact.)*

### Day 3 — Live Razorpay checkout ×2 *(blocked on keys only)*
- [ ] Tunnel up → dashboard webhook → MCP flow `list_products`→`get_product`→`create_payment_link` → manual test-mode payment (card `4111 1111 1111 1111`) → HMAC webhook → captured → badge <5s.
- [ ] Run twice.
- Payer answer, rehearsed out loud if asked: *"I pay it myself, manually, in test mode — the agent creates the bounded link; autonomy is in detection→fix→purchase-intent, not in unbounded spending."*

### Day 3.5 — Buffer *(partly consumed by Aug-22/23 work)*
- Remaining buffer should go to a third repetition of whichever flow is least-rehearsed.

## Tier 2 — "Bounded" gap *(done ahead of schedule)*
- [x] `max_agent_spend` cap (₹2,000, E503) + purchasable-SKU whitelist (E504) + test-mode-only guard firing pre-network (E505) — **enforced in code against DB-stored prices**, 5 policy tests. See `SAFETY.md`.
- [x] `SAFETY.md` states all three bounds explicitly (panel can find them in under a minute).
- [ ] Script the failure-handling moment into the demo. **Real footage already exists:** during run `6ee157a7`, ~406 fresh attempts hit saturated pools; breaker/backoff absorbed them; UI surfaces per-model failure rates honestly. Demo beat: fire the audit live, point at the models panel while a rate-limit lands, narrate: *"watch the breaker hold, watch nothing hide."*

## Tier 3 — Copy (zero-risk; drafted here, fold into appflow before recording)

- **Opener (15):** *"Your catalog is already losing AI-routed sales. In our controlled trials, agents couldn't even see 3 of 40 products — not because they're bad products, but because the listings are illegible to machines."* (Own measured numbers first; ChatGPT/Gemini screenshot optional garnish.)
- **Demo reorder (16):** lead with the before/after strip — score X→Y, ₹ recovered with CI — then "how we know": 640 RCTs, CIs, planted-bias validation. *Numbers finalize after Day 2.*
- **Human Gate, named aloud (17):** *"AI proposes catalog fixes. A person approves. We never touch a live listing without consent."*
- **One-liner (18):** *"AI shoppers can't find your products even when they're perfect. We find the leak, fix the catalog, prove the recovery in rupees — and close the loop with a live, capped Razorpay purchase."*

## Tier 4 — Polish status
- [x] DESIGN token swap (commit `bd5cf8f`: `#0A0A0A`, single `#4F8CFF`, Geist/Geist Mono self-hosted).
- [x] Trial-matrix table — `Docs/SUMMARY.md` §4 Step 2, derived from `constants.py`/`conditions.py` (C1×3 seeds closes the 180+180+240+40 arithmetic).
- [ ] Prompt-injection sanitization for uploads: write-up + minimal stripping of instruction-like listing content. Cheap; do only if Days 1–3 are closed.

## Cut list
Unchanged from original: cut Tier 4 remainder first, then Tier 3 individually (but they're nearly free — do them), never cut Tier 1/Tier 2.

## Submission-day checklist
- [ ] `demo/manifest.json` regenerated from a real live pair (or degraded-with-disclosure explicitly chosen and documented)
- [x] Money bounds enforced in code + documented
- [x] README leads with zero-key quickstart; headline numbers carry provenance stamps (SUMMARY §7)
- [ ] Repo pushed public, not just local
- [ ] Pitch video recorded, ≥3 rehearsals, real (non-cached) flow shown at least once; backup recording exists
- [ ] Failure-handling moment shown (live or backup)
- [ ] Every metric explainable unscripted (HHI, position lift, framing Δ, F_task)
- [x] Honest payer answer prepared
