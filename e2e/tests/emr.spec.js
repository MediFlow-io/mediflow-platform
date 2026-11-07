import { expect, test } from "@playwright/test";
import { api, department, linkedStudent, signInStaff, signInStudent, token, unique } from "./helpers.js";

test("doctor records the visit, pharmacy dispenses, the student sees the medicine", async ({ browser }) => {
  const admin = await token("admin", "admin123");
  const pharmacist = `e2e.pharm${unique()}`;
  await api("/api/users", { token: admin, method: "POST",
    body: { username: pharmacist, password: "Clinic-Pass-2026", role: "pharmacy", display_name: "E2E Pharmacist" } });
  const student = await linkedStudent();
  const opd = await department();
  const visit = await api("/api/visits", { token: admin, method: "POST", body: { patient: student.patient.id, department: opd.id, esi: 3 } });
  await api(`/api/visits/${visit.id}/start`, { token: await token("doctor", "doctor123"), method: "POST" });

  // Doctor: notes, diagnosis and a prescription from the queue.
  const doc = await (await browser.newContext()).newPage();
  await signInStaff(doc, "doctor", "doctor123");
  await doc.getByRole("button", { name: "Queue", exact: true }).click();
  await doc.getByRole("row", { name: new RegExp(student.name) }).getByRole("button", { name: "Record" }).click();
  const record = doc.getByRole("cell", { name: `Clinical record for ${student.name}` });
  await expect(record.getByText("Allergies: Penicillin")).toBeVisible();
  await record.getByLabel("Consultation notes").fill("Cough for 3 days. Chest clear.");
  await record.getByRole("button", { name: "Save notes" }).click();
  await expect(record.getByText(/^By Dr\. Demo/)).toBeVisible();
  await record.getByLabel("Diagnosis").fill("Viral upper respiratory tract infection");
  await record.getByLabel("ICD-10 (optional)").fill("J06.9");
  await record.getByRole("button", { name: "Add diagnosis" }).click();
  await expect(record.getByText("Viral upper respiratory tract infection")).toBeVisible();
  await record.getByLabel("Drug").fill("Paracetamol");
  await record.getByLabel("Dose").fill("1 g");
  await record.getByLabel("Frequency").fill("every 6 hours");
  await record.getByLabel("Duration").fill("3 days");
  await record.getByLabel("Instructions for the patient").fill("Take after food");
  await record.getByRole("button", { name: "Prescribe" }).click();
  await expect(record.getByText("Waiting for pharmacy")).toBeVisible();

  // Pharmacy: sees the allergy and dispenses.
  const ph = await (await browser.newContext()).newPage();
  await signInStaff(ph, pharmacist, "Clinic-Pass-2026");
  await ph.getByRole("button", { name: "Pharmacy", exact: true }).click();
  const row = ph.getByRole("row", { name: new RegExp(student.name) });
  await expect(row.getByText("Allergies: Penicillin")).toBeVisible();
  await row.getByRole("button", { name: "Dispense" }).click();
  await expect(ph.getByText(`Paracetamol dispensed to ${student.name}.`)).toBeVisible();

  // Student: sees what to take, not the diagnosis.
  const st = await (await browser.newContext()).newPage();
  await signInStudent(st, student.matric, student.password);
  await st.getByRole("button", { name: /Medications/ }).click();
  const meds = st.getByRole("list", { name: "Medications" });
  await expect(meds.getByText("Paracetamol 1 g")).toBeVisible();
  await expect(meds.getByText("Collected")).toBeVisible();
  await expect(meds.getByText("Take after food")).toBeVisible();
  await expect(st.getByText("Viral upper respiratory tract infection")).toHaveCount(0);

  await api(`/api/visits/${visit.id}/complete`, { token: admin, method: "POST" });
});
