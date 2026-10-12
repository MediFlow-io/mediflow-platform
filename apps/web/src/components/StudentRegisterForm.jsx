import { useState } from "react";
import { authApi } from "../api/client";

const GENDERS = ["Male", "Female", "Other"];

const initial = {
  name: "",
  unique_id: "",
  email: "",
  password: "",
  gender: GENDERS[0],
  dob: "",
  address: "",
  department: "",
  level: "",
  phone: "",
};

export default function StudentRegisterForm({ onDone }) {
  const [form, setForm] = useState(initial);
  const [confirmPassword, setConfirmPassword] = useState("");
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

    if (form.password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      // confirm_password is a client-side check only — the serializer
      // doesn't accept it, so it's never sent.
      const result = await authApi.registerStudent(form);
      setSuccess(`Registered. Health Card No: ${result.health_card_no}.`);
      setForm(initial);
      setConfirmPassword("");
      onDone?.(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      {error && <div className="error-box">{error}</div>}
      {success && <div className="success-box">{success}</div>}

      <div className="field">
        <label htmlFor="name">Full name</label>
        <input id="name" value={form.name} onChange={update("name")} required />
      </div>

      <div className="row-2">
        <div className="field">
          <label htmlFor="unique_id">Matriculation No.</label>
          <input
            id="unique_id"
            placeholder="SEN/22/9269"
            value={form.unique_id}
            onChange={update("unique_id")}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="dob">Date of birth</label>
          <input id="dob" type="date" value={form.dob} onChange={update("dob")} required />
        </div>
      </div>
      <p className="hint" style={{ marginTop: "-10px" }}>
        Minimum age 16. Format: 2–6 letters / 2–4 digits / 3–6 digits.
      </p>

      <div className="row-2">
        <div className="field">
          <label htmlFor="gender">Gender</label>
          <select id="gender" value={form.gender} onChange={update("gender")}>
            {GENDERS.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="phone">Phone number</label>
          <input
            id="phone"
            placeholder="11 digits"
            value={form.phone}
            onChange={update("phone")}
            required
          />
        </div>
      </div>

      <div className="row-2">
        <div className="field">
          <label htmlFor="department">Department</label>
          <input
            id="department"
            placeholder="Software Engineering"
            value={form.department}
            onChange={update("department")}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="level">Level</label>
          <input
            id="level"
            placeholder="300"
            value={form.level}
            onChange={update("level")}
            required
          />
        </div>
      </div>

      <div className="field">
        <label htmlFor="address">Address</label>
        <input
          id="address"
          placeholder="Residential or campus address"
          value={form.address}
          onChange={update("address")}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={form.email}
          onChange={update("email")}
          required
        />
      </div>

      <div className="row-2">
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={form.password}
            onChange={update("password")}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="confirm_password">Confirm password</label>
          <input
            id="confirm_password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
        </div>
      </div>

      <button className="btn" type="submit" disabled={loading}>
        {loading ? "Registering…" : "Create student account"}
      </button>
    </form>
  );
}
