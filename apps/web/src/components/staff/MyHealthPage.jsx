import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { Empty, ErrorBox, Loading, PageHeader, StatusBadge, formatDate } from "../ui";

const FEELINGS = ["Very unwell", "Unwell", "Okay", "Good", "Great"];
const SYMPTOMS = [
  ["fever", "Fever"], ["headache", "Headache"], ["cough", "Cough"], ["sore_throat", "Sore throat"], ["body_aches", "Body aches"],
  ["stomach_pain", "Stomach pain"], ["diarrhoea", "Diarrhoea"], ["vomiting", "Vomiting"], ["rash", "Rash"], ["dizzy", "Dizziness"],
  ["chest_pain", "Chest pain"], ["breathless", "Short of breath"],
];

/** For staff who are also patients: their own record (when linked), medicines and the daily health check. */
export default function MyHealthPage() {
  const health = useApi(() => mediflowApi.myHealth(), []);
  const meds = useApi(() => mediflowApi.myMedications(), []);
  return (
    <>
      <PageHeader title="My health" subtitle="Your own care at the clinic. Only you can see this page." />
      <DailyCheckIn />
      <section className="panel">
        <h2>My visits</h2>
        <ErrorBox error={health.error} onRetry={health.reload} />
        {!health.data && health.loading && <Loading />}
        {health.data && !health.data.linked && (
          <Empty>Your staff account isn't linked to a patient record yet. Ask the front desk to link it next time you're seen.</Empty>
        )}
        {health.data?.activeVisit && (
          <div className="info-box">
            You're <StatusBadge status={health.data.activeVisit.status} /> in {health.data.activeVisit.department}
            {health.data.activeVisit.patientsAhead != null && ` · ${health.data.activeVisit.patientsAhead} ahead of you`}.
          </div>
        )}
        {health.data?.visits?.length > 0 && (
          <ul className="plain-list">
            {health.data.visits.slice(0, 5).map((v) => (
              <li key={v.visitNumber}>{formatDate(v.checkedInAt)} · {v.department} · <StatusBadge status={v.status} /></li>
            ))}
          </ul>
        )}
      </section>
      {meds.data?.medications?.length > 0 && (
        <section className="panel">
          <h2>My medicines</h2>
          <ul className="plain-list">
            {meds.data.medications.map((m, i) => (
              <li key={i}><strong>{m.drug}</strong> {m.dose}, {m.frequency}{m.duration ? `, ${m.duration}` : ""}
                {m.instructions && <div className="small muted">{m.instructions}</div>}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function DailyCheckIn() {
  const check = useApi(() => mediflowApi.dailyCheck(), []);
  const [form, setForm] = useState({ feeling: null, symptoms: [], sleep_hours: "", water_glasses: "", stress: "" });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const today = check.data?.today;
  const toggle = (s) => setForm((f) => ({ ...f, symptoms: f.symptoms.includes(s) ? f.symptoms.filter((x) => x !== s) : [...f.symptoms, s] }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await mediflowApi.sendDailyCheck({
        feeling: form.feeling, symptoms: form.symptoms,
        ...(form.sleep_hours !== "" && { sleep_hours: Number(form.sleep_hours) }),
        ...(form.water_glasses !== "" && { water_glasses: Number(form.water_glasses) }),
        ...(form.stress !== "" && { stress: Number(form.stress) }),
      });
      setEditing(false);
      check.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Daily health check</h2>
      <ErrorBox error={error || check.error} />
      {today && !editing && (
        <div aria-live="polite">
          <div className={`check-status status-${today.status}`}>{today.headline}</div>
          <ul className="plain-list">
            {today.tips.map((t) => <li key={t.topic + t.text}><strong>{t.topic}:</strong> {t.text}</li>)}
          </ul>
          <p className="small muted">{today.disclaimer}</p>
          <button type="button" className="btn-link" onClick={() => setEditing(true)}>Update today's check-in</button>
        </div>
      )}
      {check.data && (!today || editing) && (
        <form onSubmit={submit} className="check-form">
          <p className="small">How do you feel today?</p>
          <div className="chip-row">
            {FEELINGS.map((label, i) => (
              <button key={label} type="button" aria-pressed={form.feeling === i + 1}
                className={`chip ${form.feeling === i + 1 ? "on" : ""}`} onClick={() => setForm({ ...form, feeling: i + 1 })}>{label}</button>
            ))}
          </div>
          <p className="small">Any of these today?</p>
          <div className="chip-row">
            {SYMPTOMS.map(([value, label]) => (
              <button key={value} type="button" aria-pressed={form.symptoms.includes(value)}
                className={`chip ${form.symptoms.includes(value) ? "on" : ""}`} onClick={() => toggle(value)}>{label}</button>
            ))}
          </div>
          <div className="inline-form">
            <label>Hours of sleep<input type="number" min="0" max="24" step="0.5" value={form.sleep_hours} onChange={(e) => setForm({ ...form, sleep_hours: e.target.value })} /></label>
            <label>Glasses of water<input type="number" min="0" max="40" value={form.water_glasses} onChange={(e) => setForm({ ...form, water_glasses: e.target.value })} /></label>
            <label>Stress (1–5)
              <select value={form.stress} onChange={(e) => setForm({ ...form, stress: e.target.value })}>
                <option value="">Skip</option>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}
              </select>
            </label>
          </div>
          <button type="submit" className="btn btn-small" disabled={busy || !form.feeling}>{busy ? "Getting your tips…" : "Get today's tips"}</button>
        </form>
      )}
    </section>
  );
}
