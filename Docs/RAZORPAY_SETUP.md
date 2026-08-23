# Razorpay test-mode setup — the 10-minute walkthrough

Everything the code needs is already implemented (`backend/app/routers/payments.py`,
`scripts/razorpay_smoke.py`, MCP `create_payment_link`). Only the three keys are
missing. This page closes FINALSPRINT Day 3.

## 1. Keys (2 min)

1. Create / log in at https://dashboard.razorpay.com (test mode is the default for
   new accounts).
2. Settings → **API Keys** → *Generate Test Key*. Copy `key_id` (`rzp_test_…`) and
   `key_secret` (shown once).
3. Put them in `backend/.env`:

   ```
   RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
   RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
   ```

The E505 guard refuses anything not starting `rzp_test_` — a live key can never be
used by the agent checkout, by design.

## 2. Tunnel + webhook (5 min)

The webhook must reach your laptop:

```bash
ngrok http 8000
# copy the https://….ngrok-free.app URL
```

Razorpay dashboard → Settings → **Webhooks** → *Add New Webhook*:

- URL: `https://<your-tunnel>.ngrok-free.app/api/webhooks/razorpay`
- Events: `payment_link.paid`, `payment_link.captured`, `payment_link.failed`
- Copy the **signing secret** into `backend/.env`:

  ```
  RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxx
  ```

## 3. Run the proof (3 min)

Restart uvicorn (it reads `.env` at boot), then:

```bash
cd backend
../.venv/Scripts/python.exe -m scripts.razorpay_smoke <run_id>      # any done run
```

The script picks a product, creates the bounded link, prints the payment URL —
open it and pay with the standard test card:

```
4111 1111 1111 1111   any future date   any CVV   (any name / OTP works)
```

Within ~5 s of payment the webhook flips the payment row to `captured` and the
script prints the F8 badge line. Run it **twice** — the second run proves
idempotency (same link replayed, no duplicate money action).

In the UI: `/checkout/<run_id>` → *Start agent* walks the same flow visually.

## Money-action bounds in force (SAFETY.md)

| Policy | Value | Code |
|---|---|---|
| Per-link spend cap | ₹2,000 (`MAX_AGENT_SPEND_INR`) | E503 |
| Purchasable-SKU whitelist | demo `sku_001`–`sku_040` | E504 |
| Test mode only | key must start `rzp_test_` | E505 |

## If the webhook never arrives

- Tunnel URL changed since you created the webhook (ngrok free URLs rotate) →
  update the webhook URL in the dashboard.
- Watch the ngrok request inspector: a 400 means signature mismatch (wrong
  `RAZORPAY_WEBHOOK_SECRET`); a 200 with no badge means the entity key didn't
  match a known payment link.
