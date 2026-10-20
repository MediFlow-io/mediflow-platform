import { expect, test } from "@playwright/test";
import { ADMIN, signInStaff } from "./helpers.js";

test("check-in shows the NEWS2 score next to the ESI suggestion", async ({ page }) => {
  await signInStaff(page, "nurse", "nurse123");
  await page.getByRole("button", { name: "Patients", exact: true }).click();
  await page.getByRole("button", { name: "Register patient" }).click();
  await page.getByLabel("Full name *").fill(`NEWS2 ${Date.now() % 100000}`);
  await page.getByLabel("Sex *").selectOption("Male");
  await page.getByLabel("Phone *").fill("0");
  await page.getByRole("button", { name: "Register patient" }).last().click();
  await page.getByRole("button", { name: "Check in" }).click();
  await page.getByLabel(/Heart rate/).fill("135");
  await page.getByLabel(/Resp. rate/).fill("26");
  await page.getByRole("button", { name: "Suggest ESI" }).click();
  const news2 = page.getByRole("status", { name: "NEWS2 early warning score" });
  await expect(news2.getByText(/^NEWS2 6\+/)).toBeVisible(); // 3 (HR) + 3 (RR), other vitals missing
  await expect(news2.getByText(/missing spo2/)).toBeVisible();
});

test("admin sees AI insights with expected waits", async ({ page }) => {
  await page.goto(`${ADMIN}/login`);
  await page.getByLabel("Staff ID").fill("admin");
  await page.getByLabel("Password").fill("admin123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("link", { name: "AI insights" }).click();
  await expect(page.getByRole("heading", { name: "Expected wait for a new arrival" })).toBeVisible();
  await expect(page.getByRole("row", { name: /Outpatient Department/ }).getByText(/\d+–\d+ min/)).toBeVisible();
});
