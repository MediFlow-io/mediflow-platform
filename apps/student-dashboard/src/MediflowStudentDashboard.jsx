import { useState } from "react";
import { LayoutGrid, CalendarDays, ClipboardList, Syringe, Pill, Bell, Plus, X, Check, ShieldAlert, Phone } from "lucide-react";

// Mediflow palette
const C = {
  ink: "#0E2140",
  cobalt: "#2F5BFF",
  mint: "#2BC3A0",
  coral: "#FF6B6B",
  mist: "#EDF2F9",
  line: "#D9E2EF",
};

// ---- Sample data: replace with your Mediflow API ----
const student = { name: "Amara Okafor", id: "STU-2041", grade: "Grade 10B", blood: "O+", guardian: "Mrs. Ngozi Okafor", phone: "+234 803 555 0142" };

const journey = ["Checked in", "Nurse triage", "Doctor", "Pharmacy", "Cleared"];
const currentStage = 2; // 0-based index; -1 means no active visit

const vitals = [
  { label: "Heart rate", unit: "bpm", value: 78, trend: [74, 80, 76, 82, 79, 77, 78] },
  { label: "Temperature", unit: "°C", value: 36.8, trend: [36.6, 36.9, 36.7, 37.1, 36.8, 36.7, 36.8] },
  { label: "Weight", unit: "kg", value: 52, trend: [50.5, 50.8, 51, 51.2, 51.5, 51.8, 52] },
];

const seedAppts = [
  { id: 1, date: "2026-09-29", time: "10:30", reason: "Asthma review", staff: "Dr. Bello", status: "Confirmed" },
  { id: 2, date: "2026-10-08", time: "09:00", reason: "Vision screening", staff: "Nurse Adeyemi", status: "Pending" },
];

const visits = [
  { date: "2026-09-12", title: "Headache and fatigue", staff: "Nurse Adeyemi", note: "Rested 40 minutes and given paracetamol. Returned to class." },
  { date: "2026-08-03", title: "Asthma flare-up", staff: "Dr. Bello", note: "Inhaler used on site. Advised to carry it at all times." },
  { date: "2026-05-19", title: "Ankle sprain", staff: "Nurse Adeyemi", note: "Ice and compression. Excused from PE for one week." },
];

const vaccines = [
  { name: "Tetanus booster", when: "Mar 2025", done: true },
  { name: "Meningitis ACWY", when: "Sep 2024", done: true },
  { name: "HPV dose 1", when: "Jan 2026", done: true },
  { name: "HPV dose 2", when: "Due since Jul 2026", done: false },
];

const meds = [
  { name: "Salbutamol inhaler", dose: "2 puffs when wheezing", note: "Keep in school bag" },
  { name: "Cetirizine 10 mg", dose: "Once daily, evening", note: "Seasonal allergies" },
];

const allergies = ["Penicillin", "Groundnuts"];
const notices = ["HPV dose 2 is overdue. Book a clinic slot.", "Your 29 Sep appointment is confirmed."];

const fmt = (d) => new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

const nav = [
  { id: "home", label: "Today", icon: LayoutGrid },
  { id: "appts", label: "Appointments", icon: CalendarDays },
  { id: "history", label: "Visit history", icon: ClipboardList },
  { id: "vaccines", label: "Vaccines", icon: Syringe },
  { id: "meds", label: "Medications", icon: Pill },
];

function Logo({ light }) {
  return (
    <div className="flex items-center gap-2">
      <svg width="34" height="22" viewBox="0 0 34 22" fill="none" aria-hidden="true">
        <path d="M1 12 C6 12 6 3 11 3 S16 19 21 19 S26 11 33 11" stroke={C.mint} strokeWidth="3" strokeLinecap="round" />
        <path d="M1 8 C6 8 6 0 11 0" stroke={C.cobalt} strokeWidth="0" />
      </svg>
      <span className="text-xl font-bold tracking-tight" style={{ color: light ? "#fff" : C.ink }}>
        Medi<span style={{ color: C.mint }}>flow</span>
      </span>
    </div>
  );
}

function Spark({ data, color }) {
  const min = Math.min(...data), max = Math.max(...data), r = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * 100},${28 - ((v - min) / r) * 24}`).join(" ");
  return (
    <svg viewBox="0 0 100 32" className="w-full h-8" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
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

function CareJourney() {
  return (
    <div className="rounded-3xl p-6 md:p-8 text-white" style={{ background: C.ink }}>
      <p className="text-sm" style={{ color: "#9DB2D6" }}>Your visit to the clinic today</p>
      <h2 className="text-2xl md:text-3xl font-bold mt-1">
        {currentStage >= 0 ? `You're with ${journey[currentStage] === "Doctor" ? "the doctor" : journey[currentStage].toLowerCase()} now` : "No active visit"}
      </h2>
      {currentStage >= 0 && (
        <div className="mt-8 flex items-center">
          {journey.map((step, i) => {
            const done = i < currentStage, now = i === currentStage;
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

function Home({ appts, go }) {
  const next = appts[0];
  return (
    <div className="grid gap-5">
      <CareJourney />
      <div className="grid gap-5 md:grid-cols-3">
        {vitals.map((v, i) => (
          <Card key={v.label}>
            <div className="text-sm" style={{ color: "#5B6F8F" }}>{v.label}</div>
            <div className="text-3xl font-bold mt-1" style={{ color: C.ink }}>{v.value}<span className="text-base font-medium ml-1">{v.unit}</span></div>
            <Spark data={v.trend} color={[C.cobalt, C.coral, C.mint][i]} />
            <div className="text-xs mt-1" style={{ color: "#5B6F8F" }}>Last 7 readings</div>
          </Card>
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Next appointment" right={<button onClick={() => go("appts")} className="text-sm font-semibold" style={{ color: C.cobalt }}>Manage</button>} className="lg:col-span-2">
          {next ? (
            <div className="flex items-center gap-4">
              <div className="rounded-2xl px-4 py-3 text-center" style={{ background: C.mist, color: C.ink }}>
                <div className="text-2xl font-bold leading-none">{new Date(next.date).getDate()}</div>
                <div className="text-xs">{new Date(next.date).toLocaleString("en-GB", { month: "short" })}</div>
              </div>
              <div>
                <div className="font-semibold" style={{ color: C.ink }}>{next.reason}</div>
                <div className="text-sm" style={{ color: "#5B6F8F" }}>{next.time} with {next.staff}</div>
              </div>
            </div>
          ) : <p className="text-sm">Nothing booked. Open Appointments to request a slot.</p>}
        </Card>
        <Card title="Safety card">
          <div className="flex flex-wrap gap-2 mb-4">
            {allergies.map((a) => (
              <span key={a} className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium" style={{ background: "#FFE9E9", color: "#B23A3A" }}>
                <ShieldAlert size={14} /> {a}
              </span>
            ))}
          </div>
          <div className="text-sm flex items-center gap-2" style={{ color: C.ink }}><Phone size={14} /> {student.guardian}, {student.phone}</div>
        </Card>
      </div>
    </div>
  );
}

function Appts({ appts, setAppts }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ date: "", time: "", reason: "" });
  const ok = f.date && f.time && f.reason.trim();
  const inp = "mt-1 w-full rounded-xl px-3 py-2 bg-white";
  const save = () => {
    if (!ok) return;
    setAppts((a) => [...a, { id: Date.now(), ...f, staff: "To be assigned", status: "Pending" }].sort((x, y) => (x.date + x.time).localeCompare(y.date + y.time)));
    setF({ date: "", time: "", reason: "" });
    setOpen(false);
  };
  return (
    <Card
      title="Appointments"
      right={
        <button onClick={() => setOpen(!open)} className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold text-white" style={{ background: C.cobalt }}>
          {open ? <X size={16} /> : <Plus size={16} />} {open ? "Close" : "Book a slot"}
        </button>
      }
    >
      {open && (
        <div className="grid gap-3 md:grid-cols-4 p-4 rounded-2xl mb-5" style={{ background: C.mist }}>
          <label className="text-sm">Date<input type="date" className={inp} style={{ border: `1px solid ${C.line}` }} value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></label>
          <label className="text-sm">Time<input type="time" className={inp} style={{ border: `1px solid ${C.line}` }} value={f.time} onChange={(e) => setF({ ...f, time: e.target.value })} /></label>
          <label className="text-sm md:col-span-2">Reason<input className={inp} style={{ border: `1px solid ${C.line}` }} placeholder="e.g. Persistent cough" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></label>
          <button onClick={save} disabled={!ok} className="md:col-span-4 rounded-full py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ background: C.ink }}>Send request</button>
        </div>
      )}
      {!appts.length && <p className="text-sm">No appointments yet. Select Book a slot to request one.</p>}
      <ul>
        {appts.map((a) => (
          <li key={a.id} className="py-3 flex items-center justify-between gap-3" style={{ borderTop: `1px solid ${C.line}` }}>
            <div>
              <div className="font-semibold" style={{ color: C.ink }}>{a.reason}</div>
              <div className="text-sm" style={{ color: "#5B6F8F" }}>{fmt(a.date)}, {a.time} · {a.staff}</div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold rounded-full px-3 py-1" style={a.status === "Confirmed" ? { background: "#DDF6EF", color: "#137A62" } : { background: "#FFF1D6", color: "#8A5B00" }}>{a.status}</span>
              <button aria-label="Cancel appointment" onClick={() => setAppts((l) => l.filter((x) => x.id !== a.id))}><X size={16} color="#8A9BB8" /></button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function History() {
  return (
    <Card title="Visit history">
      <ol className="grid gap-6 ml-2" style={{ borderLeft: `2px solid ${C.line}` }}>
        {visits.map((v) => (
          <li key={v.date} className="pl-5 relative">
            <span className="absolute w-3 h-3 rounded-full top-1.5" style={{ left: -7, background: C.mint }} />
            <div className="text-sm" style={{ color: "#5B6F8F" }}>{fmt(v.date)} · {v.staff}</div>
            <div className="font-semibold" style={{ color: C.ink }}>{v.title}</div>
            <p className="text-sm max-w-xl mt-1">{v.note}</p>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function Vaccines() {
  return (
    <Card title="Vaccines">
      {vaccines.map((v) => (
        <div key={v.name} className="py-3 flex items-center justify-between" style={{ borderTop: `1px solid ${C.line}` }}>
          <div className="flex items-center gap-3">
            <span className="w-6 h-6 rounded-full flex items-center justify-center" style={{ background: v.done ? C.mint : "#FFD9A8" }}>
              {v.done && <Check size={14} color={C.ink} />}
            </span>
            <span className="font-medium" style={{ color: C.ink }}>{v.name}</span>
          </div>
          <span className="text-sm" style={{ color: v.done ? "#5B6F8F" : "#B25E00", fontWeight: v.done ? 400 : 600 }}>{v.when}</span>
        </div>
      ))}
    </Card>
  );
}

function Meds() {
  return (
    <Card title="Medications on file">
      <div className="grid md:grid-cols-2 gap-3">
        {meds.map((m) => (
          <div key={m.name} className="rounded-2xl p-4" style={{ background: C.mist }}>
            <div className="font-semibold" style={{ color: C.ink }}>{m.name}</div>
            <div className="text-sm mt-1">{m.dose}</div>
            <div className="text-xs mt-2" style={{ color: "#5B6F8F" }}>{m.note}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function MediflowStudentDashboard() {
  const [tab, setTab] = useState("home");
  const [appts, setAppts] = useState(seedAppts);
  const [showNotices, setShowNotices] = useState(false);

  return (
    <div className="min-h-screen md:flex" style={{ background: C.mist, color: "#2A3B57", fontFamily: "'Avenir Next', 'Segoe UI', system-ui, sans-serif" }}>
      <aside className="md:w-64 md:min-h-screen p-5 flex md:flex-col gap-6 items-center md:items-stretch justify-between md:justify-start" style={{ background: C.ink }}>
        <Logo light />
        <nav className="flex md:flex-col gap-1 overflow-x-auto">
          {nav.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap"
              style={{ background: tab === id ? C.cobalt : "transparent", color: tab === id ? "#fff" : "#9DB2D6" }}
            >
              <Icon size={18} /> <span className="hidden md:inline">{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="flex-1 p-5 md:p-8 max-w-5xl">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold" style={{ color: C.ink, fontFamily: "Georgia, serif" }}>Hello, {student.name.split(" ")[0]}</h1>
            <p className="text-sm" style={{ color: "#5B6F8F" }}>{student.grade} · {student.id} · Blood group {student.blood}</p>
          </div>
          <div className="relative">
            <button aria-label="Notifications" onClick={() => setShowNotices(!showNotices)} className="relative w-11 h-11 rounded-full bg-white flex items-center justify-center" style={{ border: `1px solid ${C.line}` }}>
              <Bell size={18} color={C.ink} />
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full text-[10px] text-white flex items-center justify-center" style={{ background: C.coral }}>{notices.length}</span>
            </button>
            {showNotices && (
              <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl p-3 grid gap-2 z-10 shadow-lg" style={{ border: `1px solid ${C.line}` }}>
                {notices.map((n) => <div key={n} className="text-sm rounded-xl p-3" style={{ background: C.mist }}>{n}</div>)}
              </div>
            )}
          </div>
        </header>

        {tab === "home" && <Home appts={appts} go={setTab} />}
        {tab === "appts" && <Appts appts={appts} setAppts={setAppts} />}
        {tab === "history" && <History />}
        {tab === "vaccines" && <Vaccines />}
        {tab === "meds" && <Meds />}
      </div>
    </div>
  );
}
