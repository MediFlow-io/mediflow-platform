import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useAuth } from "../../api/AuthContext";
import { useApi } from "../../hooks/useApi";
import { can } from "../../lib/roles";
import { ErrorBox, Loading, formatDate, formatTime } from "../ui";

/** The clinical record of one visit (EMR Lite): notes, diagnoses, prescriptions, referrals, admission. */
export default function VisitRecord({ visitId }) {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi(() => mediflowApi.visitRecord(visitId), [visitId]);
  if (!data && loading) return <Loading />;
  if (!data) return <ErrorBox error={error} onRetry={reload} />;
  const patient = data.visit.patient;
  return (
    <div className="record">
      <div className="record-alerts">
        {patient.allergies ? <span className="badge status-cancelled">Allergies: {patient.allergies}</span>
          : <span className="badge status-completed">No known allergies</span>}
        {patient.chronicConditions.map((c) => <span key={c} className="badge status-called">{c}</span>)}
      </div>
      <Notes visitId={visitId} consultation={data.consultation} canWrite={can(user, "writeNotes")} onSaved={reload} />
      <Diagnoses visitId={visitId} items={data.diagnoses} canWrite={can(user, "prescribe")} onSaved={reload} />
      <Prescriptions visitId={visitId} items={data.prescriptions} canWrite={can(user, "prescribe")} onSaved={reload} />
      <Referrals visitId={visitId} items={data.referrals} canWrite={can(user, "prescribe")} onSaved={reload} />
      <AdmissionBlock visitId={visitId} admission={data.admission} canWrite={can(user, "admit")} onSaved={reload} />
    </div>
  );
}

function useSave(onSaved) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  async function save(call, after) {
    setBusy(true);
    setError(null);
    try {
      await call();
      after?.();
      await onSaved();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, save };
}

function Notes({ visitId, consultation, canWrite, onSaved }) {
  const [notes, setNotes] = useState(consultation?.notes ?? "");
  const { busy, error, save } = useSave(onSaved);
  return (
    <section className="record-section">
      <h3>Consultation notes</h3>
      {consultation && (
        <p className="small muted">By {consultation.clinician ?? "—"}{consultation.updatedBy && consultation.updatedBy !== consultation.clinician
          ? `, last edited by ${consultation.updatedBy}` : ""} · {formatTime(consultation.updatedAt)}</p>
      )}
      {canWrite ? (
        <form onSubmit={(e) => { e.preventDefault(); save(() => mediflowApi.saveConsultation(visitId, notes)); }}>
          <label htmlFor={`notes-${visitId}`} className="sr-only">Consultation notes</label>
          <textarea id={`notes-${visitId}`} rows={5} value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="History, examination, plan" maxLength={20000} />
          <ErrorBox error={error} />
          <button type="submit" className="btn btn-small" disabled={busy || !notes.trim() || notes === (consultation?.notes ?? "")}>
            {busy ? "Saving…" : "Save notes"}
          </button>
        </form>
      ) : (
        <p className="prewrap">{consultation?.notes || <span className="muted">No notes yet.</span>}</p>
      )}
    </section>
  );
}

function Diagnoses({ visitId, items, canWrite, onSaved }) {
  const [form, setForm] = useState({ description: "", code: "", primary: items.length === 0 });
  const { busy, error, save } = useSave(onSaved);
  return (
    <section className="record-section">
      <h3>Diagnoses</h3>
      {items.length === 0 ? <p className="muted small">None recorded.</p> : (
        <ul className="plain-list">
          {items.map((d) => (
            <li key={d.id} className={d.status === "entered_in_error" ? "struck" : undefined}>
              {d.primary && <span className="badge status-in_progress">Primary</span>} {d.description}
              {d.code && <span className="mono small"> {d.code}</span>}
              <span className="small muted"> · {d.recorded_by}</span>
              {d.status === "entered_in_error" && <span className="small muted"> (entered in error)</span>}
              {canWrite && d.status === "active" && (
                <button type="button" className="btn-link small" disabled={busy}
                  onClick={() => window.confirm("Mark this diagnosis as entered in error?") && save(() => mediflowApi.diagnosisInError(d.id))}>
                  Entered in error
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canWrite && (
        <form className="inline-form" onSubmit={(e) => {
          e.preventDefault();
          save(() => mediflowApi.addDiagnosis(visitId, form), () => setForm({ description: "", code: "", primary: false }));
        }}>
          <label className="grow">Diagnosis
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={200} required />
          </label>
          <label>ICD-10 (optional)
            <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} maxLength={16} placeholder="J45.9" />
          </label>
          <label className="check"><input type="checkbox" checked={form.primary} onChange={(e) => setForm({ ...form, primary: e.target.checked })} /> Primary</label>
          <button type="submit" className="btn btn-small" disabled={busy || !form.description.trim()}>Add diagnosis</button>
          <ErrorBox error={error} />
        </form>
      )}
    </section>
  );
}

const NEW_RX = { drug: "", dose: "", route: "oral", frequency: "", duration: "", instructions: "" };

function Prescriptions({ visitId, items, canWrite, onSaved }) {
  const [form, setForm] = useState(NEW_RX);
  const { busy, error, save } = useSave(onSaved);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <section className="record-section">
      <h3>Prescriptions</h3>
      {items.length === 0 ? <p className="muted small">None.</p> : (
        <table className="table">
          <tbody>
            {items.map((p) => (
              <tr key={p.id} className={p.status === "cancelled" ? "row-muted struck" : undefined}>
                <td><strong>{p.drug}</strong> {p.dose} {p.route} · {p.frequency}{p.duration && ` · ${p.duration}`}
                  {p.instructions && <div className="small muted">{p.instructions}</div>}</td>
                <td className="small">{p.status === "dispensed" ? `Dispensed by ${p.dispensed_by}` : p.status === "cancelled" ? `Cancelled: ${p.cancelled_reason}` : "Waiting for pharmacy"}</td>
                <td className="actions">
                  {canWrite && p.status === "prescribed" && (
                    <button type="button" className="btn btn-small btn-secondary" disabled={busy} onClick={() => {
                      const reason = window.prompt("Why cancel this prescription?");
                      if (reason) save(() => mediflowApi.prescriptionAction(p.id, "cancel", { reason }));
                    }}>Cancel</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {canWrite && (
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); save(() => mediflowApi.addPrescription(visitId, form), () => setForm(NEW_RX)); }}>
          <label className="grow">Drug<input value={form.drug} onChange={set("drug")} maxLength={120} required /></label>
          <label>Dose<input value={form.dose} onChange={set("dose")} maxLength={60} required placeholder="500 mg" /></label>
          <label>Route
            <select value={form.route} onChange={set("route")}>
              {["oral", "inhaled", "topical", "IM", "IV", "other"].map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
          <label>Frequency<input value={form.frequency} onChange={set("frequency")} maxLength={60} required placeholder="three times a day" /></label>
          <label>Duration<input value={form.duration} onChange={set("duration")} maxLength={60} placeholder="5 days" /></label>
          <label className="grow">Instructions for the patient<input value={form.instructions} onChange={set("instructions")} maxLength={300} /></label>
          <button type="submit" className="btn btn-small" disabled={busy}>Prescribe</button>
          <ErrorBox error={error} />
        </form>
      )}
    </section>
  );
}

function Referrals({ visitId, items, canWrite, onSaved }) {
  const [form, setForm] = useState({ destination: "", reason: "", urgency: "routine" });
  const { busy, error, save } = useSave(onSaved);
  if (!canWrite && items.length === 0) return null;
  return (
    <section className="record-section">
      <h3>Referrals</h3>
      {items.length > 0 && (
        <ul className="plain-list">
          {items.map((r) => <li key={r.id}><strong>{r.destination}</strong> · {r.urgency} · {r.reason} <span className="small muted">({r.referred_by}, {formatDate(r.created_at)})</span></li>)}
        </ul>
      )}
      {canWrite && (
        <form className="inline-form" onSubmit={(e) => {
          e.preventDefault();
          save(() => mediflowApi.addReferral(visitId, form), () => setForm({ destination: "", reason: "", urgency: "routine" }));
        }}>
          <label className="grow">Refer to<input value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} maxLength={200} required /></label>
          <label>Urgency
            <select value={form.urgency} onChange={(e) => setForm({ ...form, urgency: e.target.value })}>
              <option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option>
            </select>
          </label>
          <label className="grow">Reason<input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required /></label>
          <button type="submit" className="btn btn-small" disabled={busy}>Refer</button>
          <ErrorBox error={error} />
        </form>
      )}
    </section>
  );
}

function AdmissionBlock({ visitId, admission, canWrite, onSaved }) {
  const [ward, setWard] = useState("");
  const [summary, setSummary] = useState("");
  const { busy, error, save } = useSave(onSaved);
  if (!canWrite && !admission) return null;
  return (
    <section className="record-section">
      <h3>Admission</h3>
      {admission ? (
        <>
          <p>{admission.ward} · admitted {formatTime(admission.admittedAt)} by {admission.admittedBy}
            {admission.dischargedAt && <> · discharged {formatTime(admission.dischargedAt)} by {admission.dischargedBy}</>}</p>
          {admission.dischargeSummary && <p className="prewrap small">{admission.dischargeSummary}</p>}
          {canWrite && !admission.dischargedAt && (
            <form className="inline-form" onSubmit={(e) => { e.preventDefault(); save(() => mediflowApi.discharge(visitId, summary)); }}>
              <label className="grow">Discharge summary<input value={summary} onChange={(e) => setSummary(e.target.value)} required /></label>
              <button type="submit" className="btn btn-small" disabled={busy}>Discharge</button>
            </form>
          )}
        </>
      ) : (
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); save(() => mediflowApi.admit(visitId, ward)); }}>
          <label className="grow">Ward or bay<input value={ward} onChange={(e) => setWard(e.target.value)} maxLength={60} required placeholder="Observation bay 1" /></label>
          <button type="submit" className="btn btn-small btn-secondary" disabled={busy}>Admit</button>
        </form>
      )}
      <ErrorBox error={error} />
    </section>
  );
}
