import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { ErrorBox } from "../ui";

/** Staff book an appointment for a patient (confirmed straight away). */
export default function BookAppointmentForm({ patient, onDone, onCancel }) {
  const departments = useApi(() => mediflowApi.departments(), []);
  const [form, setForm] = useState({ department: "", date: "", time: "", reason: "" });
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = (name) => (e) => setForm({ ...form, [name]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const appt = await mediflowApi.bookAppointment({ ...form, patient: patient.id, department: Number(form.department) });
      onDone?.(appt);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="form-grid">
      <ErrorBox error={error || departments.error} />
      <fieldset>
        <legend>Book an appointment for {patient.fullName}</legend>
        <div className="field">
          <label htmlFor="ba-dept">Department *</label>
          <select id="ba-dept" value={form.department} onChange={set("department")} required>
            <option value="">{departments.loading ? "Loading…" : "Select…"}</option>
            {(departments.data || []).filter((d) => d.active).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="ba-reason">Reason</label>
          <input id="ba-reason" value={form.reason} onChange={set("reason")} maxLength={300} />
        </div>
        <div className="field">
          <label htmlFor="ba-date">Date *</label>
          <input id="ba-date" type="date" value={form.date} onChange={set("date")} required />
        </div>
        <div className="field">
          <label htmlFor="ba-time">Time *</label>
          <input id="ba-time" type="time" step="900" value={form.time} onChange={set("time")} required />
        </div>
      </fieldset>
      <div className="form-actions">
        <button type="submit" className="btn" disabled={saving}>{saving ? "Booking…" : "Book appointment"}</button>
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={saving}>Cancel</button>
      </div>
    </form>
  );
}
