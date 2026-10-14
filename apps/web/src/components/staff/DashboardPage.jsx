import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { Empty, ErrorBox, Loading, PageHeader } from "../ui";

const minutes = (value) => (value === null || value === undefined ? "—" : `${value} min`);

export default function DashboardPage() {
  const { data, error, loading, reload } = useApi(() => mediflowApi.dashboard(), [], { refreshMs: 30000 });

  return (
    <>
      <PageHeader title="Today" subtitle="Live numbers from today's check-ins. Updates every 30 seconds.">
        <button type="button" className="btn btn-secondary" onClick={reload} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </PageHeader>
      <ErrorBox error={error} onRetry={reload} />
      {!data && loading && <Loading />}
      {data && (
        <>
          <div className="stats">
            <Stat label="Patients today" value={data.patientsToday} />
            <Stat label="Waiting now" value={data.currentlyWaiting} />
            <Stat label="Emergencies waiting" value={data.emergencyCases} tone={data.emergencyCases ? "alert" : undefined} hint="ESI 1–2" />
            <Stat label="In consultation" value={data.inConsultation} />
            <Stat label="Completed today" value={data.completedToday} />
            <Stat label="Average wait" value={minutes(data.averageWaitMinutes)} hint="Check-in to called" />
            <Stat label="Longest current wait" value={minutes(data.longestCurrentWaitMinutes)} tone={data.longestCurrentWaitMinutes > 60 ? "alert" : undefined} />
          </div>
          <section className="panel">
            <h2>Check-ins by department</h2>
            {data.byDepartment.length === 0 ? (
              <Empty>No check-ins yet today.</Empty>
            ) : (
              <table className="table">
                <thead>
                  <tr><th>Department</th><th className="num">Check-ins</th></tr>
                </thead>
                <tbody>
                  {data.byDepartment.map((row) => (
                    <tr key={row.department__name}>
                      <td>{row.department__name}</td>
                      <td className="num">{row.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </>
  );
}

function Stat({ label, value, hint, tone }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}
