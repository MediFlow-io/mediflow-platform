import { defineConfig } from "@playwright/test";

// Browser tests across the running stack. Defaults match `npm run dev` (see docs/PROJECT-STATUS.md);
// CI points them at the Docker stack instead (WEB_URL=http://localhost:8080 and so on).
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1, // the tests share one demo database
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    timezoneId: "Africa/Lagos", // the hospital's time zone, so "today" matches the server
    viewport: { width: 1360, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
