from datetime import date
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.ai import client as ai_client
from apps.emr.models import Diagnosis
from apps.operations.models import AuditLog
from apps.patients.models import Department, Patient, Visit

FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
RESULT = {"matched_conditions": ["Uncomplicated malaria"], "suggestions": [{"drug": "Artemether-lumefantrine 20/120 mg"}],
          "excluded": [], "notes": [], "model_version": "formulary-test"}


@FAST_HASHER
class DrugSuggestionTests(TestCase):
    def setUp(self):
        for role in ("doctor", "nurse"):
            User.objects.create_user(username=role, password="safe-password-123", role=role)
        opd = Department.objects.create(name="Outpatient", code="opd")
        self.patient = Patient.objects.create(full_name="Synthetic Patient", sex="Female", phone="0", allergies="Penicillin",
                                              chronic_conditions=["Asthma"], date_of_birth=date(2004, 1, 1))
        self.visit = Visit.objects.create(patient=self.patient, department=opd, status=Visit.Status.IN_PROGRESS)
        Diagnosis.objects.create(visit=self.visit, description="Malaria, uncomplicated", code="B54")
        Diagnosis.objects.create(visit=self.visit, description="Wrong", status=Diagnosis.Status.ENTERED_IN_ERROR)

    def as_user(self, username):
        client = APIClient()
        client.force_authenticate(User.objects.get(username=username))
        return client

    @mock.patch.object(ai_client, "call", return_value=RESULT)
    def test_doctor_gets_suggestions_without_identifiers_being_sent(self, call):
        res = self.as_user("doctor").post("/api/ai/drug-suggestions", {"visit": self.visit.id, "diagnoses": ["Headache"], "pregnant": True}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        path, payload = call.call_args.args
        self.assertEqual(path, "/ai/drug-suggestions")
        self.assertEqual(payload["diagnoses"], ["Malaria, uncomplicated (B54)", "Headache"])
        self.assertEqual((payload["allergies"], payload["chronic_conditions"], payload["pregnant"]), ("Penicillin", ["Asthma"], True))
        self.assertIsInstance(payload["age_years"], int)
        self.assertNotIn("Synthetic Patient", str(payload))
        self.assertNotIn(self.patient.hospital_number, str(payload))
        self.assertTrue(AuditLog.objects.filter(action="ai.drugs_suggested").exists())

    @mock.patch.object(ai_client, "call", return_value=RESULT)
    def test_only_doctors_and_only_with_a_diagnosis(self, call):
        self.assertEqual(self.as_user("nurse").post("/api/ai/drug-suggestions", {"visit": self.visit.id}, format="json").status_code, 403)
        Diagnosis.objects.all().delete()
        self.assertEqual(self.as_user("doctor").post("/api/ai/drug-suggestions", {"visit": self.visit.id}, format="json").status_code, 400)
        self.assertEqual(self.as_user("doctor").post("/api/ai/drug-suggestions", {"visit": self.visit.id, "diagnoses": "x"}, format="json").status_code, 400)
        self.assertEqual(self.as_user("doctor").post("/api/ai/drug-suggestions", {"visit": 99999, "diagnoses": ["x"]}, format="json").status_code, 404)
        call.assert_not_called()

    @mock.patch.object(ai_client, "call", side_effect=ai_client.AIUnavailable)
    def test_ai_down_is_a_clear_503(self, call):
        self.assertEqual(self.as_user("doctor").post("/api/ai/drug-suggestions", {"visit": self.visit.id}, format="json").status_code, 503)
