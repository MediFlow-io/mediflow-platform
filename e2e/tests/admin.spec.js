import { expect, test } from "@playwright/test";
import { ADMIN, unique } from "./helpers.js";

async function signIn(page, username, password) {
  await page.goto(`${ADMIN}/login`);
  await page.getByLabel("Staff ID").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("admin console refuses non-admins", async ({ page }) => {
  await signIn(page, "nurse", "nurse123");
  await expect(page.getByText("The admin console is for administrators only.")).toBeVisible();
});

test("admin uses overview, audit log, reports and departments", async ({ page }) => {
  await signIn(page, "admin", "admin123");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("Recent activity")).toBeVisible();

  await page.getByRole("link", { name: "Audit log", exact: true }).click();
  await page.getByLabel("Action starts with").fill("auth.login");
  await page.getByRole("button", { name: "Filter" }).click();
  const actions = await page.locator("td code").allInnerTexts();
  expect(actions.length).toBeGreaterThan(0);
  expect(actions.every((a) => a.startsWith("auth.login"))).toBe(true);

  await page.getByRole("link", { name: "Flow reports", exact: true }).click();
  await expect(page.getByText("By department")).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Download CSV" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^mediflow-flow-\d{4}-\d{2}-\d{2}-to-\d{4}-\d{2}-\d{2}\.csv$/);

  const code = `e2e${unique()}`.slice(0, 20);
  await page.getByRole("link", { name: "Departments", exact: true }).click();
  await page.getByLabel("Name").fill(`E2E Clinic ${code}`);
  await page.getByLabel("Code").fill(code);
  await page.getByRole("button", { name: "Add department" }).click();
  await expect(page.getByText(`Department “E2E Clinic ${code}” created.`)).toBeVisible();
  await page.getByRole("row", { name: new RegExp(code) }).getByRole("button", { name: "Close" }).click();
  await expect(page.getByText(`“E2E Clinic ${code}” closed: new check-ins are blocked.`)).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("You have signed out.")).toBeVisible();
});

test("flow report shows targets, bottlenecks and workload, and downloads as PDF", async ({ page }) => {
  await signIn(page, "admin", "admin123");
  await page.getByRole("link", { name: "Flow reports", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Seen within ESI target" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Where the time goes" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Clinician workload" })).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Download PDF" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^mediflow-flow-\d{4}-\d{2}-\d{2}-to-\d{4}-\d{2}-\d{2}\.pdf$/);
  const path = await download.path();
  const { readFileSync } = await import("node:fs");
  expect(readFileSync(path).subarray(0, 4).toString()).toBe("%PDF");
});
