import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { Empty, ErrorBox, Loading, PageHeader } from "../ui";

export const timeAgo = (value, now = Date.now()) => {
  const minutes = Math.round((now - new Date(value).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} h ago`;
  return new Date(value).toLocaleDateString([], { day: "numeric", month: "short" });
};

/** Served by the Flask notification service. `onNavigate` opens the page a notification points to. */
export default function NotificationsPage({ onNavigate, onUnreadChange }) {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const { data, error, loading, reload } = useApi(() => mediflowApi.notifications({ unread: unreadOnly ? 1 : undefined }),
    [unreadOnly], { refreshMs: 20000 });
  const [actionError, setActionError] = useState(null);

  async function run(call) {
    setActionError(null);
    try {
      await call();
      await reload();
      onUnreadChange?.();
    } catch (err) {
      setActionError(err);
    }
  }

  const open = (n) => run(async () => {
    if (!n.readAt) await mediflowApi.markNotificationRead(n.id);
    if (n.link && n.link !== "home") onNavigate?.(n.link);
  });

  return (
    <>
      <PageHeader title="Notifications" subtitle="Updates about appointments and the queue.">
        <label className="inline-check">
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} /> Unread only
        </label>
        <button type="button" className="btn btn-secondary" disabled={!data?.unread}
          onClick={() => run(() => mediflowApi.markAllNotificationsRead())}>
          Mark all read
        </button>
      </PageHeader>
      <ErrorBox error={error || actionError} onRetry={reload} />
      {!data && loading && <Loading />}
      {data && data.results.length === 0 && <Empty>{unreadOnly ? "Nothing unread." : "No notifications yet."}</Empty>}
      {data && data.results.length > 0 && (
        <ul className="panel notification-list" aria-label="Notifications">
          {data.results.map((n) => (
            <li key={n.id}>
              <button type="button" className={`notification ${n.readAt ? "" : "unread"}`} onClick={() => open(n)}>
                <span className="notification-title">{n.title}</span>
                <span className="notification-body">{n.body}</span>
                <span className="small muted">{timeAgo(n.createdAt)}{n.readAt ? "" : " · new"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <DeliveryPreferences />
    </>
  );
}

function DeliveryPreferences() {
  const loaded = useApi(() => mediflowApi.notificationPreferences(), []);
  const [changed, setChanged] = useState(null);
  const [saving, setSaving] = useState(false);
  const prefs = changed ?? loaded.data;
  if (!prefs) return null;
  async function toggle(channel) {
    setChanged({ ...prefs, [channel]: !prefs[channel] }); // show the change at once; undo it if saving fails
    setSaving(true);
    try {
      setChanged(await mediflowApi.setNotificationPreferences({ [channel]: !prefs[channel] }));
    } catch {
      setChanged(prefs);
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="panel narrow">
      <h2>Also tell me by</h2>
      {[["email", "Email"], ["sms", "SMS"]].map(([channel, label]) => (
        <label key={channel} className="inline-check">
          <input type="checkbox" checked={prefs[channel]} disabled={saving} onChange={() => toggle(channel)} /> {label}
        </label>
      ))}
      <p className="small muted">Emails and texts only say there is a new notification; the details stay here.</p>
    </section>
  );
}
