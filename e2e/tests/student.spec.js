import { expect, test } from "@playwright/test";
import { api, department, linkedStudent, signInStudent, token, unique, watchErrors } from "./helpers.js";

test("unlinked student gets clear instructions", async ({ page }) => {
  const matric = `E2E/U${unique()}`;
  await api("/api/auth/register/student", { method: "POST", body: { unique_id: matric, password: "Student-Pass-2026", name: "Unlinked" } });
  await signInStudent(page, matric, "Student-Pass-2026");
  await expect(page.getByText("isn't linked to a health record yet").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "No active visit" })).toBeVisible();
});

test("student follows their queue position and sees vitals, not clinical text", async ({ page }) => {
  const errors = watchErrors(page);
  const student = await linkedStudent();
  const opd = await department();
  const admin = await token("admin", "admin123");
  const urgent = await api("/api/patients", { token: admin, method: "POST", body: { fullName: `Urgent ${unique()}`, sex: "Male", phone: "0" } });
  const u = await api("/api/visits", { token: admin, method: "POST", body: { patient: urgent.id, department: opd.id, esi: 1 } });
  const v = await api("/api/visits", { token: admin, method: "POST", body: { patient: student.patient.id, department: opd.id, esi: 4,
    chief_complaint: "private complaint text", vitals: { heart_rate: 92, temperature_c: 37.9 } } });

  await signInStudent(page, student.matric, student.password);
  await expect(page.getByRole("heading", { name: "You're in the queue" })).toBeVisible();
  await expect(page.getByText(/(person is|people are) ahead of you in Outpatient Department/)).toBeVisible();
  await expect(page.getByText("Penicillin")).toBeVisible();
  await expect(page.getByText("37.9")).toBeVisible();
  await expect(page.getByText("private complaint text")).toHaveCount(0);

  const nurse = await token("nurse", "nurse123");
  await api(`/api/visits/${v.id}/call`, { token: nurse, method: "POST" });
  await expect(page.getByRole("heading", { name: "You've been called" })).toBeVisible({ timeout: 30_000 }); // 20 s refresh

  for (const id of [u.id, v.id]) await api(`/api/visits/${id}/cancel`, { token: admin, method: "POST" }).catch(() => {});
  expect(errors).toEqual([]);
});
