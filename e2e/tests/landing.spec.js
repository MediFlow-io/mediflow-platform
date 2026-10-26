import { expect, test } from "@playwright/test";
import { STUDENT, WEB } from "./helpers.js";

test("landing page explains the app and leads to the staff and student portals", async ({ page }) => {
  await page.goto(WEB);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Shorter waits");
  await expect(page.getByRole("tab", { name: /Triage/ })).toBeVisible();

  await page.getByRole("tab", { name: /Queue/ }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Step 4 of 6");

  // Students register and sign in on the student portal, never on this site.
  await expect(page.getByRole("link", { name: "Create a student account" })).toHaveAttribute("href", `${STUDENT}/register`);
  await expect(page.getByRole("link", { name: "I'm a student" })).toHaveAttribute("href", STUDENT);

  await page.getByRole("navigation").getByRole("link", { name: "Staff sign-in" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Staff sign-in" })).toBeVisible();
  await expect(page.getByLabel("Staff ID")).toBeVisible();
  await expect(page.getByRole("link", { name: "Go to the student portal →" })).toHaveAttribute("href", STUDENT);

  await page.getByRole("link", { name: "← MediFlow home" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Shorter waits");
});

test("the wake-up routes reach every backend", async ({ request }) => {
  for (const path of ["/api/health", "/wake/gateway", "/wake/flow", "/wake/notify", "/wake-urls"]) {
    expect((await request.get(WEB + path)).status(), path).toBe(200);
  }
});
