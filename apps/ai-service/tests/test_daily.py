from datetime import date

from fastapi.testclient import TestClient

from app.config import DEV_TOKEN
from app.daily import DailyCheckRequest, check
from app.main import app

client = TestClient(app)
AUTH = {"X-Internal-Token": DEV_TOKEN}


def run(**kwargs):
    return check(DailyCheckRequest(**{"feeling": 4, **kwargs}))


def topics(result):
    return [t.topic for t in result.tips]


def test_a_good_day_still_gets_a_tip():
    result = run(sleep_hours=8, water_glasses=8, day=date(2026, 11, 7))
    assert result.status == "good" and 1 <= len(result.tips) <= 6


def test_danger_signs_point_to_help_now():
    assert run(symptoms=["chest_pain"]).status == "urgent"
    assert run(symptoms=["breathless", "cough"]).status == "urgent"


def test_fever_means_come_in_and_mentions_recent_malaria():
    result = run(symptoms=["fever"])
    assert result.status == "see_clinic" and "malaria" in result.tips[0].text.lower()
    assert "treated for malaria recently" in run(symptoms=["fever"], recent_diagnoses=["Malaria, uncomplicated"]).tips[0].text


def test_fluids_and_watch_states():
    assert run(symptoms=["diarrhoea"]).status == "watch"
    assert run(symptoms=["diarrhoea", "vomiting"]).status == "see_clinic"
    assert run(feeling=1).status == "watch"


def test_personal_tips_from_medicines_conditions_and_habits():
    result = run(medicines=["Artemether-lumefantrine 20/120 mg"], chronic_conditions=["Asthma", "Sickle cell disease"],
                 sleep_hours=4.5, water_glasses=2, stress=5)
    assert {"Your medicine", "Asthma", "Sickle cell", "Sleep", "Water", "Stress"} <= set(topics(result))
    assert "finish the course" in result.tips[0].text
    assert "4.5 hours" in next(t.text for t in result.tips if t.topic == "Sleep")


def test_sickle_cell_with_pain_needs_the_clinic():
    assert run(symptoms=["body_aches"], chronic_conditions=["Sickle cell disease"]).status == "see_clinic"


def test_endpoint_validates_and_needs_the_token():
    body = {"feeling": 3, "symptoms": ["cough"]}
    assert client.post("/ai/daily-check", json=body).status_code == 401
    assert client.post("/ai/daily-check", json=body, headers=AUTH).json()["status"] == "watch"
    assert client.post("/ai/daily-check", json={"feeling": 9}, headers=AUTH).status_code == 422
    assert client.post("/ai/daily-check", json={"feeling": 3, "symptoms": ["zombie"]}, headers=AUTH).status_code == 422
