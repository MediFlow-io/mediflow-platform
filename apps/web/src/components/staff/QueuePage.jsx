import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useAuth } from "../../api/AuthContext";
import { useApi } from "../../hooks/useApi";
import { actionsFor } from "../../lib/roles";
import { Empty, ErrorBox, EsiBadge, Loading, PageHeader, StatusBadge, formatTime, formatVitals } from "../ui";

export default function QueuePage() {
  const { user } = useAuth();
  const [department, setDepartment] = useState("");
  const departments = useApi(() => mediflowApi.departments(), []);
  // Waiting patients come from the ordered queue; called/in-consultation from today's visits.
  const queue = useApi(() => mediflowApi.queue(department), [department], { refreshMs: 15000 });
  const active = useApi(() => mediflowApi.visits({ status: "called,in_progress", department }), [department], { refreshMs: 15000 });
  const [busy, setBusy] = useState(null);
  const deptName = (code) => (departments.data || []).find((d) => d.code === code)?.name ?? code;
  const [actionError, setActionError] = useState(null);

  async function run(visitId, action) {
    if (action === "cancel" && !window.confirm("Cancel this visit? The patient leaves the queue.")) return;
    setBusy(`${visitId}:${action}`);
    setActionError(null);
    try {
      await mediflowApi.visitAction(visitId, action);
      await Promise.all([queue.reload(), active.reload()]);
    } catch (error) {
      setActionError(error);
    } finally {
      setBusy(null);
    }
  }

  const buttons = (visitId, status) =>
    actionsFor(user, status).map(({ name, label }) => (
      <button
        key={name}
        type="button"
        className={`btn btn-small ${name === "cancel" ? "btn-danger" : ""}`}
        disabled={busy !== null}
        onClick={() => run(visitId, name)}
      >
        {busy === `${visitId}:${name}` ? "…" : label}
      </button>
    ));

  return (
    <>
      <PageHeader title="Queue" subtitle="Most urgent first (ESI), then by arrival. Updates every 15 seconds.">
        <select aria-label="Department" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {(departments.data || []).filter((d) => d.active).map((d) => (
            <option key={d.code} value={d.code}>{d.name}</option>
          ))}
        </select>
      </PageHeader>
      <ErrorBox error={actionError} />

      <section className="panel">
        <h2>With staff now</h2>
        <ErrorBox error={active.error} onRetry={active.reload} />
        {!active.data && active.loading && <Loading />}
        {active.data && active.data.length === 0 && <Empty>Nobody has been called yet.</Empty>}
        {active.data && active.data.length > 0 && (
          <table className="table">
            <thead>
              <tr><th>Patient</th><th>Department</th><th>Status</th><th>Clinician</th><th>Since</th><th /></tr>
            </thead>
            <tbody>
              {active.data.map((v) => (
                <tr key={v.id}>
                  <td>
                    <strong>{v.patient_name}</strong><div className="mono small">{v.patient_hospital_number}</div>
                    {v.chief_complaint && <div className="small">{v.chief_complaint}</div>}
                    {formatVitals(v) && <div className="small muted">{formatVitals(v)}</div>}
                  </td>
                  <td>{v.department_name}</td>
                  <td><StatusBadge status={v.status} /></td>
                  <td>{v.assigned_clinician_name || "—"}</td>
                  <td>{formatTime(v.started_at || v.called_at)}</td>
                  <td className="actions">{buttons(v.id, v.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <h2>Waiting {queue.data ? `(${queue.data.length})` : ""}</h2>
        <ErrorBox error={queue.error} onRetry={queue.reload} />
        {!queue.data && queue.loading && <Loading />}
        {queue.data && queue.data.length === 0 && <Empty>No one is waiting.</Empty>}
        {queue.data && queue.data.length > 0 && (
          <table className="table">
            <thead>
              <tr><th>#</th><th>Patient</th><th>Priority</th><th>Department</th><th>Arrived</th><th>Waited</th><th /></tr>
            </thead>
            <tbody>
              {queue.data.map((q) => (
                <tr key={q.id} className={q.priority <= 2 ? "row-urgent" : undefined}>
                  <td>{q.position}</td>
                  <td>
                    <strong>{q.fullName}</strong><div className="mono small">{q.hospitalNumber}</div>
                    {q.chiefComplaint && <div className="small muted">{q.chiefComplaint}</div>}
                  </td>
                  <td><EsiBadge esi={q.priority} /></td>
                  <td>{deptName(q.department)}</td>
                  <td>{q.arrival}</td>
                  <td className={q.waitingMinutes >= 60 ? "text-alert" : undefined}>{q.wait}</td>
                  <td className="actions">{buttons(q.id, "waiting")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
