import { expect, test } from "@playwright/test";
import { signInStaff, unique, watchErrors } from "./helpers.js";

test("nurse registers a patient, gets an AI suggestion, checks in and completes the visit", async ({ page }) => {
  const errors = watchErrors(page);
  const name = `E2E Patient ${unique()}`;
  await signInStaff(page, "nurse", "nurse123");
  await expect(page.getByRole("heading", { name: "Today" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Staff", exact: true })).toHaveCount(0); // admin only

  await page.getByRole("button", { name: "Patients", exact: true }).click();
  await page.getByRole("button", { name: "Register patient" }).click();
  await page.getByLabel("Full name *").fill(name);
  await page.getByLabel("Sex *").selectOption("Female");
  await page.getByLabel("Date of birth").fill("2004-05-17");
  await page.getByLabel("Phone *").fill("08000000000");
  await page.getByRole("button", { name: "Register patient" }).last().click();
  await expect(page.getByText(`${name} registered`)).toBeVisible();

  await page.getByRole("button", { name: "Check in" }).click();
  await page.getByLabel("Department *").selectOption({ label: "Outpatient Department" });
  await page.getByLabel("Chief complaint").fill("chest pain since morning");
  await page.getByLabel(/Heart rate/).fill("112");
  await page.getByRole("button", { name: "Suggest ESI" }).click();
  await expect(page.getByText("High-risk complaint")).toBeVisible();
  await expect(page.getByLabel("Triage level (ESI) *")).toHaveValue("2"); // pre-filled, nurse decides
  await page.getByRole("button", { name: "Check in", exact: true }).last().click();
  await expect(page.getByText(`${name} checked in to Outpatient Department (ESI 2)`)).toBeVisible();

  await page.getByRole("button", { name: "Queue", exact: true }).click();
  const row = page.getByRole("row", { name: new RegExp(name) });
  await expect(row.getByText("ESI 2 · Emergent")).toBeVisible();
  await expect(row.getByText("chest pain since morning")).toBeVisible();
  await row.getByRole("button", { name: "Start consultation" }).click();
  await expect(row.getByText("In consultation")).toBeVisible();
  await expect(row.getByText("HR 112")).toBeVisible();
  await row.getByRole("button", { name: "Complete" }).click();
  await expect(page.getByRole("row", { name: new RegExp(name) })).toHaveCount(0);

  await page.reload(); // session survives a reload
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("admin creates a staff member and deactivates them", async ({ page }) => {
  const username = `e2e.doc${unique()}`;
  await signInStaff(page, "admin", "admin123");
  await page.getByRole("button", { name: "Staff", exact: true }).click();
  await page.getByRole("button", { name: "Add staff member" }).click();
  await page.locator("#s_name").fill("E2E Doctor");
  await page.locator("#s_id").fill(username);
  await page.locator("#s_password").fill("Clinic-Pass-2026");
  await page.getByRole("button", { name: "Register staff member" }).click();
  await expect(page.getByText(/account created/i)).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("row", { name: new RegExp(username) }).getByRole("button", { name: "Deactivate" }).click();
  await expect(page.getByText(`${username} deactivated and signed out.`)).toBeVisible();
});
