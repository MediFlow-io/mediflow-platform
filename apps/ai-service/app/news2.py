"""NEWS2 (National Early Warning Score 2, Royal College of Physicians, 2017): a risk score from vital signs.

It is a published, validated bedside score, not a trained model, so every point can be checked by hand.
Decision support only: it flags patients who may be deteriorating; a clinician decides what to do.

Missing vitals score nothing, so an incomplete score is a lower bound: the response says which are
missing and never calls an incomplete score "low" without saying so. SpO₂ uses scale 1 (scale 2 is
for confirmed hypercapnic respiratory failure, which needs a clinician's judgement).
"""
from __future__ import annotations

from dataclasses import dataclass

from .schemas import RiskScoreRequest

MODEL_VERSION = "news2-rcp-2017"


@dataclass(frozen=True)
class Band:
    upto: float      # inclusive upper bound
    points: int


def points(value: float, bands: list[Band]) -> int:
    for band in bands:
        if value <= band.upto:
            return band.points
    return bands[-1].points


RESP = [Band(8, 3), Band(11, 1), Band(20, 0), Band(24, 2), Band(float("inf"), 3)]
SPO2 = [Band(91, 3), Band(93, 2), Band(95, 1), Band(float("inf"), 0)]
SYSTOLIC = [Band(90, 3), Band(100, 2), Band(110, 1), Band(219, 0), Band(float("inf"), 3)]
PULSE = [Band(40, 3), Band(50, 1), Band(90, 0), Band(110, 1), Band(130, 2), Band(float("inf"), 3)]
TEMP = [Band(35.0, 3), Band(36.0, 1), Band(38.0, 0), Band(39.0, 1), Band(float("inf"), 2)]

RESPONSE = {
    "low": "Continue routine observations; a nurse assesses whether to change their frequency.",
    "low-medium": "One vital sign is in the red zone: a clinician should review urgently.",
    "medium": "Urgent review by a clinician; consider moving the patient up the queue.",
    "high": "Emergency assessment now by a clinician competent in acute care.",
}


def score(req: RiskScoreRequest) -> dict:
    v = req.vitals
    parts: list[dict] = []

    def add(name: str, value, pts: int):
        parts.append({"parameter": name, "value": value, "points": pts})

    if v.resp_rate is not None:
        add("resp_rate", v.resp_rate, points(v.resp_rate, RESP))
    if v.spo2 is not None:
        add("spo2", v.spo2, points(v.spo2, SPO2))
    add("supplemental_oxygen", req.on_oxygen, 2 if req.on_oxygen else 0)
    if v.systolic_bp is not None:
        add("systolic_bp", v.systolic_bp, points(v.systolic_bp, SYSTOLIC))
    if v.heart_rate is not None:
        add("heart_rate", v.heart_rate, points(v.heart_rate, PULSE))
    if v.avpu is not None or req.new_confusion:
        alert = v.avpu in (None, "A") and not req.new_confusion
        add("consciousness", "new confusion" if req.new_confusion and v.avpu in (None, "A") else v.avpu, 0 if alert else 3)
    if v.temperature_c is not None:
        add("temperature_c", v.temperature_c, points(v.temperature_c, TEMP))

    total = sum(p["points"] for p in parts)
    red = any(p["points"] == 3 for p in parts)
    if total >= 7:
        risk = "high"
    elif total >= 5:
        risk = "medium"
    elif red:
        risk = "low-medium"
    else:
        risk = "low"
    missing = [name for name in ("resp_rate", "spo2", "systolic_bp", "heart_rate", "temperature_c") if getattr(v, name) is None]
    if v.avpu is None and not req.new_confusion:
        missing.append("avpu")
    reasons = [f"{p['parameter']} {p['value']} → {p['points']}" for p in parts if p["points"] > 0]
    if missing:
        reasons.append("Incomplete: missing " + ", ".join(missing) + " (the true score may be higher).")
    return {
        "score": total, "risk": risk, "complete": not missing, "parameters": parts, "missing": missing,
        "reasons": reasons, "recommendation": RESPONSE[risk], "method": "news2", "model_version": MODEL_VERSION,
    }
