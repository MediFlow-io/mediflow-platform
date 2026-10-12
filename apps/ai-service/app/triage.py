"""Rule-based ESI triage *suggestion*.

Decision support only: a nurse or doctor sets the real ESI level. The rules
follow the shape of the ESI v4 algorithm (life-saving intervention → high-risk
or danger-zone vitals → expected resources). They are transparent on purpose:
every suggestion lists the rules that fired so a clinician can check them.

Safety choices:
- Ambiguity rounds toward MORE urgent. Keyword matching ignores negation, so
  "no chest pain" still flags chest pain; over-triage is the safe failure.
- Without vitals, nothing is suggested below ESI 3, because stability cannot be confirmed.
- No confidence score is returned. Rules have no calibrated probability and
  inventing one would mislead clinicians.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schemas import TriageRequest

MODEL_VERSION = "rules-esi-2026.10"

# Complaint keywords, normalised to lowercase. Matched as whole phrases.
LIFE_THREAT = (
    "not breathing", "stopped breathing", "no pulse", "cardiac arrest", "unresponsive",
    "unconscious", "choking", "anaphylaxis", "uncontrolled bleeding", "actively seizing",
)
HIGH_RISK = (
    "chest pain", "shortness of breath", "difficulty breathing", "can't breathe", "cannot breathe",
    "stroke", "slurred speech", "facial droop", "one sided weakness", "suicidal", "self harm",
    "overdose", "poisoning", "seizure", "convulsion", "allergic reaction", "vomiting blood",
    "coughing blood", "severe bleeding", "severe burn", "head injury", "fainted", "collapsed",
    "pregnant bleeding", "severe pain",
)
MULTI_RESOURCE = (
    "abdominal pain", "stomach pain", "fever", "vomiting", "diarrhoea", "diarrhea", "fracture",
    "broken", "dislocation", "back pain", "headache", "dehydration", "urinary retention",
)
ONE_RESOURCE = (
    "cut", "laceration", "sprain", "sore throat", "ear pain", "urinary", "painful urination",
    "eye irritation", "minor burn", "wound",
)
NO_RESOURCE = (
    "prescription refill", "refill", "medical certificate", "follow up", "follow-up", "cold",
    "runny nose", "rash", "insect bite", "mild cough", "check up", "checkup",
)


def _matches(text: str, phrases: tuple[str, ...]) -> list[str]:
    return [p for p in phrases if re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", text)]


def danger_zone_limits(age_years: float | None) -> tuple[int, int]:
    """(max heart rate, max respiratory rate) from the ESI handbook danger-zone table."""
    if age_years is None or age_years > 8:
        return 100, 20
    if age_years < 0.25:
        return 180, 50
    if age_years < 3:
        return 160, 40
    return 140, 30


@dataclass
class TriageResult:
    suggested_esi: int
    reasons: list[str] = field(default_factory=list)
    missing_vitals: list[str] = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        return {1: "CRITICAL", 2: "HIGH", 3: "MEDIUM"}.get(self.suggested_esi, "LOW")

    @property
    def recommendation(self) -> str:
        return {
            1: "Immediate life-saving assessment. Alert the doctor now.",
            2: "High risk: prioritise clinical assessment within minutes.",
            3: "Stable for now. Likely needs several resources (labs, imaging, IV). Reassess vitals while waiting.",
            4: "Likely needs one resource. Standard queue; reassess if condition changes.",
            5: "Likely needs no resources. Standard queue; reassess if condition changes.",
        }[self.suggested_esi]


def suggest_esi(req: TriageRequest) -> TriageResult:
    complaint = " ".join((req.chief_complaint or "").lower().split())
    v = req.vitals
    age = req.age_years
    reasons: list[str] = []

    # --- ESI 1: needs an immediate life-saving intervention ---
    if v.avpu in ("P", "U"):
        reasons.append(f"Responds only to {'pain' if v.avpu == 'P' else 'nothing'} (AVPU {v.avpu})")
    if v.spo2 is not None and v.spo2 < 90:
        reasons.append(f"SpO2 {v.spo2}% is below 90%")
    if v.systolic_bp is not None and v.systolic_bp < 80 and (age is None or age >= 12):
        reasons.append(f"Systolic BP {v.systolic_bp} mmHg is below 80")
    if v.heart_rate is not None and (v.heart_rate < 40 or ((age is None or age > 8) and v.heart_rate > 150)):
        reasons.append(f"Heart rate {v.heart_rate}/min is critically abnormal")
    if v.resp_rate is not None and (v.resp_rate < 8 or ((age is None or age > 8) and v.resp_rate > 35)):
        reasons.append(f"Respiratory rate {v.resp_rate}/min is critically abnormal")
    reasons += [f'Complaint mentions "{k}"' for k in _matches(complaint, LIFE_THREAT)]
    if reasons:
        return TriageResult(1, reasons, v.missing())

    # --- ESI 2: high-risk situation, new confusion, severe pain, or danger-zone vitals ---
    hr_max, rr_max = danger_zone_limits(age)
    if v.avpu == "V":
        reasons.append("Responds only to voice (AVPU V): possible new confusion or lethargy")
    if req.pain_score is not None and req.pain_score >= 7:
        reasons.append(f"Severe pain ({req.pain_score}/10)")
    if v.heart_rate is not None and v.heart_rate > hr_max:
        reasons.append(f"Heart rate {v.heart_rate}/min is above the danger zone ({hr_max}) for age")
    if v.resp_rate is not None and v.resp_rate > rr_max:
        reasons.append(f"Respiratory rate {v.resp_rate}/min is above the danger zone ({rr_max}) for age")
    if v.spo2 is not None and v.spo2 < 92:
        reasons.append(f"SpO2 {v.spo2}% is below 92%")
    if v.temperature_c is not None:
        if v.temperature_c >= 40 or v.temperature_c < 35:
            reasons.append(f"Temperature {v.temperature_c}°C is outside the safe range")
        elif age is not None and age < 0.25 and v.temperature_c >= 38:
            reasons.append(f"Fever {v.temperature_c}°C in an infant under 3 months")
    reasons += [f'High-risk complaint: "{k}"' for k in _matches(complaint, HIGH_RISK)]
    if reasons:
        return TriageResult(2, reasons, v.missing())

    # --- ESI 3–5: expected resources, judged from the complaint ---
    missing = v.missing()
    if hits := _matches(complaint, MULTI_RESOURCE):
        result = TriageResult(3, [f'Complaint "{hits[0]}" usually needs several resources'])
    elif hits := _matches(complaint, ONE_RESOURCE):
        result = TriageResult(4, [f'Complaint "{hits[0]}" usually needs one resource'])
    elif hits := _matches(complaint, NO_RESOURCE):
        result = TriageResult(5, [f'Complaint "{hits[0]}" usually needs no resources'])
    else:
        result = TriageResult(3, ["Complaint not recognised; defaulting to ESI 3 for clinician review"])

    if result.suggested_esi > 3 and len(missing) == len(v.CORE_VITALS):
        result.suggested_esi = 3
        result.reasons.append("No vitals recorded: cannot confirm stability, so not suggesting below ESI 3")
    result.missing_vitals = missing
    return result
