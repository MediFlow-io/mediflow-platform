import { Fragment, useRef, useState } from "react";
import { mediflowApi } from "../../api/client";
import { useAuth } from "../../api/AuthContext";
import { useApi } from "../../hooks/useApi";
import { useQueueEvents } from "../../hooks/useQueueEvents";
import { actionsFor, can } from "../../lib/roles";
import TriageForm from "./TriageForm";
import { Empty, ErrorBox, EsiBadge, LiveBadge, Loading, PageHeader, StatusBadge, formatTime, formatVitals } from "../ui";

export default function QueuePage() {
  const { user } = useAuth();
  const [department, setDepartment] = useState("");
  const departments = useApi(() => mediflowApi.departments(), []);
  // Waiting patients come from the ordered queue; called/in-consultation from today's visits.
  // Live updates from the Go patient-flow service; polling is only a safety net while they're connected.
  const reloaders = useRef([]);
  const live = useQueueEvents(() => reloaders.current.forEach((reload) => reload()));
  const refreshMs = live ? 60000 : 15000;
  const queue = useApi(() => mediflowApi.queue(department), [department], { refreshMs });
  const active = useApi(() => mediflowApi.visits({ status: "called,in_progress", department }), [department], { refreshMs });
  reloaders.current = [queue.reload, active.reload];
  const [busy, setBusy] = useState(null);
  const deptName = (code) => (departments.data || []).find((d) => d.code === code)?.name ?? code;
  const [actionError, setActionError] = useState(null);
  const [triageFor, setTriageFor] = useState(null);
  const [notice, setNotice] = useState(null);

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
      <PageHeader title="Queue" subtitle="Most urgent first (ESI), then by arrival.">
        <LiveBadge live={live} />
        <select aria-label="Department" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {(departments.data || []).filter((d) => d.active).map((d) => (
            <option key={d.code} value={d.code}>{d.name}</option>
          ))}
        </select>
      </PageHeader>
      <ErrorBox error={actionError} />
      {notice && <p className="notice" role="status">{notice}</p>}

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
              <tr><th>#</th><th>Patient</th><th>Priority</th><th>Department</th><th>Arrived</th><th>Waited</th><th>Est. wait</th><th /></tr>
            </thead>
            <tbody>
              {queue.data.map((q) => (
                <Fragment key={q.id}>
                <tr className={q.priority <= 2 ? "row-urgent" : undefined}>
                  <td>{q.position}</td>
                  <td>
                    <strong>{q.fullName}</strong><div className="mono small">{q.hospitalNumber}</div>
                    {q.chiefComplaint && <div className="small muted">{q.chiefComplaint}</div>}
                  </td>
                  <td><EsiBadge esi={q.priority} /></td>
                  <td>{deptName(q.department)}</td>
                  <td>{q.arrival}</td>
                  <td className={q.overTarget ? "text-alert" : undefined}>
                    {q.wait}
                    {q.overTarget && <div className="small">over {q.targetMinutes} min target</div>}
                  </td>
                  <td>{estimate(q.estimatedWaitMinutes)}</td>
                  <td className="actions">
                    {can(user, "changeTriage") && (
                      <button type="button" className="btn btn-small btn-secondary" disabled={busy !== null}
                        onClick={() => { setNotice(null); setTriageFor(triageFor === q.id ? null : q.id); }}>
                        Change ESI
                      </button>
                    )}
                    {buttons(q.id, "waiting")}
                  </td>
                </tr>
                {triageFor === q.id && (
                  <tr className="row-form">
                    <td colSpan={8}>
                      <TriageForm visitId={q.id} current={q.priority} patientName={q.fullName}
                        onCancel={() => setTriageFor(null)}
                        onDone={(message) => { setTriageFor(null); setNotice(message); queue.reload(); }} />
                    </td>
                  </tr>
                )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

// A rough guide from the queue engine: people ahead × recent consultation time ÷ clinicians working.
function estimate(minutes) {
  if (minutes === null || minutes === undefined) return "—";
  if (minutes === 0) return "Next";
  return `~${minutes} min`;
}
