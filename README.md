# AgentAudit — AI-Buy-Readiness Audit

Can AI shopping agents actually see, choose, and buy from your catalog?

AgentAudit runs 640 randomized, controlled shopping trials with real LLM agents against a
merchant catalog, measures choice behavior (concentration, position bias, framing sensitivity,
coverage failure, cross-model stability), and converts findings into an AgentReady Score with
confidence intervals, a rupee-denominated Revenue-at-Risk model with labeled inputs, a
per-product remediation loop verified by re-run, and an end-to-end agent checkout proof on
Razorpay test mode.

> Built for the Razorpay AI Buildathon — Track 01: AI Growth & Agentic Commerce.

- Product/why: [`Docs/PRD.md`](Docs/PRD.md)
- Engineering contract: [`Docs/TECHSPEC.md`](Docs/TECHSPEC.md)
- Data & API shapes: [`Docs/SCHEMA.md`](Docs/SCHEMA.md)
- UX flow & copy: [`Docs/appflow.md`](Docs/appflow.md)
- Build plan & gates: [`Docs/IMPLEMENTATIONPLAN.md`](Docs/IMPLEMENTATIONPLAN.md)
- Engineering log: [`Docs/BUILDLOG.md`](Docs/BUILDLOG.md)

## Quickstart (local dev)

```bash
docker compose up -d          # Postgres 16 (optional — SQLite fallback works out of the box)
cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
python demo-store/generate.py && python -m scripts.seed_demo   # build + load demo store
```

Frontend (`frontend/`, Next.js) and demo-store static site (`:8080`) per `Docs/TECHSPEC.md` §21.

## Status

Pre-alpha scaffold. See `Docs/BUILDLOG.md` for the day-by-day engineering log.
