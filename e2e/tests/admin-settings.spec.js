import { expect, test } from "@playwright/test";
import { ADMIN, api, department, linkedStudent, token, unique } from "./helpers.js";

async function signInAdmin(page) {
  await page.goto(`${ADMIN}/login`);
  await page.getByLabel("Staff ID").fill("admin");
  await page.getByLabel("Password").fill("admin123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
}

test("admin adds a holiday in the console and bookings that day are refused", async ({ page }) => {
  const day = new Date(Date.now() + 20 * 86_400_000).toLocaleDateString("en-CA", { timeZone: "Africa/Lagos" });
  const name = `E2E Day ${unique()}`;
  await signInAdmin(page);
  await page.getByRole("link", { name: "Queue rules & holidays" }).click();
  await page.getByLabel("Date").fill(day);
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Add holiday" }).click();
  await expect(page.getByText(`Holiday added: ${name} (${day}).`)).toBeVisible();

  const student = await linkedStudent();
  const opd = await department();
  const res = await fetch(`${process.env.WEB_URL ?? "http://localhost:5173"}/api/appointments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${await token(student.matric, student.password)}` },
    body: JSON.stringify({ department: opd.id, date: day, time: "10:00", reason: "check-up" }),
  });
  expect(res.status).toBe(400);
  expect((await res.json()).time[0]).toContain(`(${name})`);

  await page.getByRole("row", { name: new RegExp(name) }).getByRole("button", { name: "Remove" }).click();
  await expect(page.getByText("Holiday removed.")).toBeVisible();
});

test("admin gives a department its own hours and rosters a doctor", async ({ page }) => {
  const code = `e2eh${unique()}`.slice(0, 20);
  const admin = await token("admin", "admin123");
  const dept = await api("/api/departments", { token: admin, method: "POST", body: { name: `E2E Hours ${code}`, code, active: true } });

  await signInAdmin(page);
  await page.getByRole("link", { name: "Opening hours" }).click();
  await page.getByLabel("Hours for").selectOption({ label: dept.name });
  await page.getByRole("button", { name: "Show" }).click();
  await expect(page.getByText("This department uses the clinic default hours.")).toBeVisible();
  await page.getByLabel("Monday", { exact: true }).check();
  await page.getByLabel("Monday opens").fill("09:00");
  await page.getByLabel("Monday closes").fill("12:30");
  await page.getByRole("button", { name: "Save hours" }).click();
  await expect(page.getByText("Opening hours saved.")).toBeVisible();
  const hours = await api("/api/clinic/hours", { token: admin });
  expect(hours.filter((h) => h.department === dept.id).map((h) => [h.weekday, h.opens, h.closes])).toEqual([[1, "09:00:00", "12:30:00"]]);

  await page.getByRole("link", { name: "Staff rota" }).click();
  await page.getByLabel("Staff member").selectOption({ label: "Dr. Demo (doctor)" });
  await page.getByLabel("Department").selectOption({ label: dept.name });
  await page.getByLabel("Tue").check();
  await page.getByLabel("Thu").check();
  await page.getByRole("button", { name: "Add shifts" }).click();
  await expect(page.getByText("2 shifts added.")).toBeVisible();
  const shifts = await api(`/api/clinic/shifts?department=${dept.id}`, { token: admin });
  expect(shifts.map((s) => s.day).sort()).toEqual(["Thu", "Tue"]);
  for (const s of shifts) {
    await page.getByRole("button", { name: `Remove Dr. Demo on ${s.day === "Tue" ? "Tuesday" : "Thursday"}` }).first().click();
  }
  await expect(page.getByText("Shift removed.")).toBeVisible();
  await api(`/api/departments/${dept.id}`, { token: admin, method: "PATCH", body: { active: false } });
});
