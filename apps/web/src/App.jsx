import { useState } from "react";
import { AuthProvider, useAuth } from "./api/AuthContext";
import LoginForm from "./components/LoginForm";
import StudentRegisterForm from "./components/StudentRegisterForm";
import ChangePasswordForm from "./components/ChangePasswordForm";
import StaffApp from "./components/staff/StaffApp";
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

function SignInScreen() {
  const [tab, setTab] = useState("login");
  return (
    <div className="card">
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

function Root() {
  const { status, user } = useAuth();
  if (status === "checking") return <div className="shell"><Loading label="Restoring your session…" /></div>;
  if (status !== "signed-in") return <div className="shell"><SignInScreen /></div>;
  if (user.role === "student") return <div className="shell"><StudentScreen /></div>;
  return <StaffApp />;
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}
