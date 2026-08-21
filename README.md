# AgentAudit — AI-Buy-Readiness Audit

**Can AI shopping agents actually see, choose, and buy from your catalog?**

AgentAudit runs **640 randomized, controlled shopping trials** with real LLM agents against a
merchant catalog, measures agent choice behavior, converts findings into an **AgentReady Score
with confidence intervals**, a **rupee-denominated Revenue-at-Risk model with labeled inputs**,
a **human-gated remediation loop verified by re-run**, and closes with an end-to-end
**agent checkout proof on Razorpay test mode**.

> Razorpay AI Buildathon — Track 01: AI Growth & Agentic Commerce.

---

## What it measures (and how it stays honest)

| Signal | Meaning | Guardrail |
|---|---|---|
| HHI_norm | demand concentration across agents' choices | persona-cluster bootstrap CI |
| Position bias | do top-listed products win by slot alone? | permutation test p-value |
| Framing sensitivity | does equivalent copy change choices? | per-SKU Δ with CI |
| Coverage failure F_task | share of tasks ending in *no purchase* | Wilson CI |
| Cross-model stability | do GPT/Gemini/Claude agree? | cosine matrix + band |
| Invisible SKUs | listings whose share CI-upper < 1/N | flagged, not vibes |

- **Every headline number carries its CI.** The score CI is propagated through the same
  bootstrap resample — never assumed.
- **Partial runs are never rendered as complete** anywhere in the product.
- **Revenue inputs are labeled**: GMV and s_agent are *your assumptions*; F_task is *measured*.
- **Nothing applies automatically**: fixes require per-item human approval; the re-run proves
  the delta over the same protocol.

## Architecture

```
Next.js :3000  ──►  FastAPI :8000  ──►  trial engine (OpenRouter: 3 bulk + 2 flagship models)
        │                    │                    │  640 trials · seeds deterministic
        │                    ├──►  PostgreSQL 16 (SQLite fallback for local dev)
        │                    ├──►  response cache keyed (prompt_hash, model_version)
        │                    └──►  Razorpay test-mode Payment Links + HMAC webhooks
        └── SSE progress stream            MCP stdio server for external AI agents
```

## Quickstart (local dev)

```bash
# backend
docker compose up -d db            # optional — SQLite fallback works out of the box
cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# demo catalog (40 products, engineered tier structure)
python demo-store/generate.py && python -m scripts.seed_demo

# frontend
cd ../frontend && npm install && npm run dev   # http://localhost:3000
```

### Run your first audit

```bash
curl -X POST localhost:8000/api/audit -H 'Content-Type: application/json' \
     -d '{"catalog_source":"demo"}'
# → {"audit_id": "...", "status": "queued", "trials_total": 640}
```

Then open `localhost:3000/audit/<id>` and watch trials land live.

## Environment

Copy `.env.example` → `.env`:

| Var | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | all LLM providers via OpenRouter (required for live runs) |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | test-mode payment links |
| `RAZORPAY_WEBHOOK_SECRET` | webhook signing secret (dashboard → Settings → Webhooks) |
| `DATABASE_URL` | SQLite default; Postgres in deployed envs |
| `COST_CAP_USD` | per-run spend guard (default $30) → partial state, never silent |

## Repo map

```
backend/app/engine/      trial engine: conditions, prompts, client, runner, cache, parse
backend/app/stats/       metrics M1–M6, persona-cluster bootstrap, legibility scoring
backend/app/revenue/     Revenue-at-Risk model (labeled inputs)
backend/app/remediate/   fix proposals, mirror builder, rerun gate
backend/app/routers/     REST API (uploads, audit, metrics, report, revenue, fixes, delta,
                         payments, webhooks, SSE stream)
backend/tests/validation/ V1–V6 planted-bias suite  → make validate
demo-store/              controlled 40-product world (generator + static site)
mcp-server/server.mjs    stdio MCP server: audit_status / get_report / create_payment_link
Docs/                    PRD · TECHSPEC · SCHEMA · APPFLOW · IMPLEMENTATIONPLAN · BUILDLOG
```

## Engineering gates

```bash
make test         # 73 unit/integration tests
make validate     # V1–V6 planted-bias suite (CI-gated)
make seed-demo    # rebuild demo fixture + load into DB
make demo-check   # verify manifest numbers vs database (G12)
```

## Recorded demo numbers

Headline figures quoted in the demo are from one recorded run against the committed fixture;
provenance lives in [`demo/manifest.json`](demo/manifest.json) (models+versions, seeds, cost,
git sha, prompt-hash sample) and is re-verifiable via `make demo-check`. See
[`Docs/BUILDLOG.md`](Docs/BUILDLOG.md) for the day-by-day engineering log.

## Known limitations (honest ones)

- Demo store is synthetic; uploaded catalogs get template fix proposals with explicit
  `[seller to confirm]` markers — we never fabricate specs for a real merchant.
- Primary metrics pool bulk-tier models; flagship runs are reported but too thin to pool.
- Single-process deployment scope; the SSE bus swaps for Redis pub/sub if multi-worker.
