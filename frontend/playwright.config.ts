import { defineConfig } from "@playwright/test";

/**
 * Boots the real stack for route-level smoke:
 *   1. backend  — seeds the demo catalog, then uvicorn on :8000
 *   2. frontend — `next start` on :3000 (expects an existing `npm run build`)
 * Locally servers you already have running are reused; in CI they must be fresh.
 * --no-proxy-server: every target here is localhost; system proxies have been
 * observed to black-hole loopback traffic on this machine.
 */
const BACKEND = "http://127.0.0.1:8000";
const FRONTEND = "http://127.0.0.1:3000";
const REUSE = !process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: FRONTEND,
    launchOptions: { args: ["--no-proxy-server"] },
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: [
    {
      command:
        'cd /d ..\\backend && ..\\.venv\\Scripts\\python.exe -m scripts.seed_demo && ..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000',
      url: `${BACKEND}/healthz`,
      reuseExistingServer: REUSE,
      timeout: 90_000,
    },
    {
      command: "npm run start",
      url: FRONTEND,
      reuseExistingServer: REUSE,
      timeout: 120_000,
    },
  ],
});
