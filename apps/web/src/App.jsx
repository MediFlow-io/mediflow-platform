import { useState } from "react";
import { AuthProvider, useAuth } from "./api/AuthContext";
import LoginForm from "./components/LoginForm";
import StudentRegisterForm from "./components/StudentRegisterForm";
import StaffRegisterForm from "./components/StaffRegisterForm";
import ChangePasswordForm from "./components/ChangePasswordForm";

const TABS = [
  { id: "login", label: "Sign in" },
  { id: "student", label: "Student registration" },
  { id: "staff", label: "Staff registration" },
  { id: "password", label: "Change password" },
];

function Header() {
  return (
    <div className="brand">
      <span className="brand-mark" />
      <span className="brand-name">MediFlow</span>
    </div>
  );
}

function AuthScreen() {
  const [tab, setTab] = useState("login");
  const { user, logout, isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return (
      <div className="card">
        <Header />
        <h1>Signed in</h1>
        <p className="subtitle">
          {user?.name ? `${user.name} · ${user.role}` : "Session active."}
        </p>

        <div className="success-box">
          Access token stored. You can now reach protected MediFlow services
          through the gateway.
        </div>

        <details style={{ marginBottom: 20 }}>
          <summary style={{ cursor: "pointer", fontSize: 13, color: "var(--slate)" }}>
            Change my password
          </summary>
          <div style={{ marginTop: 16 }}>
            <ChangePasswordForm />
          </div>
        </details>

        {user?.role === "Admin" && (
          <details style={{ marginBottom: 20 }}>
            <summary style={{ cursor: "pointer", fontSize: 13, color: "var(--slate)" }}>
              Register a staff member
            </summary>
            <div style={{ marginTop: 16 }}>
              <StaffRegisterForm />
            </div>
          </details>
        )}

        <button className="btn-link" onClick={logout}>
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="card">
      <Header />
      <h1>Hospital operations sign-in</h1>
      <p className="subtitle">
        Use your matriculation number or staff ID to access MediFlow.
      </p>

      <div className="tabs">
        {TABS.filter((t) => t.id !== "password").map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
            type="button"
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "login" && <LoginForm />}
      {tab === "student" && <StudentRegisterForm onDone={() => setTab("login")} />}
      {tab === "staff" && (
        <>
          <p className="hint" style={{ marginBottom: 16 }}>
            Staff registration requires an administrator to already be signed
            in. Sign in as an admin first, then use "Register staff member"
            from the account panel.
          </p>
        </>
      )}
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <div className="shell">
        <AuthScreen />
      </div>
    </AuthProvider>
  );
}
