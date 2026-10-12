import pytest
from fastapi.testclient import TestClient

from app.config import DEV_TOKEN
from app.main import app
from app.schemas import TriageRequest, Vitals
from app.triage import suggest_esi

client = TestClient(app)
AUTH = {"X-Internal-Token": DEV_TOKEN}
NORMAL = {"heart_rate": 80, "resp_rate": 16, "spo2": 98, "temperature_c": 36.8, "systolic_bp": 120, "avpu": "A"}


def esi(complaint="", age=25, pain=None, **vitals):
    return suggest_esi(TriageRequest(chief_complaint=complaint, age_years=age, pain_score=pain,
                                     vitals=Vitals(**{**NORMAL, **vitals})))


# --- triage rules ---------------------------------------------------------

@pytest.mark.parametrize("vitals", [{"avpu": "U"}, {"avpu": "P"}, {"spo2": 85}, {"systolic_bp": 70},
                                    {"heart_rate": 35}, {"resp_rate": 40}])
def test_life_threatening_vitals_suggest_esi_1(vitals):
    result = esi("feeling unwell", **vitals)
    assert result.suggested_esi == 1
    assert result.risk_level == "CRITICAL"


def test_life_threatening_complaint_suggests_esi_1():
    assert esi("Friend is not breathing").suggested_esi == 1


@pytest.mark.parametrize("complaint", ["chest pain since morning", "Slurred speech", "suicidal thoughts"])
def test_high_risk_complaints_suggest_esi_2(complaint):
    assert esi(complaint).suggested_esi == 2


def test_danger_zone_vitals_depend_on_age():
    # 130/min is danger-zone for an adult but normal for a 1-year-old.
    assert esi("cough", age=30, heart_rate=130).suggested_esi == 2
    assert esi("mild cough", age=1, heart_rate=130).suggested_esi == 5


def test_infant_fever_is_high_risk():
    assert esi("fever", age=0.1, temperature_c=38.2).suggested_esi == 2


def test_severe_pain_is_esi_2():
    assert esi("back pain", pain=8).suggested_esi == 2


def test_resource_based_levels():
    assert esi("abdominal pain").suggested_esi == 3
    assert esi("small cut on finger").suggested_esi == 4
    assert esi("prescription refill").suggested_esi == 5


def test_unknown_complaint_defaults_to_esi_3():
    assert esi("something odd").suggested_esi == 3


def test_missing_vitals_never_suggest_below_esi_3():
    result = suggest_esi(TriageRequest(chief_complaint="prescription refill"))
    assert result.suggested_esi == 3
    assert set(result.missing_vitals) == set(Vitals.CORE_VITALS)


def test_negation_errs_toward_over_triage():
    # Documented safety choice: keyword rules do not parse negation.
    assert esi("no chest pain").suggested_esi == 2


def test_every_suggestion_explains_itself():
    for complaint in ["chest pain", "cut", "unknown", "refill"]:
        assert esi(complaint).reasons


# --- API ------------------------------------------------------------------

def test_health_is_public():
    response = client.get("/ai/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize("path,body", [("/ai/triage", {"chief_complaint": "cut"}), ("/ai/ask", {"question": "burn"})])
def test_endpoints_require_internal_token(path, body):
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers={"X-Internal-Token": "wrong"}).status_code == 401


def test_triage_endpoint_response_contract():
    response = client.post("/ai/triage", headers=AUTH, json={
        "chief_complaint": "chest pain", "age_years": 50, "vitals": NORMAL})
    assert response.status_code == 200
    data = response.json()
    assert data["suggested_esi"] == 2
    assert data["requires_clinician_review"] is True
    assert data["method"] == "rules"
    assert "not a diagnosis" in data["disclaimer"]
    assert "confidence" not in data


def test_triage_rejects_out_of_range_vitals_and_unknown_fields():
    assert client.post("/ai/triage", headers=AUTH, json={"vitals": {"spo2": 150}}).status_code == 422
    assert client.post("/ai/triage", headers=AUTH, json={"patient_name": "x"}).status_code == 422


def test_ask_gives_first_aid_with_disclaimer():
    data = client.post("/ai/ask", headers=AUTH, json={"question": "What should I do for a burn?"}).json()
    assert data["topic"] == "burn"
    assert "20 minutes" in data["answer"]
    assert data["emergency"] is False
    assert "not medical advice" in data["disclaimer"]


def test_ask_escalates_emergencies():
    data = client.post("/ai/ask", headers=AUTH, json={"question": "my friend is choking"}).json()
    assert data["emergency"] is True
    assert data["answer"].startswith("This may be an emergency. Call 112")


def test_ask_refuses_doses_and_diagnosis():
    data = client.post("/ai/ask", headers=AUTH, json={"question": "how many mg of paracetamol should I take"}).json()
    assert data["topic"] == "out_of_scope"


def test_ask_does_not_match_inside_other_words():
    data = client.post("/ai/ask", headers=AUTH, json={"question": "how do I keep fit and execute workouts"}).json()
    assert data["topic"] == "unknown"


def test_ask_validates_length():
    assert client.post("/ai/ask", headers=AUTH, json={"question": ""}).status_code == 422
    assert client.post("/ai/ask", headers=AUTH, json={"question": "x" * 501}).status_code == 422


def test_metrics_exposed():
    client.get("/ai/health")
    assert "mediflow_ai_requests_total" in client.get("/metrics").text
