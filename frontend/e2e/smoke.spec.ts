import { expect, test } from "@playwright/test";

/**
 * Route-level smoke over the real production build against the real backend.
 * Strictly read-only: uploads validate rows only, no audit/payment is ever started.
 */
const UNKNOWN = "e2e-no-such-run";

test.describe("AgentAudit e2e smoke — all 7 routes", () => {
  test("F1+F2 home renders and validates an uploaded catalog inline", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /Can AI shopping agents actually buy/ }),
    ).toBeVisible();

    // 5 valid rows clears the >=5-products gate; per-row validation only — no run starts
    // (skus must be lowercase per SCHEMA §1 — the E103 gate enforces it)
    const rows = Array.from(
      { length: 5 },
      (_, i) => `sku_${i},Test Widget ${i},A sturdy widget for testing,${499 + i},,,`,
    );
    const csv = ["id,title,description,price_inr,image_url,page_url", ...rows].join("\n");
    await page.locator('input[type="file"]').setInputFiles({
      name: "catalog.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv, "utf-8"),
    });
    await expect(page.getByText("5 of 5 rows valid")).toBeVisible({ timeout: 15_000 });
  });

  test("F3 progress route surfaces run-not-found", async ({ page }) => {
    await page.goto(`/audit/${UNKNOWN}`);
    await expect(page.locator(".errorbox")).toBeVisible();
    await expect(page.locator(".errorbox .code")).toHaveText("E601");
  });

  test("F4 results route surfaces report-not-found", async ({ page }) => {
    await page.goto(`/audit/${UNKNOWN}/results`);
    await expect(page.locator(".errorbox")).toBeVisible();
  });

  test("F5 revenue route surfaces revenue-not-found", async ({ page }) => {
    await page.goto(`/audit/${UNKNOWN}/revenue`);
    await expect(page.locator(".errorbox")).toBeVisible();
  });

  test("F6 fixes route shows empty remediation state for an unaudited run", async ({ page }) => {
    await page.goto(`/audit/${UNKNOWN}/fixes`);
    await expect(page.locator(".errorbox, :text('Remediation plan')").first()).toBeVisible();
  });

  test("F7 delta route surfaces rerun-not-found", async ({ page }) => {
    await page.goto(`/delta/${UNKNOWN}`);
    await expect(page.locator(".errorbox")).toBeVisible();
  });

  test("F8 checkout route renders the agent console shell", async ({ page }) => {
    await page.goto(`/checkout/${UNKNOWN}`);
    await expect(page.getByRole("heading", { name: "Agent checkout proof" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Start agent/ })).toBeVisible();
    await expect(page.locator(".console")).toContainText("idle");
  });
});
