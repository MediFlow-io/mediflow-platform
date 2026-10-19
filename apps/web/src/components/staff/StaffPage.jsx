import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useAuth } from "../../api/AuthContext";
import { useApi } from "../../hooks/useApi";
import { STAFF_ROLES } from "../../lib/roles";
import StaffRegisterForm from "../StaffRegisterForm";
import { Empty, ErrorBox, Loading, PageHeader, formatDate } from "../ui";

/** Admin-only: list, create, change role, (de)activate and reset passwords for accounts. */
export default function StaffPage() {
  const { user } = useAuth();
  const [role, setRole] = useState("");
  const [active, setActive] = useState("true");
  const [adding, setAdding] = useState(false);
  const users = useApi(() => mediflowApi.users({ role, active }), [role, active]);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  async function update(target, payload, message) {
    setBusy(target.id);
    setError(null);
    setNotice(null);
    try {
      await mediflowApi.updateUser(target.id, payload);
      setNotice(message);
      await users.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  async function resetMfa(target) {
    if (!window.confirm(`Reset two-step sign-in for ${target.username}? Use this when they lost their phone; they can sign in with their password and set it up again.`)) return;
    setBusy(target.id);
    setError(null);
    setNotice(null);
    try {
      const { reset } = await mediflowApi.resetMfa(target.id);
      setNotice(reset ? `Two-step sign-in reset for ${target.username}.` : `${target.username} didn't have two-step sign-in on.`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  function resetPassword(target) {
    const password = window.prompt(`New temporary password for ${target.username} (at least 8 characters):`);
    if (password) update(target, { password }, `Password reset for ${target.username}. Share it securely.`);
  }

  return (
    <>
      <PageHeader title="Staff" subtitle="Accounts are deactivated, never deleted, so the audit history stays complete.">
        <button type="button" className="btn" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add staff member"}</button>
      </PageHeader>
      {adding && (
        <section className="panel narrow">
          <StaffRegisterForm onCreated={() => users.reload()} />
        </section>
      )}
      <ErrorBox error={error} />
      {notice && <div className="success-box" role="status">{notice}</div>}

      <section className="panel">
        <div className="filters">
          <select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">All roles</option>
            {[...STAFF_ROLES, "student"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select aria-label="Status" value={active} onChange={(e) => setActive(e.target.value)}>
            <option value="true">Active</option>
            <option value="false">Deactivated</option>
            <option value="">All</option>
          </select>
        </div>
        <ErrorBox error={users.error} onRetry={users.reload} />
        {!users.data && users.loading && <Loading />}
        {users.data && users.data.length === 0 && <Empty>No accounts match.</Empty>}
        {users.data && users.data.length > 0 && (
          <table className="table">
            <thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Last sign-in</th><th /></tr></thead>
            <tbody>
              {users.data.map((u) => {
                const self = u.id === user.id;
                return (
                  <tr key={u.id} className={u.is_active ? undefined : "row-muted"}>
                    <td>{u.display_name || "—"}</td>
                    <td className="mono">{u.username}</td>
                    <td>
                      <select aria-label={`Role for ${u.username}`} value={u.role} disabled={self || busy === u.id}
                        onChange={(e) => update(u, { role: e.target.value }, `${u.username} is now ${e.target.value}.`)}>
                        {[...STAFF_ROLES, "student"].map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </td>
                    <td>{u.last_login ? formatDate(u.last_login) : "never"}</td>
                    <td className="actions">
                      <button type="button" className="btn btn-small btn-secondary" disabled={busy === u.id} onClick={() => resetPassword(u)}>
                        Reset password
                      </button>
                      {u.role !== "student" && (
                        <button type="button" className="btn btn-small btn-secondary" disabled={busy === u.id} onClick={() => resetMfa(u)}>
                          Reset 2FA
                        </button>
                      )}
                      {!self && (
                        <button type="button" className={`btn btn-small ${u.is_active ? "btn-danger" : ""}`} disabled={busy === u.id}
                          onClick={() => update(u, { is_active: !u.is_active }, `${u.username} ${u.is_active ? "deactivated and signed out" : "reactivated"}.`)}>
                          {u.is_active ? "Deactivate" : "Reactivate"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
