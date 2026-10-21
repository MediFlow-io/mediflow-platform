import { expect, test } from "@playwright/test";
import { WEB } from "./helpers.js";

test("landing page explains the app and leads to sign-in and registration", async ({ page }) => {
  await page.goto(WEB);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Shorter waits");
  await expect(page.getByRole("tab", { name: /Triage/ })).toBeVisible();

  await page.getByRole("tab", { name: /Queue/ }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Step 4 of 6");

  await page.getByRole("link", { name: "Student? Create an account" }).click();
  await expect(page.getByRole("tab", { name: "Student registration" })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("link", { name: "← MediFlow home" }).click();
  await page.getByRole("navigation").getByRole("link", { name: "Sign in" }).click();
  await expect(page.getByLabel("Matric No. or Staff ID")).toBeVisible();
});

test("the wake-up routes reach every backend", async ({ request }) => {
  for (const path of ["/api/health", "/wake/gateway", "/wake/flow", "/wake/notify", "/wake-urls"]) {
    expect((await request.get(WEB + path)).status(), path).toBe(200);
  }
});
