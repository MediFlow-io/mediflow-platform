import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { Empty, ErrorBox, Loading, formatDate } from "../ui";

/** A patient's past diagnoses and medicines, visit by visit (read-only; recording happens on the queue). */
export default function ClinicalHistory({ patientId }) {
  const { data, error, loading, reload } = useApi(() => mediflowApi.patientHistory(patientId), [patientId]);
  if (!data && loading) return <Loading />;
  if (!data) return <ErrorBox error={error} onRetry={reload} />;
  const withRecords = data.visits.filter((v) => v.consultation || v.diagnoses.length || v.prescriptions.length || v.referrals.length || v.admission);
  if (withRecords.length === 0) return <Empty>No clinical records yet.</Empty>;
  return (
    <ul className="history">
      {withRecords.map((r) => (
        <li key={r.visit.id}>
          <div className="small muted">{formatDate(r.visit.checkedInAt)} · {r.visit.department} · {r.visit.visitNumber}</div>
          {r.diagnoses.filter((d) => d.status === "active").map((d) => (
            <div key={d.id}>{d.primary ? <strong>{d.description}</strong> : d.description}{d.code && <span className="mono small"> {d.code}</span>}</div>
          ))}
          {r.prescriptions.filter((p) => p.status !== "cancelled").map((p) => (
            <div key={p.id} className="small">℞ {p.drug} {p.dose} · {p.frequency}{p.duration && ` · ${p.duration}`}</div>
          ))}
          {r.referrals.map((ref) => <div key={ref.id} className="small">Referred to {ref.destination} ({ref.urgency})</div>)}
          {r.admission && <div className="small">Admitted to {r.admission.ward}{r.admission.dischargedAt ? ", discharged" : ""}</div>}
        </li>
      ))}
    </ul>
  );
}
