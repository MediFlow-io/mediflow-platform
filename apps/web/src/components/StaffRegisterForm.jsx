import { useState } from "react";
import { authApi } from "../api/client";

const ROLES = ["Admin", "Doctor", "Nurse", "Reception", "Lab", "Pharmacy", "IT"];

const initial = {
  name: "",
  unique_id: "",
  email: "",
  password: "",
  role: ROLES[1],
};

export default function StaffRegisterForm({ onCreated }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [loading, setLoading] = useState(false);

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const result = await authApi.registerStaff(form);
      setSuccess(
        `${result.role} account created for ${result.profile?.name ?? form.name} (${result.unique_id}).`
      );
      setForm(initial);
      onCreated?.(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <p className="hint" style={{ marginBottom: "16px" }}>
        Creates a staff account. Share the temporary password securely and ask
        them to change it after their first sign-in.
      </p>

      {error && <div className="error-box">{error}</div>}
      {success && <div className="success-box">{success}</div>}

      <div className="field">
        <label htmlFor="s_name">Full name</label>
        <input id="s_name" value={form.name} onChange={update("name")} required />
      </div>

      <div className="row-2">
        <div className="field">
          <label htmlFor="s_id">Staff ID</label>
          <input
            id="s_id"
            placeholder="2018002 or DOC/001"
            value={form.unique_id}
            onChange={update("unique_id")}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="s_role">Role</label>
          <select id="s_role" value={form.role} onChange={update("role")}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="field">
        <label htmlFor="s_email">Email</label>
        <input id="s_email" type="email" value={form.email} onChange={update("email")} />
      </div>

      <div className="field">
        <label htmlFor="s_password">Temporary password</label>
        <input
          id="s_password"
          type="password"
          value={form.password}
          onChange={update("password")}
          required
          minLength={8}
        />
        <p className="hint">At least 8 characters, not a common or all-numeric password.</p>
      </div>

      <button className="btn" type="submit" disabled={loading}>
        {loading ? "Creating…" : "Register staff member"}
      </button>
    </form>
  );
}
