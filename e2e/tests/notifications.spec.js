import { expect, test } from "@playwright/test";
import { api, department, linkedStudent, signInStaff, signInStudent, token, unique } from "./helpers.js";

// Notifications are written by the Flask service from patient-flow events, a moment after each change.
async function waitForNotification(accessToken, title) {
  await expect.poll(async () => (await api("/api/notifications", { token: accessToken })).results.map((n) => n.title),
    { timeout: 10_000 }).toContain(title);
}

test("student is told they've been called, and can read it from the bell", async ({ page }) => {
  const student = await linkedStudent();
  const opd = await department();
  const admin = await token("admin", "admin123");
  const visit = await api("/api/visits", { token: admin, method: "POST", body: { patient: student.patient.id, department: opd.id, esi: 4 } });
  await api(`/api/visits/${visit.id}/call`, { token: await token("nurse", "nurse123"), method: "POST" });
  const studentToken = await token(student.matric, student.password);
  await waitForNotification(studentToken, "You've been called");

  await signInStudent(page, student.matric, student.password);
  const bell = page.getByRole("button", { name: /Notifications \(\d+ unread\)/ });
  await expect(bell).not.toHaveAccessibleName("Notifications (0 unread)");
  await bell.click();
  await expect(page.getByRole("button", { name: /You.ve been called.*Please go to Outpatient Department now/ })).toBeVisible();
  await page.getByRole("button", { name: "See all notifications" }).click();
  const list = page.getByRole("list", { name: "Notifications" });
  await expect(list.getByText("You're checked in")).toBeVisible();
  await list.getByRole("button", { name: /You've been called/ }).click(); // opens Today, where the call is shown
  await expect(page.getByRole("heading", { name: "You've been called" })).toBeVisible();
  await expect.poll(async () => (await api("/api/notifications?unread=1", { token: studentToken })).results.map((n) => n.title))
    .not.toContain("You've been called");

  await page.getByRole("button", { name: "Notifications", exact: true }).click();
  await page.getByRole("button", { name: "Mark all read" }).click();
  await expect(page.getByRole("button", { name: "Notifications (0 unread)" })).toBeVisible();
  await api(`/api/visits/${visit.id}/cancel`, { token: admin, method: "POST" });
});

test("front desk hears about appointment requests and the patient hears back", async ({ page }) => {
  const student = await linkedStudent();
  const opd = await department();
  const studentToken = await token(student.matric, student.password);
  const tomorrow = new Date(Date.now() + 86_400_000).toLocaleDateString("en-CA", { timeZone: "Africa/Lagos" });
  const reason = `Check-up ${unique()}`;
  const appt = await api("/api/appointments", { token: studentToken, method: "POST",
    body: { department: opd.id, date: tomorrow, time: "10:00", reason } });

  await signInStaff(page, "nurse", "nurse123");
  await expect(page.getByRole("button", { name: /^Notifications/ })).toBeVisible();
  await expect.poll(async () => {
    await page.getByRole("button", { name: /^Notifications/ }).click();
    return page.getByText(`${student.name} asked for Outpatient Department`).count();
  }, { timeout: 15_000 }).toBeGreaterThan(0);
  await expect(page.getByText(reason)).toHaveCount(0); // the patient's own words stay on the appointment
  await page.getByText(`${student.name} asked for Outpatient Department`).click();
  await expect(page.getByRole("heading", { name: "Appointments" })).toBeVisible();

  await api(`/api/appointments/${appt.id}/confirm`, { token: await token("nurse", "nurse123"), method: "POST",
    body: { note: "Bring your health card" } });
  await waitForNotification(studentToken, "Appointment confirmed");
  const [confirmed] = (await api("/api/notifications", { token: studentToken })).results;
  expect(confirmed.body).toMatch(/^Outpatient Department, \w{3} \d{2} \w{3}, 10:00\. Note from the clinic: Bring your health card$/);
  await api(`/api/appointments/${appt.id}/cancel`, { token: studentToken, method: "POST" });
});
