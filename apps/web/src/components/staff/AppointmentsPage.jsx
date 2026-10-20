import { useRef, useState } from "react";
import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { useQueueEvents } from "../../hooks/useQueueEvents";
import { Empty, ErrorBox, LiveBadge, Loading, PageHeader, formatDate } from "../ui";

const todayISO = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time

const STATUS = {
  requested: "Requested", confirmed: "Confirmed", declined: "Declined", cancelled: "Cancelled", checked_in: "Checked in",
};

export function AppointmentBadge({ status }) {
  return <span className={`badge appt-${status}`}>{STATUS[status] ?? status}</span>;
}

/** Front desk: answer students' requests and check booked patients in on the day. */
export default function AppointmentsPage() {
  const [tab, setTab] = useState("requests");
  const [day, setDay] = useState(todayISO());
  const params = tab === "requests" ? { status: "requested" } : { date: day, status: "confirmed,checked_in" };
  const reload = useRef(null);
  const live = useQueueEvents(() => reload.current?.());
  const list = useApi(() => mediflowApi.appointments(params), [tab, day], { refreshMs: live ? 60000 : 20000 });
  reload.current = list.reload;
  const [notice, setNotice] = useState(null);

  return (
    <>
      <PageHeader title="Appointments" subtitle="Requests from students, and today's booked patients.">
        <LiveBadge live={live} />
      </PageHeader>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "requests"} className={`tab ${tab === "requests" ? "active" : ""}`} onClick={() => setTab("requests")}>
          Requests to review
        </button>
        <button type="button" role="tab" aria-selected={tab === "day"} className={`tab ${tab === "day" ? "active" : ""}`} onClick={() => setTab("day")}>
          Day view
        </button>
      </div>
      {notice && <div className="success-box" role="status">{notice}</div>}

      <section className="panel">
        {tab === "day" && (
          <div className="filters">
            <label htmlFor="appt-day" className="sr-only">Day</label>
            <input id="appt-day" type="date" value={day} onChange={(e) => setDay(e.target.value)} />
            <button type="button" className="btn btn-secondary" onClick={() => setDay(todayISO())}>Today</button>
          </div>
        )}
        <ErrorBox error={list.error} onRetry={list.reload} />
        {!list.data && list.loading && <Loading />}
        {list.data && list.data.length === 0 && (
          <Empty>{tab === "requests" ? "No requests waiting." : `No appointments on ${formatDate(day)}.`}</Empty>
        )}
        {list.data && list.data.length > 0 && (
          <table className="table">
            <thead><tr><th>When</th><th>Patient</th><th>Department</th><th>Reason</th><th>Status</th><th /></tr></thead>
            <tbody>
              {list.data.map((a) => (
                <AppointmentRow key={a.id} appt={a} isToday={a.date === todayISO()}
                  onDone={(message) => { setNotice(message); list.reload(); }} />
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

function AppointmentRow({ appt, isToday, onDone }) {
  const [mode, setMode] = useState(null); // null | confirm | decline | check_in
  const [date, setDate] = useState(appt.date);
  const [time, setTime] = useState(appt.time);
  const [note, setNote] = useState("");
  const [esi, setEsi] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(action, body, message) {
    setBusy(true);
    setError(null);
    try {
      await mediflowApi.appointmentAction(appt.id, action, body);
      setMode(null);
      onDone(message);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const who = `${appt.patient_name} (${appt.reference})`;
  return (
    <>
      <tr>
        <td className="nowrap"><strong>{appt.time}</strong><div className="small muted">{formatDate(appt.date)}</div></td>
        <td><strong>{appt.patient_name}</strong><div className="mono small">{appt.patient_hospital_number}</div></td>
        <td>{appt.department_name}</td>
        <td>{appt.reason || "—"}{appt.staff_note && <div className="small muted">Note: {appt.staff_note}</div>}</td>
        <td><AppointmentBadge status={appt.status} /></td>
        <td className="actions">
          {appt.status === "requested" && (
            <>
              <button type="button" className="btn btn-small" disabled={busy} onClick={() => setMode(mode === "confirm" ? null : "confirm")}>Confirm</button>
              <button type="button" className="btn btn-small btn-danger" disabled={busy} onClick={() => setMode(mode === "decline" ? null : "decline")}>Decline</button>
            </>
          )}
          {appt.status === "confirmed" && (
            <>
              {isToday && <button type="button" className="btn btn-small" disabled={busy} onClick={() => setMode(mode === "check_in" ? null : "check_in")}>Check in</button>}
              <button type="button" className="btn btn-small btn-danger" disabled={busy}
                onClick={() => window.confirm(`Cancel ${who}?`) && run("cancel", {}, `${who} cancelled.`)}>
                Cancel
              </button>
            </>
          )}
        </td>
      </tr>
      {mode && (
        <tr className="row-form">
          <td colSpan={6}>
            <ErrorBox error={error} />
            <form className="inline-form" onSubmit={(e) => {
              e.preventDefault();
              if (mode === "confirm") run("confirm", { date, time, ...(note ? { note } : {}) }, `${who} confirmed for ${date} ${time}.`);
              if (mode === "decline") run("decline", { note }, `${who} declined.`);
              if (mode === "check_in") run("check_in", { esi: Number(esi) }, `${appt.patient_name} checked in. They're now in the queue.`);
            }}>
              {mode === "confirm" && (
                <>
                  <label>Date<input type="date" value={date} onChange={(e) => setDate(e.target.value)} required /></label>
                  <label>Time<input type="time" step="900" value={time} onChange={(e) => setTime(e.target.value)} required /></label>
                  <label className="grow">Note to the patient (optional)<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="e.g. Bring your health card" /></label>
                </>
              )}
              {mode === "decline" && (
                <label className="grow">Reason (shown to the patient)<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} required placeholder="e.g. Fully booked that day. Please choose Thursday." /></label>
              )}
              {mode === "check_in" && (
                <label>Triage level (ESI)
                  <select value={esi} onChange={(e) => setEsi(e.target.value)} required>
                    <option value="">Select…</option>
                    {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
              )}
              <button type="submit" className="btn btn-small" disabled={busy}>{busy ? "…" : "Save"}</button>
              <button type="button" className="btn btn-small btn-secondary" onClick={() => setMode(null)}>Close</button>
            </form>
          </td>
        </tr>
      )}
    </>
  );
}
