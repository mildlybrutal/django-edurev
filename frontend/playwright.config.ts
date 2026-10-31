import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against a running stack seeded with the synthetic demo:
 *   docker compose up -d && docker compose exec backend python manage.py seed_demo --password "$E2E_PASSWORD"
 * They create their own uniquely named drive each run, so they can be repeated.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
