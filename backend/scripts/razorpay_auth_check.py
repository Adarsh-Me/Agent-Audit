"""Read-only Razorpay auth check: GET /v1/payments?count=1 with basic auth.
Prints status only — never prints credentials."""
import asyncio
import base64
import httpx

from app.config import get_settings


async def main() -> None:
    s = get_settings()
    if not s.razorpay_key_id or not s.razorpay_key_secret:
        print("RESULT: missing keys in settings")
        return
    auth = base64.b64encode(
        f"{s.razorpay_key_id}:{s.razorpay_key_secret}".encode()
    ).decode()
    async with httpx.AsyncClient(timeout=30.0) as cx:
        r = await cx.get(
            "https://api.razorpay.com/v1/payments",
            params={"count": 1},
            headers={"Authorization": f"Basic {auth}"},
        )
    print("HTTP", r.status_code)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code == 200:
        items = body.get("items", [])
        mode = "test" if str(s.razorpay_key_id).startswith("rzp_test_") else "live"
        print(f"RESULT: AUTH OK ({mode} mode), existing payments visible: {len(items)}")
    else:
        desc = body.get("error", {}).get("description", r.text[:200])
        print("RESULT: FAILED -", desc)


asyncio.run(main())
