# SAFETY.md — Agent money-action bounds

How AgentAudit keeps autonomous shopping-agent money actions **explainable,
bounded and gated**. Everything below describes implemented code paths
(`backend/app/routers/payments.py`, `backend/app/config.py`,
`backend/app/constants.py`).

## Money-action bounds

The agent can only move money through `POST /api/payments/link`, which enforces
three server-side policies before any Razorpay call. Each rejection returns a
distinct error code plus `details.policy`, so an auditor can always tell which
rule fired:

| Policy | Default | Override | Code | `details.policy` |
|---|---|---|---|---|
| Per-link spend cap | ₹2,000 (`AGENT_SPEND_CAP_INR`) | `MAX_AGENT_SPEND_INR` env | E503 (403) | `spend_cap` |
| Purchasable-SKU whitelist | demo catalog `sku_001`–`sku_040` (`AGENT_DEFAULT_ALLOWED_SKUS`) | `AGENT_ALLOWED_SKUS` csv env | E504 (403) | `sku_whitelist` |
| Test mode only | key id must start `rzp_test_` | none — deliberate | E505 (403) | `test_mode_only` |

Cap rationale: the demo catalog's median price is ≈₹1,199 and its flagship
anchors are ₹999, so ₹2,000 covers every realistic demo checkout while blocking
high-ticket SKUs (₹2,499+) from autonomous purchase.

Enforcement is against the **DB-stored** product price: the agent sends only
`run_id` + `sku` and cannot influence the charged amount.

## Human gate

Catalog *changes* proposed for merchants go through the remediation flow
(`backend/app/remediate/fixes.py`): fixes are proposed → a human approves or
rejects each row → mirroring into the fixed catalog is refused with E401/409
until **zero rows remain pending**. Nothing applies automatically. Payment links
are bounded by the policies above rather than interactive approval; they are
test-mode payment links (no real funds) by construction.

## Idempotency, webhooks, dedupe

Already implemented in `backend/app/routers/payments.py` — see module docstring:
idempotency key `agentaudit:{run_id}:{sku}` (unique DB constraint + Razorpay
`X-Razorpay-Idempotency-Key` header), HMAC-SHA256 webhook signature verification
(`verify_webhook_signature`), and `webhook_events.entity_key` dedupe of repeat
deliveries. Not re-explained here.

## Secrets stay server-side

Per PRD §8.8, `RAZORPAY_KEY_SECRET` / webhook secret live only in backend env
(`backend/.env`, gitignored). The React frontend and the MCP proxy
(`mcp-server/server.mjs`) talk to the backend API over HTTP and never touch
key material.

## Known limitations (MVP)

- The whitelist is static configuration (constants/env), not a merchant-managed
  runtime list; changing it requires a redeploy or env restart.
- The cap bounds each payment link, not cumulative spend per run/session.
- Idempotent replays of already-created links bypass whitelist/cap checks by
  design (a replay moves no new money); the test-mode guard still applies to
  every Razorpay touch, including replays.
