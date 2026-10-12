import { useState } from "react";
import { useAuth } from "../api/AuthContext";

export default function LoginForm({ onSuccess }) {
  const { login } = useAuth();
  const [uniqueId, setUniqueId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(uniqueId, password);
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      {error && <div className="error-box">{error}</div>}

      <div className="field">
        <label htmlFor="unique_id">Matric No. or Staff ID</label>
        <input
          id="unique_id"
          type="text"
          placeholder="SEN/22/9269"
          value={uniqueId}
          onChange={(e) => setUniqueId(e.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>

      <button className="btn" type="submit" disabled={loading}>
        {loading ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
