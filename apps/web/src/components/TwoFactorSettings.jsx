import { useState } from "react";
import { authApi } from "../api/client";
import { useApi } from "../hooks/useApi";
import { ErrorBox, Loading } from "./ui";

/** Turn two-step sign-in (authenticator app) on or off for the signed-in staff member. */
export default function TwoFactorSettings() {
  const status = useApi(() => authApi.mfaStatus(), []);
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  async function run(call, message) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await call();
      setNotice(message);
      setSetup(null);
      setCode("");
      setPassword("");
      await status.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    setBusy(true);
    setError(null);
    try {
      setSetup(await authApi.mfaSetup());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (!status.data) return status.loading ? <Loading /> : <ErrorBox error={status.error} onRetry={status.reload} />;
  const { enabled, required } = status.data;
  return (
    <>
      <p className="small muted">
        {enabled ? "On: signing in asks for a code from your authenticator app."
          : "Off. With it on, a stolen password alone can't open your account."}
        {required && " Your role requires it."}
      </p>
      {notice && <p className="notice" role="status">{notice}</p>}
      <ErrorBox error={error} />
      {!enabled && !setup && <button type="button" className="btn" disabled={busy} onClick={start}>Set up two-step sign-in</button>}
      {setup && (
        <form onSubmit={(e) => { e.preventDefault(); run(() => authApi.mfaConfirm(code), "Two-step sign-in is on."); }}>
          <ol className="steps small">
            <li>Open an authenticator app (Google Authenticator, Microsoft Authenticator, Aegis…).</li>
            <li>Scan this code, or enter the key by hand.</li>
          </ol>
          <img src={setup.qrSvg} alt="QR code for your authenticator app" className="qr" />
          <p className="mono small break">{setup.secret}</p>
          <div className="field">
            <label htmlFor="mfa-code">Code from the app</label>
            <input id="mfa-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code}
              onChange={(e) => setCode(e.target.value)} required />
          </div>
          <button type="submit" className="btn" disabled={busy || code.length < 6}>Turn on</button>
        </form>
      )}
      {enabled && !required && (
        <form onSubmit={(e) => { e.preventDefault(); run(() => authApi.mfaDisable(password, code), "Two-step sign-in is off."); }}>
          <div className="field">
            <label htmlFor="mfa-off-password">Password</label>
            <input id="mfa-off-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="mfa-off-code">Current code</label>
            <input id="mfa-off-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code}
              onChange={(e) => setCode(e.target.value)} required />
          </div>
          <button type="submit" className="btn btn-secondary" disabled={busy}>Turn off</button>
        </form>
      )}
    </>
  );
}
