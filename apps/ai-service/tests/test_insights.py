import pytest
from fastapi.testclient import TestClient

from app.config import DEV_TOKEN
from app.main import app

client = TestClient(app)
AUTH = {"X-Internal-Token": DEV_TOKEN}
NORMAL = {"heart_rate": 80, "resp_rate": 16, "spo2": 98, "temperature_c": 36.8, "systolic_bp": 120, "avpu": "A"}


def risk(**body):
    res = client.post("/ai/risk-score", json=body, headers=AUTH)
    assert res.status_code == 200, res.text
    return res.json()


# --- NEWS2 ----------------------------------------------------------------

def test_normal_vitals_score_zero():
    r = risk(vitals=NORMAL)
    assert (r["score"], r["risk"], r["complete"]) == (0, "low", True)
    assert r["requires_clinician_review"] is True


@pytest.mark.parametrize("change, points", [
    ({"resp_rate": 8}, 3), ({"resp_rate": 10}, 1), ({"resp_rate": 22}, 2), ({"resp_rate": 25}, 3),
    ({"spo2": 91}, 3), ({"spo2": 93}, 2), ({"spo2": 95}, 1),
    ({"systolic_bp": 90}, 3), ({"systolic_bp": 95}, 2), ({"systolic_bp": 105}, 1), ({"systolic_bp": 220}, 3),
    ({"heart_rate": 40}, 3), ({"heart_rate": 45}, 1), ({"heart_rate": 100}, 1), ({"heart_rate": 120}, 2), ({"heart_rate": 131}, 3),
    ({"temperature_c": 35.0}, 3), ({"temperature_c": 35.5}, 1), ({"temperature_c": 38.5}, 1), ({"temperature_c": 39.1}, 2),
    ({"avpu": "V"}, 3),
])
def test_each_band_matches_the_rcp_chart(change, points):
    assert risk(vitals={**NORMAL, **change})["score"] == points


def test_risk_bands():
    assert risk(vitals={**NORMAL, "avpu": "V"})["risk"] == "low-medium"          # a single 3
    assert risk(vitals={**NORMAL, "resp_rate": 22, "heart_rate": 120, "temperature_c": 38.5})["risk"] == "medium"  # 2+2+1
    high = risk(vitals={**NORMAL, "resp_rate": 25, "spo2": 93, "heart_rate": 120}, on_oxygen=True)  # 3+2+2+2
    assert (high["score"], high["risk"]) == (9, "high")
    assert "Emergency assessment" in high["recommendation"]
    assert risk(vitals=NORMAL, new_confusion=True)["score"] == 3


def test_missing_vitals_are_flagged_not_assumed_normal():
    r = risk(vitals={"heart_rate": 80})
    assert r["complete"] is False
    assert set(r["missing"]) == {"resp_rate", "spo2", "systolic_bp", "temperature_c", "avpu"}
    assert any("true score may be higher" in reason for reason in r["reasons"])


def test_risk_score_needs_the_internal_token_and_rejects_identifiers():
    assert client.post("/ai/risk-score", json={"vitals": NORMAL}).status_code == 401
    assert client.post("/ai/risk-score", json={"vitals": NORMAL, "patient_name": "x"}, headers=AUTH).status_code == 422


# --- wait time -------------------------------------------------------------

def test_wait_time_uses_recent_consultations():
    body = {"queues": [{"name": "OPD", "ahead": 4, "clinicians": 2, "recent_service_minutes": [10, 12, 8, 10, 10, 11, 9] * 3}]}
    [res] = client.post("/ai/wait-time", json=body, headers=AUTH).json()["estimates"]
    assert res["name"] == "OPD"
    assert res["expected_minutes"] == 20
    assert res["low_minutes"] <= 20 <= res["high_minutes"]
    assert res["confidence"] == "medium" and "21 recent consultations" in res["basis"]


def test_wait_time_without_history_uses_the_default_with_low_confidence():
    body = {"queues": [{"name": "A", "ahead": 2, "clinicians": 0}, {"name": "B", "ahead": 0}]}
    a, b = client.post("/ai/wait-time", json=body, headers=AUTH).json()["estimates"]
    assert (a["expected_minutes"], a["confidence"]) == (30, "low")
    assert b["high_minutes"] == 0
    assert client.post("/ai/wait-time", json={"queues": []}, headers=AUTH).status_code == 422


# --- bottlenecks -------------------------------------------------------------

def test_bottleneck_findings_are_explained_and_ranked():
    body = {
        "departments": [
            {"name": "Outpatient", "check_ins": 80, "waiting_now": 12, "avg_wait_minutes": 70, "avg_call_to_start_minutes": 4,
             "avg_consult_minutes": 12, "seen_within_target_percent": 45},
            {"name": "Emergency", "check_ins": 20, "avg_wait_minutes": 5, "avg_call_to_start_minutes": 15, "avg_consult_minutes": 35},
            {"name": "Tiny", "check_ins": 2, "avg_wait_minutes": 300},
        ],
        "hours": [{"hour": 10, "check_ins": 30}, {"hour": 11, "check_ins": 25}, {"hour": 15, "check_ins": 5}],
    }
    res = client.post("/ai/bottleneck", json=body, headers=AUTH).json()
    findings = [(f["severity"], f["department"], f["stage"]) for f in res["findings"]]
    assert set(findings[:2]) == {("high", "Outpatient", "targets"), ("high", "Outpatient", "waiting")}  # most severe first
    assert ("low", "Emergency", "called_to_seen") in findings and ("low", "Emergency", "consultation") in findings
    assert not any(d == "Tiny" for _, d, _ in findings), "too few visits to judge"
    peak = next(f for f in res["findings"] if f["stage"] == "demand")
    assert "10:00 (30 check-ins), 11:00 (25 check-ins)" in peak["message"]
    assert "70 min" in next(f for f in res["findings"] if f["stage"] == "waiting")["message"]


def test_health_lists_model_versions():
    models = client.get("/ai/health").json()["models"]
    assert models["risk_score"] == "news2-rcp-2017" and models["flow"].startswith("flow-stats")
