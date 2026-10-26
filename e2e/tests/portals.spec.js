import { expect, test } from "@playwright/test";
import { STUDENT, WEB, unique } from "./helpers.js";

test("a student registers on the student portal and lands on their dashboard", async ({ page }) => {
  const matric = `E2E/R${unique()}`;
  await page.goto(STUDENT);
  await page.getByRole("link", { name: "Create a student account" }).click();
  await expect(page).toHaveURL(/\/register$/);
  await page.getByLabel("Full name").fill("Portal Student");
  await page.getByLabel("Matric number").fill(matric);
  await page.getByLabel("Email").fill(`portal-${unique()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("Student-Pass-2026");
  await page.getByLabel("Confirm password").fill("Student-Pass-2026");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("isn't linked to a health record yet").first()).toBeVisible();

  // The same account is refused on the staff portal.
  await page.goto(`${WEB}/login`);
  await page.getByLabel("Staff ID").fill(matric);
  await page.getByLabel("Password").fill("Student-Pass-2026");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("This is the staff sign-in. Students sign in on the student portal.")).toBeVisible();
});

test("staff are refused on the student portal and pointed to the staff portal", async ({ page }) => {
  await page.goto(STUDENT);
  await page.getByLabel("Matric number").fill("nurse");
  await page.getByLabel("Password").fill("nurse123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("This is the student portal. Staff sign in on the staff portal.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Use the staff portal" })).toHaveAttribute("href", `${WEB}/login`);
});
