import { useEffect, useState } from "react";
import { mediflowApi } from "../../api/client";
import { useAuth } from "../../api/AuthContext";
import { useApi } from "../../hooks/useApi";
import { can } from "../../lib/roles";
import { Empty, ErrorBox, Loading, PageHeader, StatusBadge, formatDate, formatTime, formatVitals } from "../ui";
import CheckInForm from "./CheckInForm";
import PatientForm from "./PatientForm";

function useDebounced(value, ms = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

export default function PatientsPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const query = useDebounced(search.trim());
  const list = useApi(() => mediflowApi.patients(query), [query]);
  // panel: null | {mode: "new"} | {mode: "view" | "checkin", id}
  const [panel, setPanel] = useState(null);
  const [notice, setNotice] = useState(null);

  const done = (message, next = null) => {
    setNotice(message);
    setPanel(next);
    list.reload();
  };

  return (
    <>
      <PageHeader title="Patients" subtitle="Search by name, hospital number or phone.">
        {can(user, "createPatients") && (
          <button type="button" className="btn" onClick={() => { setNotice(null); setPanel({ mode: "new" }); }}>
            Register patient
          </button>
        )}
      </PageHeader>
      {notice && <div className="success-box" role="status">{notice}</div>}

      <div className="split">
        <section className="panel">
          <input type="search" className="search" placeholder="Search patients…" aria-label="Search patients"
            value={search} onChange={(e) => setSearch(e.target.value)} />
          <ErrorBox error={list.error} onRetry={list.reload} />
          {!list.data && list.loading && <Loading />}
          {list.data && list.data.length === 0 && <Empty>{query ? "No patients match that search." : "No patients registered yet."}</Empty>}
          {list.data && list.data.length > 0 && (
            <ul className="list">
              {list.data.map((p) => (
                <li key={p.id}>
                  <button type="button" className={`list-item ${panel?.id === p.id ? "selected" : ""}`}
                    onClick={() => { setNotice(null); setPanel({ mode: "view", id: p.id }); }}>
                    <strong>{p.fullName}</strong>
                    <span className="mono small">{p.hospitalNumber}</span>
                    <span className="small muted">{p.sex}{p.dateOfBirth ? ` · born ${formatDate(p.dateOfBirth)}` : ""} · {p.phone}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          {!panel && <Empty>Select a patient, or register a new one.</Empty>}
          {panel?.mode === "new" && (
            <>
              <h2>Register patient</h2>
              <PatientForm canLink={can(user, "editPatients")} onCancel={() => setPanel(null)}
                onSaved={(p) => done(`${p.fullName} registered (${p.hospitalNumber}).`, { mode: "view", id: p.id })} />
            </>
          )}
          {panel && panel.mode !== "new" && (
            <PatientDetail key={panel.id} id={panel.id} mode={panel.mode}
              onMode={(mode) => setPanel({ ...panel, mode })}
              onSaved={(message) => done(message, { mode: "view", id: panel.id })} />
          )}
        </section>
      </div>
    </>
  );
}

function PatientDetail({ id, mode, onMode, onSaved }) {
  const { user } = useAuth();
  const patient = useApi(() => mediflowApi.patient(id), [id]);
  const visits = useApi(() => mediflowApi.visits({ patient: id }), [id]);
  const [editing, setEditing] = useState(false);
  const canEdit = can(user, "editPatients");

  if (patient.error) return <ErrorBox error={patient.error} onRetry={patient.reload} />;
  if (!patient.data) return <Loading />;
  const p = patient.data;
  const activeVisit = (visits.data || []).find((v) => ["waiting", "called", "in_progress"].includes(v.status));

  if (mode === "checkin") {
    return <CheckInForm patient={p} onCancel={() => onMode("view")}
      onDone={(v) => onSaved(`${p.fullName} checked in to ${v.department_name} (ESI ${v.esi}).`)} />;
  }

  return (
    <>
      <div className="detail-head">
        <div>
          <h2>{p.fullName}</h2>
          <p className="mono small">{p.hospitalNumber}{p.linkedAccountName ? ` · linked to ${p.linkedAccountName}` : ""}</p>
        </div>
        <div className="page-actions">
          {can(user, "checkIn") && !activeVisit && (
            <button type="button" className="btn" onClick={() => onMode("checkin")}>Check in</button>
          )}
          {canEdit && !editing && <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}>Edit</button>}
        </div>
      </div>
      {activeVisit && (
        <div className="info-box">
          Currently <StatusBadge status={activeVisit.status} /> in {activeVisit.department_name} (ESI {activeVisit.esi}),
          checked in at {formatTime(activeVisit.checked_in_at)}. Manage it from the Queue.
        </div>
      )}
      <PatientForm key={editing ? "edit" : "view"} patient={p} readOnly={!editing} canLink={canEdit}
        onCancel={() => setEditing(false)}
        onSaved={() => { setEditing(false); patient.reload(); onSaved(`${p.fullName}'s record was updated.`); }} />

      <h3>Visits</h3>
      <ErrorBox error={visits.error} onRetry={visits.reload} />
      {visits.data && visits.data.length === 0 && <Empty>No visits yet.</Empty>}
      {visits.data && visits.data.length > 0 && (
        <table className="table">
          <thead><tr><th>Date</th><th>Department</th><th>ESI</th><th>Complaint / observations</th><th>Status</th><th>Clinician</th></tr></thead>
          <tbody>
            {[...visits.data].sort((a, b) => b.checked_in_at.localeCompare(a.checked_in_at)).map((v) => (
              <tr key={v.id}>
                <td>{formatDate(v.checked_in_at)} {formatTime(v.checked_in_at)}</td>
                <td>{v.department_name}</td>
                <td>{v.esi}</td>
                <td>{v.chief_complaint || "—"}{formatVitals(v) && <div className="small muted">{formatVitals(v)}</div>}</td>
                <td><StatusBadge status={v.status} /></td>
                <td>{v.assigned_clinician_name || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
