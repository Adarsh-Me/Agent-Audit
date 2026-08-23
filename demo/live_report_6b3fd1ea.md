# Live audit report — run 6b3fd1ea (nemotron gap-fill completion)

**Recorded:** 2026‑08‑23 ~15:00 IST · provider OpenRouter · cost $0.00
**Status:** `done` — all 640 trials executed and flushed. **parse_ok 239/640**; every
non-parsed trial is an honestly-counted provider failure.

## Headline numbers (with 95% CI)

| Metric | Value | 95% CI |
|---|---|---|
| AgentReady Score | **67.1** | [55.9, 74.6] |
| HHI_norm | 0.105 | [0.088, 0.253] |
| Top‑3 capture | 22.8% | [13.0%, 35.1%] |
| Position lift | 3.04× (p=0.0001) | — |
| Framing Δ | +2.1 pp | [+1.4, +8.3] |
| F_task | 10.1% | [6.1%, 16.2%] |
| Cross-model stability | 0.58 ("moderate") | [0.24, 0.85] |
| Invisible SKUs | sku_003 · sku_030 · sku_037 · sku_040 | upper CI < 1/N |

## What this run changed vs 6ee157a7

- **Nemotron bulk: 14/200 → 19/200 parse_ok** (failure rate 0.93 → 0.905). The UTC-midnight
  quota reset did open the free pool, but congestion re-closed it after ~5 usable calls —
  every further attempt either hung past its ≤300 s unbreakable wall cap or came back 429,
  all counted as failures. Successes are cached and will replay free on any future refire.
- gpt-oss stayed delisted upstream (HTTP 404 on every call → 200 counted failures);
  nemotron flagship had no cache coverage → 20/20 counted failures.
- Score moved 70.5 → 67.1 and stability 0.75 → 0.58 purely from the added nemotron rows —
  the cross-model signal is honestly sensitive to how much of each block is real data.
- Per-model parse-failure rates: ox-alpha 0.00 · ox-alpha-flagship 0.00 · nemotron-flash
  0.905 · nemotron-flagship 1.00 · gpt-oss 1.00.
- Full-matrix execution under the hardened runner again: zero stalls, zero silent deaths.
