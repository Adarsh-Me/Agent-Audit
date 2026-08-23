# Live audit report — run 6ee157a7 (first complete-matrix live recording)

**Recorded:** 2026‑08‑23 02:21 IST · provider OpenRouter · cost $0.00
**Status:** `done` — all 640 trials executed and flushed. **parse_ok 234/640** — every
non-parsed trial is an honestly-counted provider failure (see breakdown), never dropped.

## Headline numbers (with 95% CI)

| Metric | Value | 95% CI |
|---|---|---|
| AgentReady Score | **70.5** | [57.9, 76.6] |
| HHI_norm | 0.110 | [0.088, 0.262] |
| Top‑3 capture | 22.8% | [13.0%, 35.1%] |
| Position lift | 3.04× (p=0.0001) | — |
| Framing Δ | +2.1 pp | [+1.4, +8.3] |
| F_task | 9.0% | [5.2%, 15.0%] |
| Cross-model stability | 0.75 ("moderate") | [0.32, 0.90] |
| Invisible SKUs | sku_003 · sku_030 · sku_037 | upper CI < 1/N |

## Provenance & honesty notes

- **Measured:** ox‑alpha bulk 200/200 (100%) + ox‑alpha flagship 20/20 (100%) — recorded
  live Aug 21–22 and replayed here from response_cache at zero marginal cost;
  nemotron bulk 14/200 (7%) cached successes.
- **Provider-failed (counted, not dropped):** nemotron bulk 186/200 + nemotron flagship
  20/20 (`nvidia/nemotron-3.5-lightning:free` hit its daily free-pool cap mid-run) and
  gpt‑oss 200/200 (`openai/gpt-oss-20b:free` delisted upstream → HTTP 404).
- Per-model parse-failure rates: ox-alpha 0.00 · ox-alpha-flagship 0.00 · nemotron-flash
  0.93 · nemotron-flagship 1.00 · gpt-oss 1.00.
- Stats therefore lean on the fully-measured ox-alpha block; cross-model rows carry wide
  CIs until the nemotron gap-fill completes (run `6b3fd1ea`, fired post-quota-reset).
- Engine note: this is the first run completed end-to-end under the hardened runner
  (unbreakable 300 s trial wall cap + engine-error guard, commit e7e81f9) — zero stalls,
  zero silent deaths, 111 s wall-clock for the full matrix incl. cache replays.
