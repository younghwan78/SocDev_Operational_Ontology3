import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  globalSetup: "./tests/global-setup.ts",
  reporter: [["list"], ["html", { outputFolder: "../output/playwright/report", open: "never" }]],
  outputDir: "../output/playwright/test-results",
  use: {
    baseURL: "http://127.0.0.1:15173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: "uv run uvicorn soc_ot.api.main:app --app-dir backend/src --host 127.0.0.1 --port 18080",
      cwd: "..",
      url: "http://127.0.0.1:18080/health/ready",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 15173",
      cwd: ".",
      url: "http://127.0.0.1:15173/decisions",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
