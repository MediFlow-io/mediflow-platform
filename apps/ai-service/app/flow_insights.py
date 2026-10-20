"""Patient-flow insights: expected waits with a likely range, and where flow is getting stuck.

Statistics and rules over aggregate numbers (no patient data at all). Transparent on purpose: every
finding says which numbers triggered it. A trained model can replace these functions later behind the
same endpoints.
"""
from __future__ import annotations

import math
import statistics

from .schemas import BottleneckRequest, QueueInput, WaitTimeRequest

MODEL_VERSION = "flow-stats-2026.10"
DEFAULT_SERVICE = (15.0, 8.0)  # minutes (mean, standard deviation) when there's too little history
Z_80 = 1.2816                  # 10th–90th percentile of a normal distribution


def wait_times(req: WaitTimeRequest) -> dict:
    return {"estimates": [wait_time(q) for q in req.queues], "method": "statistics", "model_version": MODEL_VERSION}


def wait_time(req: QueueInput) -> dict:
    """Expected minutes until a patient with `ahead` people in front is seen, with an 80% range.

    Waiting time ≈ sum of `ahead` consultations shared over `servers` clinicians. With n independent
    consultations of mean μ and spread σ, the sum has mean nμ and spread σ√n (normal approximation).
    """
    samples = [s for s in req.recent_service_minutes if 0 < s <= 240]
    if len(samples) >= 5:
        mean, sd = statistics.fmean(samples), statistics.stdev(samples)
        basis = f"{len(samples)} recent consultations (mean {mean:.0f} min)"
    else:
        mean, sd = DEFAULT_SERVICE
        basis = "too few recent consultations; using a 15-minute default"
    confidence = "high" if len(samples) >= 50 else "medium" if len(samples) >= 15 else "low"
    servers = max(1, req.clinicians)
    expected = req.ahead * mean / servers
    spread = Z_80 * sd * math.sqrt(req.ahead) / servers
    return {
        "name": req.name,
        "expected_minutes": round(expected),
        "low_minutes": max(0, math.floor(expected - spread)),
        "high_minutes": math.ceil(expected + spread),
        "confidence": confidence,
        "basis": basis,
        "note": "A more urgent arrival moves ahead, so a patient's real wait can be longer.",
    }


SEVERITY = {"high": 0, "medium": 1, "low": 2}


def bottlenecks(req: BottleneckRequest) -> dict:
    findings: list[dict] = []

    def find(severity: str, department: str, stage: str, message: str):
        findings.append({"severity": severity, "department": department, "stage": stage, "message": message})

    for d in req.departments:
        wait, call, consult = d.avg_wait_minutes, d.avg_call_to_start_minutes, d.avg_consult_minutes
        if d.check_ins < 5:
            continue  # too few visits to say anything useful
        if wait is not None and consult is not None and wait >= 20 and wait >= 2 * consult:
            sev = "high" if wait >= 60 else "medium"
            find(sev, d.name, "waiting", f"Patients wait {wait:.0f} min to be called but consultations take {consult:.0f} min: "
                 "there aren't enough clinicians for the arrivals. Add a clinician at the busiest hours.")
        if call is not None and call >= 10:
            find("medium" if call >= 20 else "low", d.name, "called_to_seen",
                 f"Called patients take {call:.0f} min to reach the clinician. Check room hand-over and that patients "
                 "stay nearby (\"your turn is near\" notifications help).")
        if consult is not None and consult >= 30:
            find("low", d.name, "consultation", f"Consultations average {consult:.0f} min. Check whether tests or "
                 "paperwork could happen before the patient is seen.")
        if d.seen_within_target_percent is not None and d.seen_within_target_percent < 70:
            find("high" if d.seen_within_target_percent < 50 else "medium", d.name, "targets",
                 f"Only {d.seen_within_target_percent:.0f}% of patients were seen within their ESI target.")
        if d.waiting_now and d.waiting_now >= 10:
            find("medium", d.name, "queue", f"{d.waiting_now} patients are waiting right now.")

    busy = sorted((h for h in req.hours if h.check_ins > 0), key=lambda h: (h.check_ins, h.avg_wait_minutes or 0), reverse=True)[:2]
    if busy and sum(h.check_ins for h in req.hours) >= 10:
        peak = ", ".join(f"{h.hour:02d}:00 ({h.check_ins} check-ins)" for h in sorted(busy, key=lambda h: h.hour))
        find("low", "All", "demand", f"Busiest hours: {peak}. Roster more staff then.")

    findings.sort(key=lambda f: (SEVERITY[f["severity"]], f["department"]))
    return {"findings": findings, "method": "rules", "model_version": MODEL_VERSION}
