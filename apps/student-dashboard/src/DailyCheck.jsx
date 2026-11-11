import { useEffect, useState } from "react";
import { getDailyCheck, sendDailyCheck } from "./api";

const C = { ink: "#0E2140", cobalt: "#2F5BFF", mint: "#2BC3A0", coral: "#FF6B6B", mist: "#EDF2F9", line: "#D9E2EF" };

const FEELINGS = [[1, "Very unwell"], [2, "Unwell"], [3, "Okay"], [4, "Good"], [5, "Great"]];
const SYMPTOMS = [
  ["fever", "Fever"], ["headache", "Headache"], ["cough", "Cough"], ["sore_throat", "Sore throat"],
  ["body_aches", "Body aches"], ["stomach_pain", "Stomach pain"], ["diarrhoea", "Diarrhoea"], ["vomiting", "Vomiting"],
  ["rash", "Rash"], ["dizzy", "Dizziness"], ["chest_pain", "Chest pain"], ["breathless", "Short of breath"],
];
const STATUS = {
  good: { bg: "#E3F7F1", fg: "#0D6B55" },
  watch: { bg: "#FFF4E2", fg: "#7A4C00" },
  see_clinic: { bg: "#FFE9E9", fg: "#B23A3A" },
  urgent: { bg: "#B23A3A", fg: "#FFFFFF" },
};
const DAY = (d) => new Date(d).toLocaleDateString("en-GB", { weekday: "short" });

function Result({ result, onRedo }) {
  const tone = STATUS[result.status] ?? STATUS.good;
  return (
    <div className="grid gap-3" aria-live="polite">
      <div className="rounded-2xl p-4" style={{ background: tone.bg, color: tone.fg }}>
        <p className="text-lg font-semibold">{result.headline}</p>
      </div>
      <ul className="grid gap-2">
        {result.tips.map((tip) => (
          <li key={tip.topic + tip.text} className="rounded-2xl p-3 bg-white" style={{ border: `1px solid ${C.line}` }}>
            <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: C.cobalt }}>{tip.topic}</span>
            <p className="text-sm mt-0.5">{tip.text}</p>
          </li>
        ))}
      </ul>
      <p className="text-xs" style={{ color: "#5B6F8F" }}>{result.disclaimer}</p>
      <button type="button" onClick={onRedo} className="justify-self-start text-sm font-semibold" style={{ color: C.cobalt }}>
        Update today's check-in
      </button>
    </div>
  );
}

/** Daily health check-in: a few questions, then personal tips (from the AI service) and whether to come in. */
export default function DailyCheck() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ feeling: null, sleep_hours: "", water_glasses: "", stress: null, symptoms: [] });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => { getDailyCheck().then(setData, (e) => setError(e.message)); }, []);

  const toggle = (s) => setForm((f) => ({ ...f, symptoms: f.symptoms.includes(s) ? f.symptoms.filter((x) => x !== s) : [...f.symptoms, s] }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const today = await sendDailyCheck({
        feeling: form.feeling, symptoms: form.symptoms, stress: form.stress ?? undefined,
        sleep_hours: form.sleep_hours === "" ? undefined : Number(form.sleep_hours),
        water_glasses: form.water_glasses === "" ? undefined : Number(form.water_glasses),
      });
      setData(await getDailyCheck().catch(() => ({ today, week: data?.week ?? [] })));
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const chip = (active) => ({ background: active ? C.ink : "#fff", color: active ? "#fff" : C.ink, border: `1px solid ${active ? C.ink : C.line}` });
  const showForm = editing || (data && !data.today);

  return (
    <section className="grid gap-4">
      <div>
        <h2 className="text-2xl font-bold" style={{ color: C.ink, fontFamily: "Georgia, serif" }}>Daily health check</h2>
        <p className="text-sm" style={{ color: "#5B6F8F" }}>Two minutes a day. You'll get tips for today, and we'll tell you if you should come in.</p>
      </div>
      {error && <div role="alert" className="rounded-xl p-3 text-sm" style={{ background: "#FFE9E9", color: "#B23A3A" }}>{error}</div>}
      {!data && !error && <p className="text-sm" style={{ color: "#5B6F8F" }}>Loading…</p>}

      {data?.week?.length > 0 && (
        <div className="flex gap-2 flex-wrap" aria-label="Your last 7 days">
          {[...data.week].reverse().map((d) => (
            <span key={d.day} className="rounded-xl px-3 py-1.5 text-xs font-semibold"
              style={{ background: (STATUS[d.status] ?? STATUS.good).bg, color: (STATUS[d.status] ?? STATUS.good).fg }}>
              {DAY(d.day)} · {FEELINGS[d.feeling - 1]?.[1]}
            </span>
          ))}
        </div>
      )}

      {data?.today && !editing && <Result result={data.today} onRedo={() => setEditing(true)} />}

      {showForm && (
        <form onSubmit={submit} className="bg-white rounded-3xl p-5 grid gap-5" style={{ border: `1px solid ${C.line}` }}>
          <fieldset className="grid gap-2">
            <legend className="text-sm font-semibold mb-2">How do you feel today?</legend>
            <div className="flex flex-wrap gap-2">
              {FEELINGS.map(([value, label]) => (
                <button key={value} type="button" aria-pressed={form.feeling === value} onClick={() => setForm({ ...form, feeling: value })}
                  className="rounded-full px-4 py-2 text-sm" style={chip(form.feeling === value)}>{label}</button>
              ))}
            </div>
          </fieldset>
          <fieldset className="grid gap-2">
            <legend className="text-sm font-semibold mb-2">Any of these today?</legend>
            <div className="flex flex-wrap gap-2">
              {SYMPTOMS.map(([value, label]) => (
                <button key={value} type="button" aria-pressed={form.symptoms.includes(value)} onClick={() => toggle(value)}
                  className="rounded-full px-3 py-1.5 text-sm" style={chip(form.symptoms.includes(value))}>{label}</button>
              ))}
            </div>
          </fieldset>
          <div className="grid sm:grid-cols-3 gap-3">
            <label className="text-sm">Hours of sleep last night
              <input type="number" min="0" max="24" step="0.5" value={form.sleep_hours} onChange={(e) => setForm({ ...form, sleep_hours: e.target.value })}
                className="mt-1 w-full rounded-xl px-3 py-2" style={{ border: `1px solid ${C.line}` }} />
            </label>
            <label className="text-sm">Glasses of water yesterday
              <input type="number" min="0" max="40" value={form.water_glasses} onChange={(e) => setForm({ ...form, water_glasses: e.target.value })}
                className="mt-1 w-full rounded-xl px-3 py-2" style={{ border: `1px solid ${C.line}` }} />
            </label>
            <label className="text-sm">Stress (1 calm – 5 very stressed)
              <select value={form.stress ?? ""} onChange={(e) => setForm({ ...form, stress: e.target.value ? Number(e.target.value) : null })}
                className="mt-1 w-full rounded-xl px-3 py-2 bg-white" style={{ border: `1px solid ${C.line}` }}>
                <option value="">Skip</option>
                {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </div>
          <button disabled={busy || !form.feeling} className="rounded-full py-2.5 text-sm font-semibold text-white disabled:opacity-40" style={{ background: C.ink }}>
            {busy ? "Getting your tips…" : "Get today's tips"}
          </button>
        </form>
      )}
    </section>
  );
}
