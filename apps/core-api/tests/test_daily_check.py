from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.ai import client as ai_client
from apps.emr.models import Diagnosis, Prescription
from apps.patients.models import Department, Patient, Visit
from apps.wellbeing.models import DailyCheckIn

FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
RESULT = {"status": "see_clinic", "headline": "Please come to the clinic today.",
          "tips": [{"topic": "Fever", "text": "Get tested."}], "disclaimer": "Not a diagnosis.", "model_version": "t"}


@FAST_HASHER
class DailyCheckTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="SEN/22/0001", password="safe-password-123", role="student")
        self.nurse = User.objects.create_user(username="nurse", password="safe-password-123", role="nurse")
        patient = Patient.objects.create(full_name="Synthetic Student", sex="Female", phone="0", user=self.student,
                                         chronic_conditions=["Asthma"])
        visit = Visit.objects.create(patient=patient, department=Department.objects.create(name="Outpatient", code="opd"))
        Diagnosis.objects.create(visit=visit, description="Malaria, uncomplicated")
        Prescription.objects.create(visit=visit, patient=patient, drug="Artemether-lumefantrine", dose="4 tablets", frequency="twice a day")

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    @mock.patch.object(ai_client, "call", return_value=RESULT)
    def test_check_in_uses_the_record_and_is_kept_once_per_day(self, call):
        client = self.as_user(self.student)
        res = client.post("/api/me/daily-check", {"feeling": 2, "symptoms": ["fever"], "sleep_hours": 5}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual((res.data["status"], res.data["tips"][0]["topic"]), ("see_clinic", "Fever"))
        payload = call.call_args.args[1]
        self.assertEqual(payload["medicines"], ["Artemether-lumefantrine"])
        self.assertEqual(payload["recent_diagnoses"], ["Malaria, uncomplicated"])
        self.assertEqual(payload["chronic_conditions"], ["Asthma"])
        self.assertNotIn("Synthetic Student", str(payload))
        client.post("/api/me/daily-check", {"feeling": 4}, format="json")
        self.assertEqual(DailyCheckIn.objects.count(), 1)
        today = client.get("/api/me/daily-check").data
        self.assertEqual((today["today"]["feeling"], len(today["week"])), (4, 1))

    @mock.patch.object(ai_client, "call", return_value=RESULT)
    def test_staff_without_a_record_can_check_in_and_only_see_their_own(self, call):
        self.as_user(self.student).post("/api/me/daily-check", {"feeling": 3}, format="json")
        res = self.as_user(self.nurse).post("/api/me/daily-check", {"feeling": 5}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertNotIn("medicines", call.call_args.args[1])
        self.assertEqual(self.as_user(self.nurse).get("/api/me/daily-check").data["today"]["feeling"], 5)

    def test_bad_answers_and_ai_down(self):
        client = self.as_user(self.student)
        self.assertEqual(client.post("/api/me/daily-check", {"feeling": 7}, format="json").status_code, 400)
        self.assertEqual(APIClient().get("/api/me/daily-check").status_code, 401)
        with mock.patch.object(ai_client, "call", side_effect=ai_client.AIUnavailable):
            self.assertEqual(client.post("/api/me/daily-check", {"feeling": 3}, format="json").status_code, 503)
        self.assertEqual(DailyCheckIn.objects.count(), 0)
