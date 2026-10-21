import { useEffect, useState } from "react";
import { prefersReducedMotion } from "./motion";

// Made-up patients for the animation on the landing page.
const ARRIVALS = [
  { name: "Tunde A.", dept: "Outpatient", esi: 4 },
  { name: "Grace E.", dept: "Emergency", esi: 2 },
  { name: "Musa K.", dept: "Outpatient", esi: 3 },
  { name: "Ife O.", dept: "Dental", esi: 5 },
  { name: "Chidi N.", dept: "Outpatient", esi: 3 },
  { name: "Zainab Y.", dept: "Emergency", esi: 1 },
  { name: "Kemi B.", dept: "Outpatient", esi: 4 },
  { name: "Emeka U.", dept: "Eye clinic", esi: 5 },
];
const ESI_SHORT = { 1: "Immediate", 2: "Emergent", 3: "Urgent", 4: "Less urgent", 5: "Non-urgent" };

const ordered = (rows) => [...rows].sort((a, b) => a.esi - b.esi || a.n - b.n);
const patient = (n) => ({ ...ARRIVALS[n % ARRIVALS.length], n, status: "waiting" });

function start() {
  return { rows: ordered([0, 1, 2, 3].map(patient)), arrivals: 4, seen: 0 };
}

// Each tick does one visible thing: the called patient leaves, or the first is called, or someone arrives.
function tick({ rows, arrivals, seen }) {
  if (rows.some((r) => r.status === "called")) {
    return { rows: rows.filter((r) => r.status !== "called"), arrivals, seen: seen + 1 };
  }
  if (rows.length >= 4) {
    return { rows: rows.map((r, i) => (i === 0 ? { ...r, status: "called" } : r)), arrivals, seen };
  }
  return { rows: ordered([...rows, { ...patient(arrivals), fresh: true }]), arrivals: arrivals + 1, seen };
}

/** A queue that keeps moving: patients arrive and slot in by urgency, and the first one is called. */
export default function LiveQueue() {
  const [state, setState] = useState(start);

  useEffect(() => {
    if (prefersReducedMotion()) return undefined;
    const timer = setInterval(() => setState(tick), 2200);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="lp-queue" role="img" aria-label="Example of the live queue: patients ordered by urgency, the first one called to a room">
      <div className="lp-queue-head">
        <div>
          <span className="lp-queue-title">Outpatient queue</span>
          <span className="lp-queue-sub">Ordered by urgency, then arrival</span>
        </div>
        <span className="lp-live"><span className="lp-live-dot" /> Live</span>
      </div>
      <ul aria-hidden="true">
        {state.rows.map((r, i) => (
          <li key={r.n} className={`lp-queue-row ${r.status} ${r.fresh ? "fresh" : ""}`}>
            <span className="lp-queue-pos">{r.status === "called" ? "→" : i + 1}</span>
            <span className="lp-queue-name">
              {r.name}
              <small>{r.dept}</small>
            </span>
            <span className={`badge esi-${r.esi}`}>ESI {r.esi}<span className="lp-hide-sm"> · {ESI_SHORT[r.esi]}</span></span>
            <span className="lp-queue-wait">{r.status === "called" ? "Called · Room 2" : `~${(i + 1) * 6} min`}</span>
          </li>
        ))}
      </ul>
      <div className="lp-queue-foot" aria-hidden="true">
        <span>{state.rows.filter((r) => r.status === "waiting").length} waiting</span>
        <span>{38 + state.seen} seen today</span>
      </div>
    </div>
  );
}
