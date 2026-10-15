import { expect, test } from "@playwright/test";
import { api, department, linkedStudent, signInStaff, signInStudent, token, unique } from "./helpers.js";

test("the queue updates live when someone checks a patient in elsewhere", async ({ page }) => {
  await signInStaff(page, "nurse", "nurse123");
  await page.getByRole("button", { name: "Queue", exact: true }).click();
  await expect(page.getByText("● Live")).toBeVisible();

  const admin = await token("admin", "admin123");
  const opd = await department();
  const name = `Live ${unique()}`;
  const patient = await api("/api/patients", { token: admin, method: "POST", body: { fullName: name, sex: "Male", phone: "0" } });
  const visit = await api("/api/visits", { token: admin, method: "POST", body: { patient: patient.id, department: opd.id, esi: 3 } });
  // Polling is every 60 s while live, so seeing it within 5 s proves the event stream works.
  await expect(page.getByRole("row", { name: new RegExp(name) })).toBeVisible({ timeout: 5_000 });
  await api(`/api/visits/${visit.id}/cancel`, { token: admin, method: "POST" });
  await expect(page.getByRole("row", { name: new RegExp(name) })).toHaveCount(0, { timeout: 5_000 });
});

// Needs the clinic open now: CI starts the stack with CLINIC_HOURS=00:00-23:59 and CLINIC_DAYS=Sun-Sat.
test("student requests, nurse confirms and checks them in on the day", async ({ browser }) => {
  const now = new Date();
  const slot = new Date(now.getTime() + 45 * 60_000);
  slot.setMinutes(Math.ceil(slot.getMinutes() / 15) * 15, 0, 0);
  const later = new Date(slot.getTime() + 30 * 60_000);
  test.skip(later.toDateString() !== now.toDateString(), "too close to midnight for a same-day appointment");
  const pad = (n) => String(n).padStart(2, "0");
  const today = now.toLocaleDateString("en-CA");
  const hhmm = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;

  const student = await linkedStudent();
  const sPage = await (await browser.newContext()).newPage();
  await signInStudent(sPage, student.matric, student.password);
  await sPage.getByRole("button", { name: /Appointments/ }).click();
  await sPage.getByRole("button", { name: "Request a slot" }).click();
  await sPage.getByLabel("Department").selectOption({ label: "Outpatient Department" });
  await sPage.getByLabel("Date").fill(today);
  await sPage.getByLabel("Time").fill(hhmm(slot));
  await sPage.getByLabel("Reason").fill("Follow-up");
  await sPage.getByRole("button", { name: "Send request" }).click();
  await expect(sPage.getByText("Waiting for the clinic")).toBeVisible();

  const nPage = await (await browser.newContext()).newPage();
  await signInStaff(nPage, "nurse", "nurse123");
  await nPage.getByRole("button", { name: "Appointments", exact: true }).click();
  await nPage.getByRole("row", { name: new RegExp(student.name) }).getByRole("button", { name: "Confirm" }).click();
  await nPage.getByLabel("Time").fill(hhmm(later));
  await nPage.getByLabel(/Note to the patient/).fill("Bring your health card");
  await nPage.getByRole("button", { name: "Save" }).click();
  await expect(nPage.getByText(new RegExp(`confirmed for ${today} ${hhmm(later)}`))).toBeVisible();

  await sPage.reload();
  await sPage.getByRole("button", { name: /Appointments/ }).click();
  await expect(sPage.getByText("Clinic: Bring your health card")).toBeVisible();
  await expect(sPage.getByText("Confirmed", { exact: true })).toBeVisible();

  await nPage.getByRole("tab", { name: "Day view" }).click();
  await nPage.getByRole("row", { name: new RegExp(student.name) }).getByRole("button", { name: "Check in" }).click();
  await nPage.getByLabel("Triage level (ESI)").selectOption("4");
  await nPage.getByRole("button", { name: "Save" }).click();
  await expect(nPage.getByText(`${student.name} checked in. They're now in the queue.`)).toBeVisible();

  await sPage.getByRole("button", { name: /Today/ }).click();
  await sPage.reload();
  await expect(sPage.getByRole("heading", { name: "You're in the queue" })).toBeVisible();
});
