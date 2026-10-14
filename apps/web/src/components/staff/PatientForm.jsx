import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { ErrorBox } from "../ui";

const EMPTY = {
  fullName: "", sex: "", phone: "", dateOfBirth: "", address: "", nextOfKin: "", nextOfKinPhone: "",
  allergies: "", medicalHistory: "", complaint: "", diagnosis: "", treatment: "", notes: "", linkedAccount: "",
};

const fromPatient = (p) => ({
  ...EMPTY,
  ...Object.fromEntries(Object.keys(EMPTY).map((k) => [k, p[k] ?? ""])),
  linkedAccount: p.linkedAccountName ?? "",
});

/** Create (no `patient`) or edit a patient. `readOnly` shows the record without inputs being editable. */
export default function PatientForm({ patient, readOnly = false, canLink = false, onSaved, onCancel }) {
  const [form, setForm] = useState(() => (patient ? fromPatient(patient) : EMPTY));
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const field = (name) => ({
    id: `pf-${name}`,
    value: form[name],
    disabled: readOnly || saving,
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
  });

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    const payload = { ...form, dateOfBirth: form.dateOfBirth || null };
    if (!canLink || (patient && form.linkedAccount === (patient.linkedAccountName ?? ""))) delete payload.linkedAccount;
    try {
      const saved = patient
        ? await mediflowApi.updatePatient(patient.id, payload)
        : await mediflowApi.createPatient(payload);
      onSaved?.(saved);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="form-grid">
      <ErrorBox error={error} />
      <fieldset>
        <legend>Personal details</legend>
        <div className="field span-2">
          <label htmlFor="pf-fullName">Full name *</label>
          <input {...field("fullName")} required maxLength={200} />
        </div>
        <div className="field">
          <label htmlFor="pf-sex">Sex *</label>
          <select {...field("sex")} required>
            <option value="">Select…</option>
            <option>Female</option>
            <option>Male</option>
            <option>Other</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="pf-dateOfBirth">Date of birth</label>
          <input type="date" {...field("dateOfBirth")} max={new Date().toISOString().slice(0, 10)} />
        </div>
        <div className="field">
          <label htmlFor="pf-phone">Phone *</label>
          <input type="tel" {...field("phone")} required maxLength={30} />
        </div>
        <div className="field">
          <label htmlFor="pf-address">Address</label>
          <input {...field("address")} />
        </div>
        <div className="field">
          <label htmlFor="pf-nextOfKin">Next of kin</label>
          <input {...field("nextOfKin")} maxLength={200} />
        </div>
        <div className="field">
          <label htmlFor="pf-nextOfKinPhone">Next of kin phone</label>
          <input type="tel" {...field("nextOfKinPhone")} maxLength={30} />
        </div>
      </fieldset>

      <fieldset>
        <legend>Medical</legend>
        <div className="field span-2">
          <label htmlFor="pf-allergies">Allergies</label>
          <input {...field("allergies")} placeholder="e.g. Penicillin" />
        </div>
        <div className="field span-2">
          <label htmlFor="pf-medicalHistory">Medical history</label>
          <textarea rows={2} {...field("medicalHistory")} />
        </div>
        <div className="field span-2">
          <label htmlFor="pf-complaint">Presenting complaint</label>
          <textarea rows={2} {...field("complaint")} />
        </div>
        <div className="field">
          <label htmlFor="pf-diagnosis">Diagnosis</label>
          <textarea rows={2} {...field("diagnosis")} />
        </div>
        <div className="field">
          <label htmlFor="pf-treatment">Treatment</label>
          <textarea rows={2} {...field("treatment")} />
        </div>
        <div className="field span-2">
          <label htmlFor="pf-notes">Clinical notes (staff only)</label>
          <textarea rows={2} {...field("notes")} />
        </div>
      </fieldset>

      {canLink && (
        <fieldset>
          <legend>Student access</legend>
          <div className="field span-2">
            <label htmlFor="pf-linkedAccount">Linked account (matric number / username)</label>
            <input {...field("linkedAccount")} placeholder="Leave empty for no student access" />
            <p className="hint">
              The linked person can see their own record, visits and queue position in the student dashboard.
              Diagnosis, treatment and clinical notes are never shown to them.
            </p>
          </div>
        </fieldset>
      )}

      {!readOnly && (
        <div className="form-actions">
          <button type="submit" className="btn" disabled={saving}>
            {saving ? "Saving…" : patient ? "Save changes" : "Register patient"}
          </button>
          {onCancel && (
            <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={saving}>
              Cancel
            </button>
          )}
        </div>
      )}
    </form>
  );
}
