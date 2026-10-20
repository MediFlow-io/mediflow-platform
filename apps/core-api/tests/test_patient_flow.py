from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.operations.models import AuditLog
from apps.patients.models import Department, Patient, Visit

PASSWORD = "safe-password-123"
FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST_HASHER
class FlowTestCase(TestCase):
    def setUp(self):
        cache.clear()
        for role in ("admin", "doctor", "nurse", "reception", "lab", "student"):
            User.objects.create_user(username=role, password=PASSWORD, role=role, display_name=role.title())
        self.opd = Department.objects.create(name="Outpatient", code="opd")
        self.patient = Patient.objects.create(full_name="Synthetic Patient", sex="Female", phone="0")

    def as_user(self, username):
        client = APIClient()
        client.force_authenticate(User.objects.get(username=username))
        return client

    def check_in(self, patient=None, esi=3):
        # Visits are written by the Go patient-flow service; tests create them directly.
        visit = Visit.objects.create(patient=patient or self.patient, department=self.opd, esi=esi)
        return {"id": visit.id, "visit_number": visit.visit_number}


class PatientAuditAndLinkTests(FlowTestCase):
    def test_reads_and_writes_are_audited_without_search_text(self):
        client = self.as_user("doctor")
        client.get("/api/patients?search=Synthetic")
        client.get(f"/api/patients/{self.patient.id}")
        client.patch(f"/api/patients/{self.patient.id}", {"allergies": "Penicillin"}, format="json")
        logs = {log.action: log for log in AuditLog.objects.filter(entity_type="patient")}
        self.assertEqual(set(logs), {"patient.listed", "patient.viewed", "patient.updated"})
        self.assertEqual(logs["patient.listed"].details, {"results": 1, "searched": True})
        self.assertNotIn("Synthetic", str([log.details for log in logs.values()]))
        self.assertEqual(logs["patient.updated"].details["fields"], ["allergies"])

    def test_link_account_and_student_sees_only_own_record(self):
        response = self.as_user("reception").patch(
            f"/api/patients/{self.patient.id}", {"linkedAccount": "student"}, format="json")
        self.assertEqual(response.data["linkedAccountName"], "student")
        visit = self.check_in()
        self.check_in(Patient.objects.create(full_name="Ahead", sex="Male", phone="4"), esi=1)

        data = self.as_user("student").get("/api/me/health").data
        self.assertTrue(data["linked"])
        self.assertEqual(data["patient"]["fullName"], "Synthetic Patient")
        self.assertNotIn("diagnosis", data["patient"])
        self.assertEqual(data["activeVisit"]["visitNumber"], visit["visit_number"])
        self.assertEqual(data["activeVisit"]["patientsAhead"], 1)
        self.assertEqual(len(data["visits"]), 1)
        # Students still cannot browse the patient list.
        self.assertEqual(self.as_user("student").get("/api/patients").status_code, 403)

    def test_unlinked_account_gets_empty_record(self):
        data = self.as_user("student").get("/api/me/health").data
        self.assertEqual((data["linked"], data["patient"], data["visits"]), (False, None, []))

    def test_account_cannot_be_linked_twice(self):
        self.patient.user = User.objects.get(username="student")
        self.patient.save()
        other = Patient.objects.create(full_name="Other", sex="Male", phone="5")
        response = self.as_user("reception").patch(f"/api/patients/{other.id}", {"linkedAccount": "student"}, format="json")
        self.assertEqual(response.status_code, 400)


@FAST_HASHER
class StudentVitalsTests(FlowTestCase):
    def test_latest_vitals_are_shown_without_complaint_text(self):
        self.patient.user = User.objects.get(username="student")
        self.patient.save()
        Visit.objects.create(patient=self.patient, department=self.opd, esi=3, status="completed",
                             chief_complaint="private words", heart_rate=80, temperature_c="37.2")
        data = self.as_user("student").get("/api/me/health").data
        self.assertEqual(data["latestVitals"]["heartRate"], 80)
        self.assertEqual(data["latestVitals"]["temperatureC"], 37.2)
        self.assertIsNone(data["latestVitals"]["spo2"])
        self.assertNotIn("private words", str(data))

    def test_no_vitals_recorded(self):
        self.patient.user = User.objects.get(username="student")
        self.patient.save()
        self.check_in()
        self.assertIsNone(self.as_user("student").get("/api/me/health").data["latestVitals"])


@FAST_HASHER
class SecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(username="admin", password=PASSWORD, role="admin")

    def test_login_is_rate_limited_per_username(self):
        client = APIClient()
        codes = [client.post("/api/auth/login", {"unique_id": "admin", "password": "wrong"}, format="json").status_code
                 for _ in range(11)]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10], 429)
        # A different username from the same address is not blocked.
        other = client.post("/api/auth/login", {"unique_id": "someone", "password": "x"}, format="json")
        self.assertEqual(other.status_code, 401)

    def test_weak_passwords_are_rejected_at_registration(self):
        for password in ("short", "12345678901", "password123"):
            response = APIClient().post("/api/auth/register/student", {"unique_id": f"s-{password}", "password": password}, format="json")
            self.assertEqual(response.status_code, 400, password)

    def test_staff_management_deactivates_instead_of_deleting(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        created = client.post("/api/users", {"username": "doc2", "role": "doctor", "password": PASSWORD}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(client.post("/api/users", {"username": "nopass", "role": "doctor"}, format="json").status_code, 400)
        self.assertEqual(client.delete(f"/api/users/{created.data['id']}").status_code, 405)
        self.assertFalse(client.patch(f"/api/users/{created.data['id']}", {"is_active": False}, format="json").data["is_active"])
        self.assertEqual(client.patch(f"/api/users/{self.admin.id}", {"is_active": False}, format="json").status_code, 400)
        self.assertEqual([u["username"] for u in client.get("/api/users?role=doctor&active=false").data], ["doc2"])
