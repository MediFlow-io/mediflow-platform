from fastapi.testclient import TestClient

from app.config import DEV_TOKEN
from app.main import app
from app.prescribing import DrugSuggestionRequest, suggest

client = TestClient(app)
AUTH = {"X-Internal-Token": DEV_TOKEN}


def drugs(**kwargs):
    result = suggest(DrugSuggestionRequest(**kwargs))
    return [s.drug for s in result.suggestions], result


def test_malaria_gets_an_act_and_fever_relief():
    names, result = drugs(diagnoses=["Malaria, uncomplicated"])
    assert names == ["Artemether-lumefantrine 20/120 mg", "Paracetamol"]
    assert result.matched_conditions == ["Uncomplicated malaria"]
    assert result.suggestions[0].first_line and "6 doses" in result.suggestions[0].duration
    assert any("RDT" in n for n in result.notes)


def test_icd_codes_match_too():
    assert drugs(diagnoses=["B54"])[0][0].startswith("Artemether")
    assert drugs(diagnoses=["Acute tonsillitis (J03.9)"])[0][0] == "Amoxicillin"


def test_penicillin_allergy_swaps_amoxicillin_for_a_macrolide():
    names, result = drugs(diagnoses=["tonsillitis"], allergies="Penicillin (rash)")
    assert "Amoxicillin" not in names and "Azithromycin" in names
    assert result.excluded[0].drug == "Amoxicillin" and "penicillin" in result.excluded[0].reason


def test_an_allergy_to_the_drug_itself_or_its_class_excludes_it():
    assert "Artemether-lumefantrine 20/120 mg" not in drugs(diagnoses=["malaria"], allergies="coartem")[0]
    assert drugs(diagnoses=["dysmenorrhoea"], allergies="aspirin")[0] == ["Paracetamol"]
    assert "Amoxicillin" in drugs(diagnoses=["tonsillitis"], allergies="None")[0]


def test_pregnancy_and_long_term_conditions():
    names, result = drugs(diagnoses=["typhoid", "pneumonia"], allergies="penicillin, azithromycin", pregnant=True)
    assert "Ciprofloxacin" not in names and "Doxycycline" not in names
    assert any("every listed option is ruled out" in n for n in result.notes)
    names, _ = drugs(diagnoses=["period pain"], chronic_conditions=["Peptic ulcer disease"])
    assert names == ["Paracetamol"]
    _, result = drugs(diagnoses=["dysmenorrhoea"], chronic_conditions=["Asthma"])
    assert any("bronchospasm" in c for c in result.suggestions[0].cautions)


def test_no_misfires_on_similar_words():
    assert drugs(diagnoses=["Tension pneumothorax"])[0] == []
    assert drugs(diagnoses=["Corneal ulcer"])[0] == []
    assert drugs(diagnoses=["Hypertension"])[0] == ["Amlodipine"]


def test_children_and_unknown_diagnoses_get_no_suggestions():
    names, result = drugs(diagnoses=["malaria"], age_years=8)
    assert names == [] and "weight" in result.notes[0]
    names, result = drugs(diagnoses=["Fractured wrist"])
    assert names == [] and "No suggestions" in result.notes[0]


def test_endpoint_needs_the_internal_token_and_valid_input():
    body = {"diagnoses": ["malaria"], "allergies": ""}
    assert client.post("/ai/drug-suggestions", json=body).status_code == 401
    ok = client.post("/ai/drug-suggestions", json=body, headers=AUTH)
    assert ok.status_code == 200 and ok.json()["model_version"].startswith("formulary-")
    assert client.post("/ai/drug-suggestions", json={"diagnoses": []}, headers=AUTH).status_code == 422
    assert client.post("/ai/drug-suggestions", json={**body, "patient_name": "x"}, headers=AUTH).status_code == 422
