import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useAuth } from "../../api/AuthContext";
import { useApi } from "../../hooks/useApi";
import { can } from "../../lib/roles";
import { ErrorBox, EsiBadge } from "../ui";

const VITALS = [
  ["heart_rate", "Heart rate", "/min"],
  ["resp_rate", "Resp. rate", "/min"],
  ["spo2", "SpO₂", "%"],
  ["temperature_c", "Temp.", "°C"],
  ["systolic_bp", "Systolic BP", "mmHg"],
];

function ageInYears(dateOfBirth) {
  if (!dateOfBirth) return null;
  const years = (Date.now() - new Date(dateOfBirth).getTime()) / (365.25 * 24 * 3600 * 1000);
  return Math.max(0, Math.round(years * 10) / 10);
}

/** Check a patient into a department queue. Nurses/doctors can ask the AI for an ESI suggestion first. */
export default function CheckInForm({ patient, onDone, onCancel }) {
  const { user } = useAuth();
  const departments = useApi(() => mediflowApi.departments(), []);
  const [department, setDepartment] = useState("");
  const [esi, setEsi] = useState("");
  const [complaint, setComplaint] = useState(patient.complaint || "");
  const [pain, setPain] = useState("");
  const [avpu, setAvpu] = useState("A");
  const [vitals, setVitals] = useState({});
  const [suggestion, setSuggestion] = useState(null);
  const [suggesting, setSuggesting] = useState(false);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const canSuggest = can(user, "triageSuggestion");

  async function suggest() {
    setError(null);
    setSuggesting(true);
    const numeric = Object.fromEntries(
      Object.entries(vitals).filter(([, v]) => v !== "").map(([k, v]) => [k, k === "temperature_c" ? parseFloat(v) : parseInt(v, 10)]),
    );
    try {
      // Only clinical signals are sent. Names and record numbers stay in the core API.
      const result = await mediflowApi.triageSuggestion({
        chief_complaint: complaint,
        age_years: ageInYears(patient.dateOfBirth),
        pain_score: pain === "" ? null : parseInt(pain, 10),
        vitals: { ...numeric, avpu },
      });
      setSuggestion(result);
      if (!esi) setEsi(String(result.suggested_esi));
    } catch (err) {
      setError(err);
    } finally {
      setSuggesting(false);
    }
  }

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const visit = await mediflowApi.checkIn({ patient: patient.id, department: Number(department), esi: Number(esi) });
      onDone?.(visit);
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
        <legend>Check in {patient.fullName}</legend>
        <div className="field">
          <label htmlFor="ci-dept">Department *</label>
          <select id="ci-dept" value={department} onChange={(e) => setDepartment(e.target.value)} required>
            <option value="">{departments.loading ? "Loading…" : "Select…"}</option>
            {(departments.data || []).filter((d) => d.active).map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="ci-esi">Triage level (ESI) *</label>
          <select id="ci-esi" value={esi} onChange={(e) => setEsi(e.target.value)} required>
            <option value="">Select…</option>
            <option value="1">1 · Immediate (life-saving)</option>
            <option value="2">2 · Emergent (high risk)</option>
            <option value="3">3 · Urgent</option>
            <option value="4">4 · Less urgent</option>
            <option value="5">5 · Non-urgent</option>
          </select>
        </div>
      </fieldset>

      {canSuggest && (
        <fieldset>
          <legend>AI triage suggestion (optional)</legend>
          <div className="field span-2">
            <label htmlFor="ci-complaint">Chief complaint</label>
            <input id="ci-complaint" value={complaint} onChange={(e) => setComplaint(e.target.value)} maxLength={500} />
          </div>
          {VITALS.map(([key, label, unit]) => (
            <div className="field" key={key}>
              <label htmlFor={`ci-${key}`}>{label} <span className="muted">{unit}</span></label>
              <input id={`ci-${key}`} type="number" step={key === "temperature_c" ? "0.1" : "1"} min="0"
                value={vitals[key] ?? ""} onChange={(e) => setVitals({ ...vitals, [key]: e.target.value })} />
            </div>
          ))}
          <div className="field">
            <label htmlFor="ci-avpu">Responsiveness</label>
            <select id="ci-avpu" value={avpu} onChange={(e) => setAvpu(e.target.value)}>
              <option value="A">Alert</option>
              <option value="V">Responds to voice</option>
              <option value="P">Responds to pain</option>
              <option value="U">Unresponsive</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="ci-pain">Pain (0–10)</label>
            <input id="ci-pain" type="number" min="0" max="10" value={pain} onChange={(e) => setPain(e.target.value)} />
          </div>
          <div className="span-2">
            <button type="button" className="btn btn-secondary" onClick={suggest} disabled={suggesting}>
              {suggesting ? "Asking…" : "Suggest ESI"}
            </button>
            <p className="hint">Vitals are used for the suggestion only and aren't saved to the record yet.</p>
          </div>
          {suggestion && (
            <div className="suggestion span-2" role="status">
              <div><EsiBadge esi={suggestion.suggested_esi} /> <strong>{suggestion.risk_level}</strong></div>
              <p>{suggestion.recommendation}</p>
              <ul>{suggestion.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              {suggestion.missing_vitals.length > 0 && <p className="hint">Missing: {suggestion.missing_vitals.join(", ")}</p>}
              <p className="hint">{suggestion.disclaimer} You choose the final ESI above.</p>
            </div>
          )}
        </fieldset>
      )}

      <div className="form-actions">
        <button type="submit" className="btn" disabled={saving}>{saving ? "Checking in…" : "Check in"}</button>
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={saving}>Cancel</button>
      </div>
    </form>
  );
}
