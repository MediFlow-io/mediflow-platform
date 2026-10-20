import { expect, test } from "@playwright/test";
import { api, department, signInStaff, token, unique } from "./helpers.js";

test("nurse escalates a waiting patient with a reason; the queue shows estimates and targets", async ({ page }) => {
  const admin = await token("admin", "admin123");
  const opd = await department();
  const name = `Triage ${unique()}`;
  const patient = await api("/api/patients", { token: admin, method: "POST", body: { fullName: name, sex: "Female", phone: "0" } });
  const visit = await api("/api/visits", { token: admin, method: "POST", body: { patient: patient.id, department: opd.id, esi: 4 } });

  await signInStaff(page, "nurse", "nurse123");
  await page.getByRole("button", { name: "Queue", exact: true }).click();
  await expect(page.getByText("Est. wait", { exact: true })).toBeVisible();
  const row = page.getByRole("row", { name: new RegExp(name) });
  await expect(row.getByText("ESI 4 · Less urgent")).toBeVisible();
  await expect(row.getByText(/^(Next|~\d+ min)$/)).toBeVisible();

  await row.getByRole("button", { name: "Change ESI" }).click();
  const form = page.getByRole("form", { name: `Change triage for ${name}` });
  await form.getByLabel("New level").selectOption("2");
  await form.getByLabel("Reason").fill("SpO2 dropped to 89%");
  await form.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(`${name} is now ESI 2.`)).toBeVisible();
  await expect(page.getByRole("row", { name: new RegExp(name) }).getByText("ESI 2 · Emergent")).toBeVisible();

  const history = await api(`/api/visits/${visit.id}/triage`, { token: admin });
  expect(history.map((c) => [c.from_esi, c.to_esi, c.direction, c.reason])).toEqual([[4, 2, "escalated", "SpO2 dropped to 89%"]]);
  const audit = await api("/api/audit-logs?action=visit.triage_changed", { token: admin });
  expect(JSON.stringify(audit)).not.toContain("SpO2"); // the clinical reason stays out of the audit log

  const dashboard = await api("/api/dashboard", { token: admin });
  expect(dashboard.departmentLoad.some((d) => d.name === "Outpatient Department" && d.waiting >= 1)).toBe(true);
  await api(`/api/visits/${visit.id}/cancel`, { token: admin, method: "POST" });
});
