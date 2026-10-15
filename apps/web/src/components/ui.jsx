export function Loading({ label = "Loading…" }) {
  return <p className="muted" role="status">{label}</p>;
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      {error.message || String(error)}
      {onRetry && (
        <button type="button" className="btn-link inline" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ children }) {
  return <p className="muted empty">{children}</p>;
}

const ESI_LABEL = { 1: "ESI 1 · Immediate", 2: "ESI 2 · Emergent", 3: "ESI 3 · Urgent", 4: "ESI 4 · Less urgent", 5: "ESI 5 · Non-urgent" };

export function EsiBadge({ esi }) {
  return <span className={`badge esi-${esi}`}>{ESI_LABEL[esi] ?? `ESI ${esi}`}</span>;
}

const STATUS_LABEL = { waiting: "Waiting", called: "Called", in_progress: "In consultation", completed: "Completed", cancelled: "Cancelled" };

export function StatusBadge({ status }) {
  return <span className={`badge status-${status}`}>{STATUS_LABEL[status] ?? status}</span>;
}

/** Shows whether live updates are connected (otherwise the page polls). */
export function LiveBadge({ live }) {
  return (
    <span className={`badge ${live ? "live-on" : "live-off"}`} role="status" title={live ? "Updates appear instantly" : "Reconnecting; refreshing every few seconds meanwhile"}>
      {live ? "● Live" : "○ Reconnecting…"}
    </span>
  );
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="subtitle">{subtitle}</p>}
      </div>
      {children && <div className="page-actions">{children}</div>}
    </header>
  );
}

/** Short summary of recorded observations, e.g. "HR 112 · SpO₂ 95% · 37.4 °C · pain 6/10". */
export function formatVitals(visit) {
  const v = visit?.vitals || {};
  const parts = [
    v.heart_rate != null && `HR ${v.heart_rate}`,
    v.resp_rate != null && `RR ${v.resp_rate}`,
    v.spo2 != null && `SpO₂ ${v.spo2}%`,
    v.temperature_c != null && `${v.temperature_c} °C`,
    v.systolic_bp != null && `BP ${v.systolic_bp}`,
    v.avpu && v.avpu !== "A" && `AVPU ${v.avpu}`,
    visit?.pain_score != null && `pain ${visit.pain_score}/10`,
  ].filter(Boolean);
  return parts.join(" · ");
}

export const formatTime = (value) =>
  value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

export const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" }) : "—";
