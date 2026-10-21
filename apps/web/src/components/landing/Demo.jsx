import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "./motion";

const STEP_MS = 7000;

/** Milliseconds since the component mounted (a finished state straight away if motion is reduced). */
function useElapsed() {
  const [elapsed, setElapsed] = useState(() => (prefersReducedMotion() ? 60_000 : 0));
  useEffect(() => {
    if (prefersReducedMotion()) return undefined;
    const startedAt = Date.now();
    const timer = setInterval(() => {
      const ms = Date.now() - startedAt;
      setElapsed(ms);
      if (ms > STEP_MS) clearInterval(timer);
    }, 50);
    return () => clearInterval(timer);
  }, []);
  return elapsed;
}

/** Text typed out from `from` ms, one character every 35 ms. */
const typed = (text, t, from) => text.slice(0, Math.max(0, Math.floor((t - from) / 35)));
const shown = (t, at) => (t >= at ? "on" : "");

function Field({ label, value, caret }) {
  return (
    <div className="dm-field">
      <span className="dm-label">{label}</span>
      <span className="dm-input">{value}{caret && <span className="dm-caret" />}</span>
    </div>
  );
}

function Button({ children, pressed, tone = "" }) {
  return <span className={`dm-btn ${tone} ${pressed ? "pressed" : ""}`}>{children}</span>;
}

function RegisterScreen() {
  const t = useElapsed();
  const matric = typed("SEN/22/9269", t, 300);
  const name = typed("Amaka Obi", t, 900);
  const password = "•".repeat(typed("password12", t, 1400).length);
  return (
    <div className="dm-screen">
      <div className="dm-app-title">Student registration</div>
      <Field label="Matric number" value={matric} caret={t < 900} />
      <Field label="Full name" value={name} caret={t >= 900 && t < 1400} />
      <Field label="Password" value={password} caret={t >= 1400 && t < 2000} />
      <Button pressed={t >= 2300 && t < 2600}>Create account</Button>
      <div className={`dm-toast success ${shown(t, 2700)}`}>
        <strong>Account created</strong> · Health card MF-4F21C9
      </div>
    </div>
  );
}

const VITALS = [["HR", "112"], ["Temp", "38.9 °C"], ["SpO₂", "96%"], ["BP", "118/76"], ["RR", "22"]];

function CheckInScreen() {
  const t = useElapsed();
  return (
    <div className="dm-screen">
      <div className="dm-app-title">Check in · Reception</div>
      <Field label="Patient" value={typed("Amaka", t, 200)} caret={t < 600} />
      <div className={`dm-result ${shown(t, 700)}`}>
        <span className="dm-avatar">AO</span>
        <span><strong>Amaka Obi</strong><small>SEN/22/9269 · Allergy: penicillin</small></span>
      </div>
      <Field label="What brings you in?" value={typed("Fever and headache for 2 days", t, 1300)} caret={t >= 1300 && t < 2400} />
      <div className="dm-chips">
        {VITALS.map(([k, v], i) => (
          <span key={k} className={`dm-chip ${shown(t, 2500 + i * 250)}`}><small>{k}</small> {v}</span>
        ))}
      </div>
      <Button pressed={t >= 4100 && t < 4400}>Check in to Outpatient</Button>
    </div>
  );
}

function TriageScreen() {
  const t = useElapsed();
  const news = Math.min(5, Math.floor(Math.max(0, t - 600) / 220));
  return (
    <div className="dm-screen">
      <div className="dm-app-title">Triage suggestion</div>
      <div className="dm-triage">
        <div className={`dm-esi ${shown(t, 300)}`}>
          <span className="badge esi-3">ESI 3 · Urgent</span>
          <small>Suggested from vitals and complaint</small>
        </div>
        <div className="dm-news">
          <div className="dm-news-row"><span>NEWS2 early-warning score</span><strong>{news}</strong></div>
          <div className="dm-meter"><span style={{ width: `${(news / 7) * 100}%` }} /></div>
          <small className={shown(t, 1800)}>Medium risk: review within the hour</small>
        </div>
        <ul className="dm-reasons">
          {["Fever 38.9 °C with heart rate 112", "Breathing rate 22 per minute", "Oxygen and blood pressure normal"].map((r, i) => (
            <li key={r} className={shown(t, 2300 + i * 350)}>{r}</li>
          ))}
        </ul>
      </div>
      <div className="dm-row">
        <Button pressed={t >= 3900 && t < 4200}>Accept ESI 3</Button>
        <Button tone="ghost">Change</Button>
      </div>
      <div className={`dm-toast ${shown(t, 4300)}`}>Triage confirmed by Nurse Bello · the nurse always decides</div>
    </div>
  );
}

const QUEUE = [
  { name: "Grace E.", esi: 2, wait: "now" },
  { name: "Musa K.", esi: 3, wait: "~6 min" },
  { name: "Tunde A.", esi: 4, wait: "~18 min" },
  { name: "Ife O.", esi: 5, wait: "~24 min" },
];

function QueueScreen() {
  const t = useElapsed();
  const joined = t >= 1200;
  const rows = joined ? [QUEUE[0], QUEUE[1], { name: "Amaka O.", esi: 3, wait: "~12 min", me: true }, QUEUE[2], QUEUE[3]] : QUEUE;
  return (
    <div className="dm-screen">
      <div className="dm-app-title">Outpatient queue <span className="lp-live"><span className="lp-live-dot" /> Live</span></div>
      <ul className="dm-queue">
        {rows.map((r, i) => (
          <li key={r.name} className={r.me ? "me" : ""}>
            <span className="dm-pos">{i + 1}</span>
            <span className="dm-name">{r.name}</span>
            <span className={`badge esi-${r.esi}`}>ESI {r.esi}</span>
            <span className="dm-wait">{r.wait}</span>
          </li>
        ))}
      </ul>
      <p className={`dm-caption ${shown(t, 2200)}`}>
        Amaka slots in behind patients who are just as urgent and arrived earlier, and ahead of less urgent ones.
      </p>
    </div>
  );
}

function CallScreen() {
  const t = useElapsed();
  const called = t >= 1300;
  return (
    <div className="dm-split">
      <div className="dm-screen">
        <div className="dm-app-title">Dr. Adeyemi · Room 2</div>
        <div className={`dm-next ${called ? "called" : ""}`}>
          <span className="dm-avatar">AO</span>
          <span><strong>Amaka Obi</strong><small>ESI 3 · Fever and headache</small></span>
          <span className="dm-status">{called ? "Called" : "Next"}</span>
        </div>
        <Button pressed={t >= 900 && t < 1250}>{called ? "Start consultation" : "Call next patient"}</Button>
      </div>
      <div className="dm-phone" aria-hidden="true">
        <div className="dm-phone-notch" />
        <div className="dm-phone-time">Student dashboard</div>
        <div className={`dm-push near ${shown(t, 200)}`}>
          <strong>Your turn is near</strong>
          <span>1 person is ahead of you in Outpatient.</span>
        </div>
        <div className={`dm-push ${shown(t, 1700)}`}>
          <strong>You've been called · now</strong>
          <span>Please go to Outpatient now.</span>
        </div>
      </div>
    </div>
  );
}

function RecordScreen() {
  const t = useElapsed();
  return (
    <div className="dm-screen">
      <div className="dm-app-title">Consultation · Amaka Obi</div>
      <Field label="Notes" value={typed("Febrile, no neck stiffness. Malaria test positive.", t, 200)} caret={t < 2000} />
      <div className={`dm-line ${shown(t, 2100)}`}><small>Diagnosis</small> Malaria, uncomplicated</div>
      <div className={`dm-line ${shown(t, 2700)}`}><small>Prescription</small> Artemether-lumefantrine, 3 days <span className="dm-ok">Sent to pharmacy ✓</span></div>
      <div className={`dm-line ${shown(t, 3300)}`}><small>Pharmacy</small> Waiting to dispense · allergy shown: penicillin</div>
      <div className={`dm-toast success ${shown(t, 4100)}`}>
        <strong>Visit complete</strong> · Follow-up booked for Tue 10:30, reminder the day before
      </div>
    </div>
  );
}

const STEPS = [
  { title: "Register", who: "Student", text: "Amaka signs up with her matriculation number and gets a health card number.", Screen: RegisterScreen },
  { title: "Check in", who: "Reception", text: "The front desk finds her record, notes the complaint and takes vitals.", Screen: CheckInScreen },
  { title: "Triage", who: "Nurse", text: "MediFlow suggests an urgency level and an early-warning score with its reasons. The nurse confirms.", Screen: TriageScreen },
  { title: "Queue", who: "Everyone", text: "She joins the live queue by urgency. Every screen updates at once, with a wait estimate.", Screen: QueueScreen },
  { title: "Called", who: "Doctor + student", text: "Her student dashboard tells her when her turn is near, and when the doctor calls her in.", Screen: CallScreen },
  { title: "Treat", who: "Doctor", text: "Notes, diagnosis and prescription go on her record; the pharmacy sees the prescription, with her allergies, right away.", Screen: RecordScreen },
];

export default function Demo() {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(() => !prefersReducedMotion());
  const [hovering, setHovering] = useState(false);
  const [inView, setInView] = useState(false);
  const [seen, setSeen] = useState(false); // the screens start animating the first time the demo is visible
  const running = playing && !hovering && inView;
  const root = useRef(null);
  const strip = useRef(null);
  const tabs = useRef([]);

  useEffect(() => {
    if (!("IntersectionObserver" in window)) {
      setInView(true);
      setSeen(true);
      return undefined;
    }
    const observer = new IntersectionObserver(([entry]) => {
      setInView(entry.isIntersecting);
      if (entry.isIntersecting) setSeen(true);
    }, { threshold: 0.35 });
    observer.observe(root.current);
    return () => observer.disconnect();
  }, []);

  // On narrow screens the steps scroll sideways: keep the current one in sight.
  useEffect(() => {
    const tab = tabs.current[step];
    if (strip.current && tab) strip.current.scrollTo({ left: tab.offsetLeft - 16, behavior: "smooth" });
  }, [step]);

  useEffect(() => {
    if (!running) return undefined;
    const timer = setTimeout(() => setStep((s) => (s + 1) % STEPS.length), STEP_MS);
    return () => clearTimeout(timer);
  }, [running, step]);

  function go(i) {
    setStep((i + STEPS.length) % STEPS.length);
  }

  function onKeyDown(e) {
    const move = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!move) return;
    e.preventDefault();
    const i = (step + move + STEPS.length) % STEPS.length;
    go(i);
    tabs.current[i]?.focus();
  }

  const { Screen } = STEPS[step];
  return (
    <div className="dm" ref={root} onMouseEnter={() => setHovering(true)} onMouseLeave={() => setHovering(false)}>
      <div className="dm-steps" ref={strip} role="tablist" aria-label="Demo steps" onKeyDown={onKeyDown}>
        {STEPS.map((s, i) => (
          <button
            key={s.title}
            ref={(el) => { tabs.current[i] = el; }}
            type="button"
            role="tab"
            id={`dm-tab-${i}`}
            aria-selected={i === step}
            aria-controls="dm-panel"
            tabIndex={i === step ? 0 : -1}
            className={`dm-step ${i === step ? "active" : ""} ${i < step ? "done" : ""}`}
            onClick={() => go(i)}
          >
            <span className="dm-step-num">{i + 1}</span>
            <span className="dm-step-text">
              <strong>{s.title}</strong>
              <small>{s.who}</small>
            </span>
            {i === step && (
              <span className="dm-progress" aria-hidden="true">
                <span key={`${step}-${running}`} className={running ? "run" : ""} style={{ animationDuration: `${STEP_MS}ms` }} />
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="dm-stage" role="tabpanel" id="dm-panel" aria-labelledby={`dm-tab-${step}`}>
        <div className="dm-window">
          <div className="dm-window-bar" aria-hidden="true"><span /><span /><span /></div>
          <div className="dm-window-body" key={seen ? step : "waiting"}>
            {seen && <Screen />}
          </div>
        </div>
        <div className="dm-explain">
          <p className="dm-explain-step">Step {step + 1} of {STEPS.length} · {STEPS[step].who}</p>
          <p className="dm-explain-text" key={step}>{STEPS[step].text}</p>
          <div className="dm-controls">
            <button type="button" className="dm-control" onClick={() => go(step - 1)} aria-label="Previous step">←</button>
            <button type="button" className="dm-control wide" onClick={() => setPlaying((p) => !p)}>
              {playing ? "Pause" : "Play"}
            </button>
            <button type="button" className="dm-control" onClick={() => go(step + 1)} aria-label="Next step">→</button>
          </div>
        </div>
      </div>
    </div>
  );
}
