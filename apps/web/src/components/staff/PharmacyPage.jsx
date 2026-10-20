import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { Empty, ErrorBox, Loading, PageHeader, formatTime } from "../ui";

/** Prescriptions waiting to be dispensed, oldest first, with the patient's allergies shown. */
export default function PharmacyPage() {
  const [tab, setTab] = useState("prescribed");
  const { data, error, loading, reload } = useApi(() => mediflowApi.prescriptions(tab), [tab], { refreshMs: 20000 });
  const [busy, setBusy] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [notice, setNotice] = useState(null);

  async function dispense(p) {
    setBusy(p.id);
    setActionError(null);
    try {
      await mediflowApi.prescriptionAction(p.id, "dispense");
      setNotice(`${p.drug} dispensed to ${p.patient_name}.`);
      await reload();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader title="Pharmacy" subtitle="Check the allergies before dispensing.">
        <div className="tabs" role="tablist">
          {[["prescribed", "To dispense"], ["dispensed", "Dispensed"]].map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} className={`tab ${tab === id ? "active" : ""}`}
              onClick={() => { setNotice(null); setTab(id); }}>{label}</button>
          ))}
        </div>
      </PageHeader>
      {notice && <p className="notice" role="status">{notice}</p>}
      <ErrorBox error={error || actionError} onRetry={reload} />
      {!data && loading && <Loading />}
      {data && data.length === 0 && <Empty>{tab === "prescribed" ? "Nothing waiting." : "Nothing dispensed yet."}</Empty>}
      {data && data.length > 0 && (
        <section className="panel">
          <table className="table">
            <thead><tr><th>Patient</th><th>Medicine</th><th>Prescribed</th><th /></tr></thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{p.patient_name}</strong><div className="mono small">{p.hospital_number}</div>
                    {p.allergies ? <div className="small text-alert">Allergies: {p.allergies}</div> : <div className="small muted">No known allergies</div>}
                  </td>
                  <td>
                    <strong>{p.drug}</strong> {p.dose} · {p.route} · {p.frequency}{p.duration && ` · ${p.duration}`}
                    {p.instructions && <div className="small muted">{p.instructions}</div>}
                  </td>
                  <td className="small">{p.prescribed_by} · {formatTime(p.created_at)}
                    {p.dispensed_at && <div>Dispensed {formatTime(p.dispensed_at)} by {p.dispensed_by}</div>}</td>
                  <td className="actions">
                    {p.status === "prescribed" && (
                      <button type="button" className="btn btn-small" disabled={busy !== null} onClick={() => dispense(p)}>
                        {busy === p.id ? "…" : "Dispense"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
