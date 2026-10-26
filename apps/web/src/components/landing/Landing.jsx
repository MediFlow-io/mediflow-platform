import { useEffect, useRef, useState } from "react";
import Demo from "./Demo";
import LiveQueue from "./LiveQueue";
import "./landing.css";

const FEATURES = [
  {
    icon: "triage",
    title: "Triage support",
    text: "Vitals go in at the desk; MediFlow suggests an ESI level and a NEWS2 early-warning score with its reasons. A nurse always makes the final call.",
  },
  {
    icon: "queue",
    title: "A live, fair queue",
    text: "Patients are ordered by urgency, then arrival. Every screen updates the moment someone is called. No refreshing, no shouting names.",
  },
  {
    icon: "bell",
    title: "Notifications that matter",
    text: "Students hear when their turn is near and when they're called. Clinicians are paged for ESI 1–2 arrivals.",
  },
  {
    icon: "record",
    title: "Clinical records",
    text: "Consultation notes, diagnoses, prescriptions, referrals and admissions, kept per visit with a full history per patient.",
  },
  {
    icon: "calendar",
    title: "Appointments",
    text: "Students request a slot; the front desk confirms it. Reminders go out the day before and within the hour.",
  },
  {
    icon: "chart",
    title: "Reports and insight",
    text: "Daily volumes, wait times by department and bottleneck alerts help managers staff the busy hours.",
  },
];

const ROLES = [
  ["Reception", "Registers patients, checks them in and books appointments."],
  ["Nurses", "Record vitals, confirm triage and keep the queue moving."],
  ["Doctors", "Call the next patient, write notes and prescribe."],
  ["Pharmacy", "Sees prescriptions as they're written, with allergies shown, and marks them dispensed."],
  ["Administrators", "Manage staff, departments, clinic hours and rules."],
  ["Students", "Book visits, follow their place in the queue, see their record."],
];

function Icon({ name }) {
  const paths = {
    triage: <path d="M3 12h4l2-5 4 10 2-5h6" />,
    queue: <><path d="M4 6h16" /><path d="M4 12h10" /><path d="M4 18h6" /><circle cx="19" cy="15" r="3" /></>,
    bell: <><path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z" /><path d="M10 21h4" /></>,
    record: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 8h6M9 12h6M9 16h3" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>,
  };
  return (
    <svg className="lp-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

/** Adds .is-visible to [data-reveal] elements as they scroll into view (CSS does the animation). */
function useReveal(ref) {
  useEffect(() => {
    const items = ref.current?.querySelectorAll("[data-reveal]") ?? [];
    if (!("IntersectionObserver" in window)) {
      items.forEach((el) => el.classList.add("is-visible"));
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      }),
      { threshold: 0.15 },
    );
    items.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [ref]);
}

function Brand() {
  return (
    <a className="lp-brand" href="#top" aria-label="MediFlow home">
      <span className="brand-mark" />
      <span>MediFlow</span>
    </a>
  );
}

export default function Landing({ studentPortalUrl }) {
  const root = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  useReveal(root);

  return (
    <div className="lp" ref={root} id="top">
      <header className="lp-nav">
        <div className="lp-container lp-nav-inner">
          <Brand />
          <button type="button" className="lp-menu-button" aria-expanded={menuOpen} aria-controls="lp-menu" onClick={() => setMenuOpen((o) => !o)}>
            <span className="lp-sr">Menu</span>
            <span aria-hidden="true" className="lp-burger" />
          </button>
          <nav id="lp-menu" className={`lp-links ${menuOpen ? "open" : ""}`} onClick={() => setMenuOpen(false)}>
            <a href="#demo">How it works</a>
            <a href="#features">Features</a>
            <a href="#roles">Who it's for</a>
            <a href={studentPortalUrl}>Student portal</a>
            <a className="lp-btn lp-btn-small" href="/login">Staff sign-in</a>
          </nav>
        </div>
      </header>

      <main>
        <section className="lp-hero">
          <div className="lp-blob lp-blob-a" aria-hidden="true" />
          <div className="lp-blob lp-blob-b" aria-hidden="true" />
          <div className="lp-container lp-hero-grid">
            <div className="lp-hero-copy">
              <p className="lp-eyebrow lp-rise" style={{ animationDelay: "0ms" }}>Campus health centre operations</p>
              <h1 className="lp-rise" style={{ animationDelay: "80ms" }}>
                Shorter waits. <span className="lp-accent">Safer triage.</span> A calmer clinic.
              </h1>
              <p className="lp-lead lp-rise" style={{ animationDelay: "160ms" }}>
                MediFlow takes a patient from the front desk to the consulting room: check-in, triage support,
                a live queue, notes and prescriptions, with students kept informed on their phones.
              </p>
              <div className="lp-cta lp-rise" style={{ animationDelay: "240ms" }}>
                <a className="lp-btn" href={studentPortalUrl}>I'm a student</a>
                <a className="lp-btn lp-btn-ghost" href="/login">Staff sign-in</a>
              </div>
              <a className="lp-watch lp-rise" style={{ animationDelay: "320ms" }} href="#demo">
                <span className="lp-play" aria-hidden="true" /> See how it works in a minute
              </a>
            </div>
            <div className="lp-hero-visual lp-rise" style={{ animationDelay: "200ms" }}>
              <LiveQueue />
            </div>
          </div>
        </section>

        <section className="lp-strip" aria-label="At a glance">
          <div className="lp-container lp-strip-grid">
            {[
              ["5-level", "ESI triage"],
              ["NEWS2", "early-warning score"],
              ["Live", "queue on every screen"],
              ["8", "roles, each with its own view"],
            ].map(([big, small], i) => (
              <div key={small} data-reveal style={{ transitionDelay: `${i * 80}ms` }}>
                <strong>{big}</strong>
                <span>{small}</span>
              </div>
            ))}
          </div>
        </section>

        <section id="demo" className="lp-section">
          <div className="lp-container">
            <div className="lp-heading" data-reveal>
              <p className="lp-eyebrow">How it works</p>
              <h2>One visit, start to finish</h2>
              <p>Follow Amaka, a student with a fever, through MediFlow. The demo plays on its own; pick any step to jump to it.</p>
            </div>
            <div data-reveal>
              <Demo />
            </div>
          </div>
        </section>

        <section id="features" className="lp-section lp-section-tint">
          <div className="lp-container">
            <div className="lp-heading" data-reveal>
              <p className="lp-eyebrow">Features</p>
              <h2>Everything the front desk and the clinic floor need</h2>
            </div>
            <div className="lp-features">
              {FEATURES.map((f, i) => (
                <article key={f.title} className="lp-feature" data-reveal style={{ transitionDelay: `${(i % 3) * 90}ms` }}>
                  <Icon name={f.icon} />
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </article>
              ))}
            </div>
            <div className="lp-secure" data-reveal>
              <h3>Private by default</h3>
              <p>
                Every person sees only what their role allows. Staff can turn on two-step sign-in, and every change to a
                record is logged. Notifications never include symptoms or diagnoses: only where and when.
              </p>
            </div>
          </div>
        </section>

        <section id="roles" className="lp-section">
          <div className="lp-container">
            <div className="lp-heading" data-reveal>
              <p className="lp-eyebrow">Who it's for</p>
              <h2>A view for every desk</h2>
            </div>
            <ol className="lp-roles">
              {ROLES.map(([role, text], i) => (
                <li key={role} data-reveal style={{ transitionDelay: `${(i % 3) * 90}ms` }}>
                  <span className="lp-role-num">{String(i + 1).padStart(2, "0")}</span>
                  <div>
                    <h3>{role}</h3>
                    <p>{text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="lp-section lp-start">
          <div className="lp-container">
            <div className="lp-heading" data-reveal>
              <p className="lp-eyebrow">Get started</p>
              <h2>Ready when you are</h2>
            </div>
            <div className="lp-start-grid">
              <div className="lp-start-card" data-reveal>
                <h3>Students</h3>
                <p>Create an account with your matriculation number, then book visits and follow the queue from your phone.</p>
                <a className="lp-btn" href={`${studentPortalUrl}/register`}>Create a student account</a>
                <a className="lp-link" href={studentPortalUrl}>Already registered? Sign in on the student portal →</a>
              </div>
              <div className="lp-start-card" data-reveal style={{ transitionDelay: "90ms" }}>
                <h3>Staff</h3>
                <p>Sign in with the staff ID your administrator gave you. Your role decides what you see.</p>
                <a className="lp-btn lp-btn-dark" href="/login">Staff sign-in</a>
                <span className="lp-note">No account yet? Ask your clinic administrator.</span>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-container lp-footer-inner">
          <Brand />
          <p>Hospital and campus clinic operations: triage, queue, records and notifications.</p>
          <a href="#top">Back to top ↑</a>
        </div>
      </footer>
    </div>
  );
}
