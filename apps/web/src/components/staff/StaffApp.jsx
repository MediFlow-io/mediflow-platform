import { useState } from "react";
import { useAuth } from "../../api/AuthContext";
import { can } from "../../lib/roles";
import ChangePasswordForm from "../ChangePasswordForm";
import { PageHeader } from "../ui";
import DashboardPage from "./DashboardPage";
import PatientsPage from "./PatientsPage";
import QueuePage from "./QueuePage";
import StaffPage from "./StaffPage";

const PAGES = [
  { id: "dashboard", label: "Dashboard", permission: "dashboard", Component: DashboardPage },
  { id: "queue", label: "Queue", permission: "readPatients", Component: QueuePage },
  { id: "patients", label: "Patients", permission: "readPatients", Component: PatientsPage },
  { id: "staff", label: "Staff", permission: "manageStaff", Component: StaffPage },
  { id: "account", label: "My account", permission: null, Component: AccountPage },
];

export default function StaffApp() {
  const { user, logout } = useAuth();
  const pages = PAGES.filter((p) => p.permission === null || can(user, p.permission));
  const [current, setCurrent] = useState(pages[0].id);
  const Page = (pages.find((p) => p.id === current) ?? pages[0]).Component;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" />
          <span className="brand-name">MediFlow</span>
        </div>
        <nav aria-label="Main">
          {pages.map((p) => (
            <button key={p.id} type="button" className={`nav-item ${current === p.id ? "active" : ""}`}
              aria-current={current === p.id ? "page" : undefined} onClick={() => setCurrent(p.id)}>
              {p.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="small"><strong>{user.name}</strong></div>
          <div className="small muted">{user.role}</div>
          <button type="button" className="btn-link" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="content">
        <Page />
      </main>
    </div>
  );
}

function AccountPage() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader title="My account" subtitle={`${user.name} · ${user.unique_id} · ${user.role}`} />
      <section className="panel narrow">
        <h2>Change password</h2>
        <ChangePasswordForm />
      </section>
    </>
  );
}
