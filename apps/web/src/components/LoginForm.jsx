import { useState } from "react";
import { useAuth } from "../api/AuthContext";

export default function LoginForm({ onSuccess }) {
  const { login, verifyMfa } = useAuth();
  const [mfaToken, setMfaToken] = useState(null);
  const [code, setCode] = useState("");
  const [uniqueId, setUniqueId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mfaToken) {
        await verifyMfa(mfaToken, code);
      } else {
        const result = await login(uniqueId, password);
        if (result.mfaRequired) {
          setMfaToken(result.mfaToken);
          return;
        }
      }
      onSuccess?.();
    } catch (err) {
      if (err.status === 401 && mfaToken && /took too long/.test(err.message)) setMfaToken(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (mfaToken) {
    return (
      <form onSubmit={handleSubmit}>
        {error && <div className="error-box">{error}</div>}
        <p className="small">Enter the 6-digit code from your authenticator app.</p>
        <div className="field">
          <label htmlFor="mfa_code">Authentication code</label>
          <input id="mfa_code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus
            value={code} onChange={(e) => setCode(e.target.value)} required />
        </div>
        <button className="btn" type="submit" disabled={loading || code.length < 6}>{loading ? "Checking…" : "Verify"}</button>
        <button className="btn-link small" type="button" onClick={() => { setMfaToken(null); setCode(""); setError(null); }}>Back</button>
      </form>
    );
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
