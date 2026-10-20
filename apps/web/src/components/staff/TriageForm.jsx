import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { ErrorBox } from "../ui";

const LEVELS = { 1: "Immediate", 2: "Emergent", 3: "Urgent", 4: "Less urgent", 5: "Non-urgent" };

/** Escalate or de-escalate a waiting patient. The reason is kept with the visit's triage history. */
export default function TriageForm({ visitId, current, patientName, onDone, onCancel }) {
  const [esi, setEsi] = useState(String(current <= 1 ? 2 : current - 1));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await mediflowApi.changeTriage(visitId, { esi: Number(esi), reason });
      onDone(`${patientName} is now ESI ${esi}.`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <form className="inline-form" onSubmit={submit} aria-label={`Change triage for ${patientName}`}>
      <label>
        New level
        <select value={esi} onChange={(e) => setEsi(e.target.value)}>
          {Object.entries(LEVELS).filter(([level]) => Number(level) !== current).map(([level, name]) => (
            <option key={level} value={level}>ESI {level} · {name}</option>
          ))}
        </select>
      </label>
      <label className="grow">
        Reason
        <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} required
          placeholder="e.g. SpO₂ dropped to 89%" />
      </label>
      <button type="submit" className="btn btn-small" disabled={busy || !reason.trim()}>{busy ? "Saving…" : "Save"}</button>
      <button type="button" className="btn btn-small btn-secondary" onClick={onCancel}>Cancel</button>
      <ErrorBox error={error} />
    </form>
  );
}
