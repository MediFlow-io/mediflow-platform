import { useState } from "react";
import { mediflowApi } from "../../api/client";
import { useAuth } from "../../api/AuthContext";
import { useApi } from "../../hooks/useApi";
import { can } from "../../lib/roles";
import ChangePasswordForm from "../ChangePasswordForm";
import TwoFactorSettings from "../TwoFactorSettings";
import { PageHeader } from "../ui";
import DashboardPage from "./DashboardPage";
import PatientsPage from "./PatientsPage";
import AppointmentsPage from "./AppointmentsPage";
import NotificationsPage from "./NotificationsPage";
import PharmacyPage from "./PharmacyPage";
import QueuePage from "./QueuePage";
import StaffPage from "./StaffPage";

const PAGES = [
  { id: "dashboard", label: "Dashboard", permission: "dashboard", Component: DashboardPage },
  { id: "queue", label: "Queue", permission: "readPatients", Component: QueuePage },
  { id: "appointments", label: "Appointments", permission: "manageAppointments", Component: AppointmentsPage },
  { id: "patients", label: "Patients", permission: "readPatients", Component: PatientsPage },
  { id: "pharmacy", label: "Pharmacy", permission: "pharmacy", Component: PharmacyPage },
  { id: "staff", label: "Staff", permission: "manageStaff", Component: StaffPage },
  { id: "notifications", label: "Notifications", permission: null, Component: NotificationsPage },
  { id: "account", label: "My account", permission: null, Component: AccountPage },
];

export default function StaffApp() {
  const { user, logout } = useAuth();
  const pages = PAGES.filter((p) => p.permission === null || can(user, p.permission));
  const [current, setCurrent] = useState(pages[0].id);
  const Page = (pages.find((p) => p.id === current) ?? pages[0]).Component;
  // The unread count is a nice-to-have: if the notification service is down, the badge just stays hidden.
  const unread = useApi(() => mediflowApi.unreadNotifications(), [], { refreshMs: 20000 });
  const unreadCount = unread.data?.unread ?? 0;
  const navigate = (id) => pages.some((p) => p.id === id) && setCurrent(id);

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
              {p.id === "notifications" && unreadCount > 0 && (
                <span className="nav-count" aria-label={`${unreadCount} unread`}>{unreadCount}</span>
              )}
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
        {user.mfaSetupRequired && current !== "account" && (
          <div className="info-box" role="status">
            Your role needs two-step sign-in. <button type="button" className="btn-link" onClick={() => setCurrent("account")}>Set it up in My account</button>.
          </div>
        )}
        <Page onNavigate={navigate} onUnreadChange={unread.reload} />
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
      <section className="panel narrow">
        <h2>Two-step sign-in</h2>
        <TwoFactorSettings />
      </section>
    </>
  );
}
