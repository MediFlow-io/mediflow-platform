import { useEffect, useState } from "react";
import { AuthProvider, useAuth } from "./api/AuthContext";
import { onServerWaking } from "./api/client";
import { wakeServers } from "./api/wake";
import LoginForm from "./components/LoginForm";
import StaffApp from "./components/staff/StaffApp";
import Landing from "./components/landing/Landing";
import { Loading } from "./components/ui";

// The student portal (apps/student-dashboard): students register and sign in there, never here.
const STUDENT_PORTAL_URL = (import.meta.env.VITE_STUDENT_DASHBOARD_URL || "http://localhost:5174").replace(/\/$/, "");

function Header() {
  return (
    <div className="brand">
      <span className="brand-mark" />
      <span className="brand-name">MediFlow</span>
    </div>
  );
}

// "/" is the public landing page and "/login" the staff sign-in. Links from older versions used #signin.
const onLoginPage = () => window.location.pathname.replace(/\/$/, "") === "/login" || window.location.hash === "#signin";

function StaffSignIn() {
  useEffect(() => window.scrollTo(0, 0), []);
  return (
    <div className="card">
      <a className="back-home" href="/">← MediFlow home</a>
      <Header />
      <h1>Staff sign-in</h1>
      <p className="subtitle">For clinic and hospital staff. Sign in with the staff ID your administrator gave you.</p>
      <LoginForm />
      <div className="portal-switch">
        <span>Are you a student?</span>
        <a href={STUDENT_PORTAL_URL}>Go to the student portal →</a>
      </div>
    </div>
  );
}

/** A student still holding a session from before the portals were separated. */
function StudentElsewhere() {
  const { logout } = useAuth();
  return (
    <div className="card">
      <Header />
      <h1>This is the staff portal</h1>
      <p className="subtitle">Students sign in, book visits and follow the queue on the student portal.</p>
      <a className="btn" href={STUDENT_PORTAL_URL}>Go to the student portal</a>
      <button type="button" className="btn-link" style={{ marginTop: 16 }} onClick={logout}>Sign out here</button>
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
  if (status === "checking") return <div className="shell"><Loading label="Restoring your session…" /></div>;
  if (status !== "signed-in") {
    if (onLoginPage()) return <div className="shell"><StaffSignIn /></div>;
    return <Landing studentPortalUrl={STUDENT_PORTAL_URL} />;
  }
  if (user.role === "student") return <div className="shell"><StudentElsewhere /></div>;
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
