// Shared helpers. All API calls go through the web app's origin, which routes /api to the right
// service (the Vite dev proxy locally, Nginx in Docker), exactly as the browser does.
export const WEB = process.env.WEB_URL ?? "http://localhost:5173";
export const STUDENT = process.env.STUDENT_URL ?? "http://localhost:5174";
export const ADMIN = process.env.ADMIN_URL ?? "http://localhost:8082";

import { randomInt } from "node:crypto";

export const unique = () => `${Date.now() % 1_000_000}${randomInt(10, 100)}`;

export async function api(path, { token, method = "GET", body } = {}) {
  const res = await fetch(WEB + path, {
    method,
    body: body && JSON.stringify(body),
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${JSON.stringify(data)}`);
  return data;
}

// Access tokens last 10 minutes; reusing them for 5 keeps the suite under the login rate limit.
const tokens = new Map();
export async function token(username, password) {
  const key = `${username}
${password}`;
  const cached = tokens.get(key);
  if (cached && Date.now() - cached.at < 5 * 60_000) return cached.access;
  const { access } = await api("/api/auth/login", { method: "POST", body: { unique_id: username, password } });
  tokens.set(key, { access, at: Date.now() });
  return access;
}

export async function signInStaff(page, username, password) {
  await page.goto(`${WEB}/login`);
  await page.getByLabel("Staff ID").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

export async function signInStudent(page, matric, password) {
  await page.goto(STUDENT);
  await page.getByLabel("Matric number").fill(matric);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Registers a student account and a patient record linked to it. */
export async function linkedStudent() {
  const id = unique();
  const student = { matric: `E2E/${id}`, password: "Student-Pass-2026", name: `E2E Student ${id}` };
  await api("/api/auth/register/student", { method: "POST", body: { unique_id: student.matric, password: student.password, name: student.name } });
  const admin = await token("admin", "admin123");
  student.patient = await api("/api/patients", { token: admin, method: "POST",
    body: { fullName: student.name, sex: "Female", phone: "0", allergies: "Penicillin", linkedAccount: student.matric } });
  return student;
}

export async function department(code = "opd") {
  const admin = await token("admin", "admin123");
  return (await api("/api/departments", { token: admin })).find((d) => d.code === code);
}

/** Fails the test on uncaught page errors (console noise from expected 4xx responses is ignored). */
export function watchErrors(page) {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}
