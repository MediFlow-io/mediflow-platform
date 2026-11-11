import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { Empty, ErrorBox, Loading, PageHeader } from "../ui";
import { INSURANCE_SCHEMES } from "./PatientForm";

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => `${today().slice(0, 8)}01`;

/** Completed visits by insured patients (NHIA, TISHIP, HMOs), ready to send to the HMO as a spreadsheet. */
export default function ClaimsPage() {
  const [filters, setFilters] = useState({ from: monthStart(), to: today(), scheme: "" });
  const claims = useApi(() => mediflowApi.insuranceClaims(filters), [filters.from, filters.to, filters.scheme]);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);
  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.value });

  async function download() {
    setError(null);
    setDownloading(true);
    try {
      const blob = await mediflowApi.insuranceClaimsCsv(filters);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `insurance-claims-${filters.from}-to-${filters.to}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) {
      setError(err);
    } finally {
      setDownloading(false);
    }
  }

  const rows = claims.data?.claims ?? [];
  return (
    <>
      <PageHeader title="Insurance claims" subtitle="Completed visits by NHIS / HMO patients. Download the file and submit it to the HMO.">
        <button type="button" className="btn" onClick={download} disabled={downloading || rows.length === 0}>
          {downloading ? "Preparing…" : "Download CSV"}
        </button>
      </PageHeader>
      <section className="panel">
        <div className="filters">
          <label>From <input type="date" value={filters.from} max={filters.to} onChange={set("from")} /></label>
          <label>To <input type="date" value={filters.to} min={filters.from} onChange={set("to")} /></label>
          <label>Scheme
            <select value={filters.scheme} onChange={set("scheme")}>
              <option value="">All schemes</option>
              {Object.entries(INSURANCE_SCHEMES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </div>
        <ErrorBox error={error || claims.error} onRetry={claims.reload} />
        {!claims.data && claims.loading && <Loading />}
        {claims.data && rows.length === 0 && <Empty>No completed visits by insured patients in this period.</Empty>}
        {rows.length > 0 && (
          <table className="table">
            <thead><tr><th>Date</th><th>Patient</th><th>NHIA / HMO no.</th><th>Scheme / HMO</th><th>Diagnoses</th><th>Prescriptions</th></tr></thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.visitNumber}>
                  <td>{c.claimDate}</td>
                  <td>{c.patientName}<div className="mono small">{c.hospitalNumber}</div></td>
                  <td className="mono">{c.enrolmentNumber}</td>
                  <td>{c.scheme || "—"}{c.hmo && <div className="small muted">{c.hmo}</div>}</td>
                  <td>{c.diagnoses || "—"}</td>
                  <td>{c.prescriptions || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {rows.length > 0 && <p className="small muted">{rows.length} visit{rows.length === 1 ? "" : "s"}.</p>}
      </section>
    </>
  );
}
