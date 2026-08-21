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
