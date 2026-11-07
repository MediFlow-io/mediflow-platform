import { expect, test } from "@playwright/test";
import { api, signInStaff, token, unique } from "./helpers.js";

test("student patient on lapsed NHIS cover: category shown, warning before check-in, claims page opens", async ({ page }) => {
  const admin = await token("admin", "admin123");
  const name = `NHIS Student ${unique()}`;
  await api("/api/patients", { token: admin, method: "POST", body: {
    fullName: name, sex: "Female", phone: "0", patientType: "student", schoolId: `SEN/22/${unique()}`, unit: "Software Engineering",
    level: "300", paymentCategory: "insurance", insuranceScheme: "tiship", insuranceNumber: "TS-E2E", hmoName: "Example HMO",
    insuranceExpires: "2020-01-31",
  } });

  await signInStaff(page, "admin", "admin123");
  await page.getByRole("button", { name: "Patients", exact: true }).click();
  await page.getByLabel("Search patients").fill(name);
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await expect(page.getByText("NHIS cover expired").first()).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("expired on");

  await page.getByRole("button", { name: "Insurance claims" }).click();
  await expect(page.getByRole("heading", { name: "Insurance claims" })).toBeVisible();
});
