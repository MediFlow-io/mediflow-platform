import { useCallback, useEffect, useState } from "react";
import { LayoutGrid, CalendarDays, ClipboardList, Syringe, Pill, Bell, Check, ShieldAlert, Phone, LogOut, Info, Plus, X } from "lucide-react";
import {
  cancelAppointment, getDepartments, getMe, getMyAppointments, getMyHealth, getMyQueue, getNotificationPreferences,
  getNotifications, isSignedIn, setNotificationPreferences,
  markAllNotificationsRead, markNotificationRead, requestAppointment, signIn, signOut,
} from "./api";

// Mediflow palette
const C = {
  ink: "#0E2140",
  cobalt: "#2F5BFF",
  mint: "#2BC3A0",
  coral: "#FF6B6B",
  mist: "#EDF2F9",
  line: "#D9E2EF",
};

// Stages a visit really goes through in MediFlow (see the core API's visit lifecycle).
const journey = ["Checked in", "Called", "With clinician", "Done"];
const stageOf = { waiting: 0, called: 1, in_progress: 2 };
const STATUS_LABEL = { waiting: "Waiting", called: "Called", in_progress: "With clinician", completed: "Completed", cancelled: "Cancelled" };
const REFRESH_MS = 20000;

const fmt = (d) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
const time = (d) => new Date(d).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

const nav = [
  { id: "home", label: "Today", icon: LayoutGrid },
  { id: "appts", label: "Appointments", icon: CalendarDays },
  { id: "history", label: "Visit history", icon: ClipboardList },
  { id: "vaccines", label: "Vaccines", icon: Syringe },
  { id: "meds", label: "Medications", icon: Pill },
  { id: "notifications", label: "Notifications", icon: Bell },
];
// Where a notification's `link` takes you.
const LINK_TAB = { home: "home", appointments: "appts" };

function ago(d) {
  const minutes = Math.round((Date.now() - new Date(d).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} h ago`;
  return fmt(d);
}

function NotificationItem({ n, onOpen, compact }) {
  return (
    <button onClick={() => onOpen(n)} className={`w-full text-left rounded-2xl ${compact ? "p-3" : "p-4"} flex gap-3`}
      style={{ background: n.readAt ? "#fff" : C.mist, border: `1px solid ${n.readAt ? C.line : "transparent"}` }}>
      <span className="mt-1.5 w-2 h-2 rounded-full shrink-0" style={{ background: n.readAt ? "transparent" : C.cobalt }} aria-hidden="true" />
      <span className="grid gap-0.5">
        <span className="text-sm font-semibold" style={{ color: C.ink }}>{n.title}</span>
        <span className="text-sm">{n.body}</span>
        <span className="text-xs" style={{ color: "#5B6F8F" }}>{ago(n.createdAt)}{n.readAt ? "" : " · new"}</span>
      </span>
    </button>
  );
}

function DeliveryPreferences() {
  const [prefs, setPrefs] = useState(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    getNotificationPreferences().then(setPrefs, () => setPrefs(null));
  }, []);
  if (!prefs) return null;
  async function toggle(channel) {
    const before = prefs;
    setPrefs({ ...prefs, [channel]: !prefs[channel] }); // show the change at once; undo it if saving fails
    setSaving(true);
    try {
      setPrefs(await setNotificationPreferences({ [channel]: !before[channel] }));
    } catch {
      setPrefs(before);
    } finally {
      setSaving(false);
    }
  }
  return (
    <fieldset className="mt-5 pt-4 grid gap-2" style={{ borderTop: `1px solid ${C.line}` }}>
      <legend className="text-sm font-semibold" style={{ color: C.ink }}>Also tell me by</legend>
      {[["email", "Email"], ["sms", "SMS"]].map(([channel, label]) => (
        <label key={channel} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={prefs[channel]} disabled={saving} onChange={() => toggle(channel)} /> {label}
        </label>
      ))}
      <p className="text-xs" style={{ color: "#5B6F8F" }}>
        Emails and texts only say you have a new notification. The details stay in this app.
      </p>
    </fieldset>
  );
}

function Notifications({ data, failed, onOpen, onReadAll }) {
  return (
    <Card title="Notifications" right={data?.unread > 0 && (
      <button onClick={onReadAll} className="text-sm font-medium" style={{ color: C.cobalt }}>Mark all read</button>
    )}>
      {failed && <Note>Notifications can't be loaded right now. Your queue position and appointments are still up to date.</Note>}
      {!failed && !data && <p className="text-sm" role="status">Loading…</p>}
      {data && data.results.length === 0 && <p className="text-sm">No notifications yet. We'll tell you here when you're called or an appointment changes.</p>}
      {data && data.results.length > 0 && (
        <ul className="grid gap-2" aria-label="Notifications">
          {data.results.map((n) => <li key={n.id}><NotificationItem n={n} onOpen={onOpen} /></li>)}
        </ul>
      )}
      <DeliveryPreferences />
    </Card>
  );
}

function Logo({ light }) {
  return (
    <div className="flex items-center gap-2">
      <svg width="34" height="22" viewBox="0 0 34 22" fill="none" aria-hidden="true">
        <path d="M1 12 C6 12 6 3 11 3 S16 19 21 19 S26 11 33 11" stroke={C.mint} strokeWidth="3" strokeLinecap="round" />
      </svg>
      <span className="text-xl font-bold tracking-tight" style={{ color: light ? "#fff" : C.ink }}>
        Medi<span style={{ color: C.mint }}>flow</span>
      </span>
    </div>
  );
}

function Card({ title, right, children, className = "" }) {
  return (
    <section className={`bg-white rounded-3xl p-6 ${className}`} style={{ border: `1px solid ${C.line}` }}>
      {(title || right) && (
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold" style={{ color: C.ink }}>{title}</h2>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

function Note({ children }) {
  return (
    <div className="flex gap-3 rounded-2xl p-4 text-sm" style={{ background: C.mist, color: "#2A3B57" }}>
      <Info size={18} className="shrink-0 mt-0.5" color={C.cobalt} />
      <div>{children}</div>
    </div>
  );
}

function CareJourney({ visit, estimate }) {
  const stage = visit ? stageOf[visit.status] : -1;
  let headline = "No active visit";
  let detail = "Walk in to the health centre and reception will check you in. You can then follow your place here.";
  if (visit?.status === "waiting") {
    headline = "You're in the queue";
    detail = visit.patientsAhead === 0
      ? `You're next in ${visit.department}. Please stay nearby.`
      : `${visit.patientsAhead} ${visit.patientsAhead === 1 ? "person is" : "people are"} ahead of you in ${visit.department}. More urgent cases are seen first.`;
    if (visit.patientsAhead > 0 && estimate > 0) detail += ` Roughly ${estimate} min, but this can change.`;
  } else if (visit?.status === "called") {
    headline = "You've been called";
    detail = `Please go to ${visit.department} now.`;
  } else if (visit?.status === "in_progress") {
    headline = "You're with the clinician now";
    detail = `${visit.department} · since ${time(visit.startedAt)}`;
  }

  return (
    <div className="rounded-3xl p-6 md:p-8 text-white" style={{ background: C.ink }} aria-live="polite">
      <p className="text-sm" style={{ color: "#9DB2D6" }}>
        Your visit to the clinic today{visit ? ` · checked in ${time(visit.checkedInAt)}` : ""}
      </p>
      <h2 className="text-2xl md:text-3xl font-bold mt-1">{headline}</h2>
      <p className="text-sm mt-2" style={{ color: "#C8D6EE" }}>{detail}</p>
      {stage >= 0 && (
        <div className="mt-8 flex items-center">
          {journey.map((step, i) => {
            const done = i < stage, now = i === stage;
            return (
              <div key={step} className="flex items-center flex-1 last:flex-none">
                <div className="flex flex-col items-center gap-2 w-14 md:w-20">
                  <div
                    className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold"
                    style={{
                      background: done ? C.mint : now ? "#fff" : "transparent",
                      color: done ? C.ink : now ? C.cobalt : "#6C84AD",
                      border: done ? "none" : `2px solid ${now ? "#fff" : "#38537F"}`,
                      boxShadow: now ? `0 0 0 6px ${C.cobalt}55` : "none",
                    }}
                  >
                    {done ? <Check size={18} /> : i + 1}
                  </div>
                  <span className="text-[11px] md:text-xs text-center" style={{ color: now ? "#fff" : "#9DB2D6" }}>{step}</span>
                </div>
                {i < journey.length - 1 && <div className="flex-1 h-0.5 -mt-6" style={{ background: done ? C.mint : "#38537F" }} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const splitList = (text) => (text || "").split(/[,;\n]/).map((s) => s.trim()).filter(Boolean);

function LatestVitals({ vitals }) {
  const items = vitals ? [
    ["Heart rate", vitals.heartRate, "bpm"],
    ["Temperature", vitals.temperatureC, "°C"],
    ["Oxygen (SpO₂)", vitals.spo2, "%"],
    ["Breathing rate", vitals.respRate, "/min"],
    ["Blood pressure (systolic)", vitals.systolicBp, "mmHg"],
    ["Pain", vitals.painScore, "/10"],
  ].filter(([, value]) => value !== null && value !== undefined) : [];
  return (
    <Card title="Last recorded vitals" right={vitals && <span className="text-sm" style={{ color: "#5B6F8F" }}>{fmt(vitals.recordedAt)}</span>}>
      {items.length === 0 ? (
        <p className="text-sm" style={{ color: "#5B6F8F" }}>No vital signs recorded yet. The nurse records them when you check in.</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {items.map(([label, value, unit]) => (
            <div key={label} className="rounded-2xl p-4" style={{ background: C.mist }}>
              <div className="text-xs" style={{ color: "#5B6F8F" }}>{label}</div>
              <div className="text-2xl font-bold" style={{ color: C.ink }}>{value}<span className="text-sm font-medium ml-1">{unit}</span></div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function Home({ health, go, estimate }) {
  const { patient, activeVisit, visits, latestVitals } = health;
  const allergies = splitList(patient?.allergies);
  const last = visits.find((v) => v.status === "completed");
  return (
    <div className="grid gap-5">
      <CareJourney visit={activeVisit} estimate={estimate} />
      <LatestVitals vitals={latestVitals} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Your visits" right={<button onClick={() => go("history")} className="text-sm font-semibold" style={{ color: C.cobalt }}>See all</button>} className="lg:col-span-2">
          <div className="flex items-center gap-6">
            <div>
              <div className="text-3xl font-bold" style={{ color: C.ink }}>{visits.length}</div>
              <div className="text-sm" style={{ color: "#5B6F8F" }}>on record</div>
            </div>
            <div className="text-sm" style={{ color: "#5B6F8F" }}>
              {last ? <>Last completed visit: <strong style={{ color: C.ink }}>{fmt(last.checkedInAt)}</strong>, {last.department}{last.clinician ? ` with ${last.clinician}` : ""}.</> : "No completed visits yet."}
            </div>
          </div>
        </Card>
        <Card title="Safety card">
          {allergies.length > 0 ? (
            <div className="flex flex-wrap gap-2 mb-4">
              {allergies.map((a) => (
                <span key={a} className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium" style={{ background: "#FFE9E9", color: "#B23A3A" }}>
                  <ShieldAlert size={14} /> {a}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm mb-4" style={{ color: "#5B6F8F" }}>No allergies recorded. Tell the clinic if you have any.</p>
          )}
          {patient?.nextOfKin ? (
            <div className="text-sm flex items-center gap-2" style={{ color: C.ink }}><Phone size={14} /> {patient.nextOfKin}{patient.nextOfKinPhone ? `, ${patient.nextOfKinPhone}` : ""}</div>
          ) : (
            <p className="text-sm" style={{ color: "#5B6F8F" }}>No emergency contact recorded.</p>
          )}
        </Card>
      </div>
    </div>
  );
}

function History({ visits }) {
  return (
    <Card title="Visit history">
      {visits.length === 0 ? <p className="text-sm">No visits on record yet.</p> : (
        <ol className="grid gap-6 ml-2" style={{ borderLeft: `2px solid ${C.line}` }}>
          {visits.map((v) => (
            <li key={v.visitNumber} className="pl-5 relative">
              <span className="absolute w-3 h-3 rounded-full top-1.5" style={{ left: -7, background: v.status === "cancelled" ? C.coral : C.mint }} />
              <div className="text-sm" style={{ color: "#5B6F8F" }}>{fmt(v.checkedInAt)} · {time(v.checkedInAt)}{v.clinician ? ` · ${v.clinician}` : ""}</div>
              <div className="font-semibold" style={{ color: C.ink }}>{v.department}</div>
              <p className="text-sm max-w-xl mt-1">{STATUS_LABEL[v.status] ?? v.status}</p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

const APPT_STYLE = {
  requested: ["Waiting for the clinic", { background: "#FFF1D6", color: "#8A5B00" }],
  confirmed: ["Confirmed", { background: "#DDF6EF", color: "#137A62" }],
  declined: ["Declined", { background: "#FFE9E9", color: "#B23A3A" }],
  cancelled: ["Cancelled", { background: C.mist, color: "#5B6F8F" }],
  checked_in: ["Checked in", { background: "#E3EAFF", color: C.cobalt }],
};

function Appointments({ data, reload }) {
  const [open, setOpen] = useState(false);
  const [depts, setDepts] = useState([]);
  const [f, setF] = useState({ department: "", date: "", time: "", reason: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const inp = "mt-1 w-full rounded-xl px-3 py-2 bg-white";
  const border = { border: `1px solid ${C.line}` };

  useEffect(() => {
    if (open && depts.length === 0) getDepartments().then((d) => setDepts(d.filter((x) => x.active)), () => {});
  }, [open, depts.length]);

  if (!data) return <Card title="Appointments"><p className="text-sm">Loading…</p></Card>;
  if (!data.linked) {
    return <Card title="Appointments"><Note>Booking needs your account linked to your health record. Ask reception to link your matric number, then come back here.</Note></Card>;
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await requestAppointment({ ...f, department: Number(f.department) });
      setF({ department: "", date: "", time: "", reason: "" });
      setOpen(false);
      reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancel(a) {
    if (!window.confirm(`Cancel your ${a.department_name} appointment on ${fmt(a.scheduled_for)} at ${a.time}?`)) return;
    try {
      await cancelAppointment(a.id);
      reload();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <Card
      title="Appointments"
      right={
        <button onClick={() => setOpen(!open)} className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold text-white" style={{ background: C.cobalt }}>
          {open ? <X size={16} /> : <Plus size={16} />} {open ? "Close" : "Request a slot"}
        </button>
      }
    >
      <p className="text-sm mb-4" style={{ color: "#5B6F8F" }}>
        The clinic takes appointments {data.schedule}. The clinic confirms each request.
        {data.holidays?.length > 0 && <> Closed on {data.holidays.slice(0, 3).map((h) => `${fmt(h.date)} (${h.name})`).join(", ")}.</>}
      </p>
      {error && <div role="alert" className="rounded-xl p-3 mb-4 text-sm" style={{ background: "#FFE9E9", color: "#B23A3A" }}>{error}</div>}
      {open && (
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-4 p-4 rounded-2xl mb-5" style={{ background: C.mist }}>
          <label className="text-sm md:col-span-2">Department
            <select className={inp} style={border} value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} required>
              <option value="">Choose…</option>
              {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
          <label className="text-sm">Date<input type="date" className={inp} style={border} value={f.date} min={new Date().toLocaleDateString("en-CA")} onChange={(e) => setF({ ...f, date: e.target.value })} required /></label>
          <label className="text-sm">Time<input type="time" step="900" className={inp} style={border} value={f.time} onChange={(e) => setF({ ...f, time: e.target.value })} required /></label>
          <label className="text-sm md:col-span-4">Reason<input className={inp} style={border} maxLength={300} placeholder="e.g. Persistent cough" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></label>
          <button disabled={busy} className="md:col-span-4 rounded-full py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ background: C.ink }}>{busy ? "Sending…" : "Send request"}</button>
        </form>
      )}
      {data.appointments.length === 0 && <p className="text-sm">No appointments yet. Select Request a slot to ask for one.</p>}
      <ul>
        {data.appointments.map((a) => {
          const [label, style] = APPT_STYLE[a.status] ?? [a.status, {}];
          return (
            <li key={a.id} className="py-3 flex items-center justify-between gap-3" style={{ borderTop: `1px solid ${C.line}` }}>
              <div>
                <div className="font-semibold" style={{ color: C.ink }}>{a.reason || a.department_name}</div>
                <div className="text-sm" style={{ color: "#5B6F8F" }}>{fmt(a.scheduled_for)}, {a.time} · {a.department_name} · {a.reference}</div>
                {a.staff_note && <div className="text-sm mt-1" style={{ color: C.ink }}>Clinic: {a.staff_note}</div>}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold rounded-full px-3 py-1 whitespace-nowrap" style={style}>{label}</span>
                {(a.status === "requested" || a.status === "confirmed") && (
                  <button aria-label={`Cancel appointment ${a.reference}`} onClick={() => cancel(a)}><X size={16} color="#8A9BB8" /></button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function NotAvailable({ title, children }) {
  return <Card title={title}><Note>{children}</Note></Card>;
}

function SignIn({ onSignedIn }) {
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const inp = "mt-1 w-full rounded-xl px-3 py-2 bg-white";

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(id.trim(), password);
      onSignedIn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-5" style={{ background: C.mist }}>
      <form onSubmit={submit} className="bg-white rounded-3xl p-8 w-full max-w-sm grid gap-4" style={{ border: `1px solid ${C.line}` }}>
        <Logo />
        <div>
          <h1 className="text-2xl font-bold" style={{ color: C.ink, fontFamily: "Georgia, serif" }}>Student health</h1>
          <p className="text-sm" style={{ color: "#5B6F8F" }}>Sign in with your matriculation number.</p>
        </div>
        {error && <div role="alert" className="rounded-xl p-3 text-sm" style={{ background: "#FFE9E9", color: "#B23A3A" }}>{error}</div>}
        <label className="text-sm">Matric number
          <input className={inp} style={{ border: `1px solid ${C.line}` }} value={id} onChange={(e) => setId(e.target.value)} required autoComplete="username" />
        </label>
        <label className="text-sm">Password
          <input type="password" className={inp} style={{ border: `1px solid ${C.line}` }} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        </label>
        <button disabled={busy} className="rounded-full py-2.5 text-sm font-semibold text-white disabled:opacity-50" style={{ background: C.ink }}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

function Dashboard({ onSignedOut }) {
  const [tab, setTab] = useState("home");
  const [me, setMe] = useState(null);
  const [health, setHealth] = useState(null);
  const [appts, setAppts] = useState(null);
  const [error, setError] = useState(null);
  const [showNotices, setShowNotices] = useState(false);
  const [notes, setNotes] = useState(null);
  const [notesFailed, setNotesFailed] = useState(false);
  const [queueInfo, setQueueInfo] = useState(null);

  // Separate from the record: if the notification service is down, the rest of the page still works.
  const loadNotes = useCallback(
    () => getNotifications().then((data) => { setNotes(data); setNotesFailed(false); }, () => setNotesFailed(true)),
    [],
  );

  // State is only set in promise callbacks, after the request settles.
  const load = useCallback(
    () =>
      Promise.all([getMe(), getMyHealth(), getMyAppointments()]).then(
        ([profile, record, appointments]) => {
          setMe(profile);
          setHealth(record);
          setAppts(appointments);
          setError(null);
        },
        (err) => (err.status === 401 ? onSignedOut() : setError(err.message)),
      ),
    [onSignedOut],
  );

  useEffect(() => {
    // The estimate is optional: without it the card still shows the number of people ahead.
    const loadQueue = () => getMyQueue().then(setQueueInfo, () => setQueueInfo(null));
    const refresh = () => { load(); loadNotes(); loadQueue(); };
    const first = setTimeout(refresh, 0);
    const timer = setInterval(refresh, REFRESH_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [load, loadNotes]);

  async function logout() {
    await signOut();
    onSignedOut();
  }

  const unread = notes?.unread ?? 0;

  async function openNote(n) {
    setShowNotices(false);
    if (!n.readAt) await markNotificationRead(n.id).catch(() => {});
    if (LINK_TAB[n.link]) setTab(LINK_TAB[n.link]);
    loadNotes();
  }

  async function readAll() {
    await markAllNotificationsRead().catch(() => {});
    loadNotes();
  }

  return (
    <div className="min-h-screen md:flex" style={{ background: C.mist, color: "#2A3B57", fontFamily: "'Avenir Next', 'Segoe UI', system-ui, sans-serif" }}>
      <aside className="md:w-64 md:min-h-screen p-5 flex md:flex-col gap-6 items-center md:items-stretch justify-between md:justify-start" style={{ background: C.ink }}>
        <Logo light />
        <nav className="flex md:flex-col gap-1 overflow-x-auto">
          {nav.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              aria-current={tab === id ? "page" : undefined}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap"
              style={{ background: tab === id ? C.cobalt : "transparent", color: tab === id ? "#fff" : "#9DB2D6" }}
            >
              <Icon size={18} /> <span className="hidden md:inline">{label}</span>
            </button>
          ))}
        </nav>
        <button onClick={logout} className="md:mt-auto flex items-center gap-2 px-3 py-2 text-sm" style={{ color: "#9DB2D6" }}>
          <LogOut size={16} /> <span className="hidden md:inline">Sign out</span>
        </button>
      </aside>

      <div className="flex-1 p-5 md:p-8 max-w-5xl">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold" style={{ color: C.ink, fontFamily: "Georgia, serif" }}>
              Hello{me ? `, ${(me.name || "").split(" ")[0]}` : ""}
            </h1>
            <p className="text-sm" style={{ color: "#5B6F8F" }}>
              {me?.unique_id}{health?.patient ? ` · Hospital no. ${health.patient.hospitalNumber}` : ""}
            </p>
          </div>
          <div className="relative">
            <button aria-label={`Notifications (${unread} unread)`} aria-expanded={showNotices} onClick={() => setShowNotices(!showNotices)} className="relative w-11 h-11 rounded-full bg-white flex items-center justify-center" style={{ border: `1px solid ${C.line}` }}>
              <Bell size={18} color={C.ink} />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full text-[10px] text-white flex items-center justify-center" style={{ background: C.coral }}>{unread > 9 ? "9+" : unread}</span>
              )}
            </button>
            {showNotices && (
              <div className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2.5rem)] bg-white rounded-2xl p-3 grid gap-2 z-10 shadow-lg" style={{ border: `1px solid ${C.line}` }}>
                {notesFailed && <div className="text-sm p-3">Notifications can't be loaded right now.</div>}
                {!notesFailed && (notes?.results.length
                  ? notes.results.slice(0, 5).map((n) => <NotificationItem key={n.id} n={n} onOpen={openNote} compact />)
                  : <div className="text-sm p-3">No notifications yet.</div>)}
                <button onClick={() => { setShowNotices(false); setTab("notifications"); }} className="text-sm font-medium p-2" style={{ color: C.cobalt }}>
                  See all notifications
                </button>
              </div>
            )}
          </div>
        </header>

        {error && <div role="alert" className="rounded-2xl p-4 mb-5 text-sm" style={{ background: "#FFE9E9", color: "#B23A3A" }}>{error} <button className="underline ml-2" onClick={load}>Try again</button></div>}
        {!health && !error && <p className="text-sm" role="status">Loading your record…</p>}

        {health && !health.linked && (
          <div className="mb-5">
            <Note>
              Your account isn't linked to a health record yet. At your next visit, ask reception to link matric number <strong>{me?.unique_id}</strong>.
              Then your visits and queue position will appear here.
            </Note>
          </div>
        )}

        {health && tab === "home" && <Home health={health} go={setTab} estimate={queueInfo?.estimatedWaitMinutes} />}
        {health && tab === "history" && <History visits={health.visits} />}
        {tab === "appts" && <Appointments data={appts} reload={load} />}
        {tab === "vaccines" && <NotAvailable title="Vaccines">Vaccination records aren't kept in MediFlow yet. Ask the health centre for your immunisation card.</NotAvailable>}
        {tab === "notifications" && <Notifications data={notes} failed={notesFailed} onOpen={openNote} onReadAll={readAll} />}
        {tab === "meds" && <NotAvailable title="Medications on file">Prescriptions aren't kept in MediFlow yet. Check with the pharmacy or the clinician who treated you.</NotAvailable>}
      </div>
    </div>
  );
}

export default function App() {
  const [signedIn, setSignedIn] = useState(isSignedIn());
  const signedOut = useCallback(() => setSignedIn(false), []);
  return signedIn ? <Dashboard onSignedOut={signedOut} /> : <SignIn onSignedIn={() => setSignedIn(true)} />;
}
