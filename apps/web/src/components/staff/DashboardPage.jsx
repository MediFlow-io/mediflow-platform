import { useRef } from "react";
import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { useQueueEvents } from "../../hooks/useQueueEvents";
import { Empty, ErrorBox, LiveBadge, Loading, PageHeader } from "../ui";

const minutes = (value) => (value === null || value === undefined ? "—" : `${value} min`);

export default function DashboardPage() {
  const reloadRef = useRef(null);
  const live = useQueueEvents(() => reloadRef.current?.(), { debounceMs: 1000 });
  const { data, error, loading, reload } = useApi(() => mediflowApi.dashboard(), [], { refreshMs: live ? 60000 : 30000 });
  reloadRef.current = reload;

  return (
    <>
      <PageHeader title="Today" subtitle="Numbers from today's check-ins.">
        <LiveBadge live={live} />
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
            <Stat label="Longest current wait" value={minutes(data.longestCurrentWaitMinutes)} tone={data.longestCurrentWaitMinutes > (data.longWaitMinutes ?? 60) ? "alert" : undefined} />
            <Stat label="Over ESI target" value={data.overTarget ?? 0} tone={data.overTarget ? "alert" : undefined} hint="Waiting longer than their level allows" />
          </div>
          {data.departmentLoad?.length > 0 && (
            <section className="panel">
              <h2>Queue load now</h2>
              <table className="table">
                <thead>
                  <tr><th>Department</th><th className="num">Waiting</th><th className="num">In consultation</th><th className="num">Longest wait</th><th className="num">Over target</th><th className="num">Over {data.longWaitMinutes} min</th></tr>
                </thead>
                <tbody>
                  {data.departmentLoad.map((d) => (
                    <tr key={d.name} className={d.overTarget ? "row-urgent" : undefined}>
                      <td>{d.name}</td>
                      <td className="num">{d.waiting}</td>
                      <td className="num">{d.inConsultation}</td>
                      <td className="num">{d.waiting ? minutes(d.longestWaitMinutes) : "—"}</td>
                      <td className="num">{d.overTarget}</td>
                      <td className="num">{d.longWaits}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
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
