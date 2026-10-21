import { useEffect, useState } from "react";
import { AuthProvider, useAuth } from "./api/AuthContext";
import { onServerWaking } from "./api/client";
import { wakeServers } from "./api/wake";
import LoginForm from "./components/LoginForm";
import StudentRegisterForm from "./components/StudentRegisterForm";
import ChangePasswordForm from "./components/ChangePasswordForm";
import StaffApp from "./components/staff/StaffApp";
import Landing from "./components/landing/Landing";
import { Loading } from "./components/ui";

// Where students view their own record (apps/student-dashboard). Configurable per deployment.
const STUDENT_DASHBOARD_URL = import.meta.env.VITE_STUDENT_DASHBOARD_URL ?? "http://localhost:5174";

function Header() {
  return (
    <div className="brand">
      <span className="brand-mark" />
      <span className="brand-name">MediFlow</span>
    </div>
  );
}

// The landing page is at "/"; sign-in and registration at #signin and #register, so links can point at them.
function useHash() {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const update = () => setHash(window.location.hash);
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return hash;
}

function SignInScreen({ hash }) {
  const tab = hash === "#register" ? "student" : "login";
  const setTab = (next) => { window.location.hash = next === "student" ? "register" : "signin"; };
  useEffect(() => window.scrollTo(0, 0), []);
  return (
    <div className="card">
      <a className="back-home" href="#">← MediFlow home</a>
      <Header />
      <h1>Hospital operations sign-in</h1>
      <p className="subtitle">Use your matriculation number or staff ID to access MediFlow.</p>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "login"} className={`tab ${tab === "login" ? "active" : ""}`} onClick={() => setTab("login")}>
          Sign in
        </button>
        <button type="button" role="tab" aria-selected={tab === "student"} className={`tab ${tab === "student" ? "active" : ""}`} onClick={() => setTab("student")}>
          Student registration
        </button>
      </div>
      {tab === "login" && <LoginForm />}
      {tab === "student" && <StudentRegisterForm onDone={() => setTab("login")} />}
      <p className="hint" style={{ marginTop: 16 }}>Staff accounts are created by an administrator.</p>
    </div>
  );
}

function StudentScreen() {
  const { user, logout } = useAuth();
  return (
    <div className="card">
      <Header />
      <h1>Hello, {user.name}</h1>
      <p className="subtitle">Your health record, visits and queue position are in the student dashboard.</p>
      <a className="btn" href={STUDENT_DASHBOARD_URL}>Open student dashboard</a>
      <details style={{ margin: "20px 0" }}>
        <summary style={{ cursor: "pointer", fontSize: 13, color: "var(--slate)" }}>Change my password</summary>
        <div style={{ marginTop: 16 }}><ChangePasswordForm /></div>
      </details>
      <button type="button" className="btn-link" onClick={logout}>Sign out</button>
    </div>
  );
}

/** Shown while a request waits for a sleeping server (free hosting) to start. */
function WakeNotice() {
  const [waking, setWaking] = useState(false);
  useEffect(() => onServerWaking(setWaking), []);
  if (!waking) return null;
  return (
    <div className="wake-notice" role="status">
      <span className="wake-spinner" aria-hidden="true" />
      The server is waking up after a quiet spell. This can take up to a minute…
    </div>
  );
}

function Root() {
  const { status, user } = useAuth();
  const hash = useHash();
  if (status === "checking") return <div className="shell"><Loading label="Restoring your session…" /></div>;
  if (status !== "signed-in") {
    if (hash === "#signin" || hash === "#register") return <div className="shell"><SignInScreen hash={hash} /></div>;
    return <Landing studentDashboardUrl={STUDENT_DASHBOARD_URL} />;
  }
  if (user.role === "student") return <div className="shell"><StudentScreen /></div>;
  return <StaffApp />;
}

export default function App() {
  useEffect(() => {
    wakeServers();
    // A request found a server asleep: wake them again from the browser (see api/wake.js).
    return onServerWaking((waking) => waking && wakeServers({ again: true }));
  }, []);
  return (
    <AuthProvider>
      <Root />
      <WakeNotice />
    </AuthProvider>
  );
}
