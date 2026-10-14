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

export const formatTime = (value) =>
  value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

export const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" }) : "—";
