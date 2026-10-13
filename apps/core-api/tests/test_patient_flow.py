from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
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

    def check_in(self, patient=None, esi=3, client=None):
        response = (client or self.as_user("reception")).post(
            "/api/visits", {"patient": (patient or self.patient).id, "department": self.opd.id, "esi": esi}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data


class VisitLifecycleTests(FlowTestCase):
    def test_full_flow_sets_timestamps_and_clinician(self):
        visit = self.check_in()
        self.assertEqual(self.as_user("reception").post(f"/api/visits/{visit['id']}/call").data["status"], "called")
        started = self.as_user("nurse").post(f"/api/visits/{visit['id']}/start").data
        self.assertEqual((started["status"], started["assigned_clinician_name"]), ("in_progress", "Nurse"))
        done = self.as_user("doctor").post(f"/api/visits/{visit['id']}/complete").data
        self.assertEqual(done["status"], "completed")
        self.assertTrue(done["called_at"] and done["started_at"] and done["completed_at"])
        actions = list(AuditLog.objects.filter(entity_type="visit").values_list("action", flat=True))
        self.assertEqual(sorted(actions), ["visit.call", "visit.checked_in", "visit.complete", "visit.start"])

    def test_invalid_transition_is_409(self):
        visit = self.check_in()
        response = self.as_user("doctor").post(f"/api/visits/{visit['id']}/complete")
        self.assertEqual(response.status_code, 409)
        self.assertIn("waiting", response.data["detail"])

    def test_roles_per_transition(self):
        visit = self.check_in()
        self.assertEqual(self.as_user("reception").post(f"/api/visits/{visit['id']}/start").status_code, 403)
        self.assertEqual(self.as_user("lab").post(f"/api/visits/{visit['id']}/call").status_code, 403)
        self.assertEqual(self.as_user("student").post(f"/api/visits/{visit['id']}/cancel").status_code, 403)
        self.assertEqual(self.as_user("reception").post(f"/api/visits/{visit['id']}/cancel").data["status"], "cancelled")

    def test_status_cannot_be_patched_directly(self):
        visit = self.check_in()
        self.as_user("admin").patch(f"/api/visits/{visit['id']}", {"status": "completed"}, format="json")
        self.assertEqual(Visit.objects.get(pk=visit["id"]).status, "waiting")

    def test_one_active_visit_per_patient(self):
        self.check_in()
        response = self.as_user("reception").post(
            "/api/visits", {"patient": self.patient.id, "department": self.opd.id, "esi": 3}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("active visit", str(response.data))

    def test_unknown_visit_is_404(self):
        self.assertEqual(self.as_user("doctor").post("/api/visits/999999/start").status_code, 404)

    def test_visit_filters(self):
        visit = self.check_in()
        other = Patient.objects.create(full_name="Other", sex="Male", phone="1")
        second = self.check_in(other)
        self.as_user("reception").post(f"/api/visits/{second['id']}/call")
        waiting = self.as_user("doctor").get("/api/visits?status=waiting&department=opd&today=true").data
        self.assertEqual([v["id"] for v in waiting], [visit["id"]])


class QueueAndDashboardTests(FlowTestCase):
    def test_queue_reports_real_wait_and_position(self):
        visit = self.check_in(esi=3)
        Visit.objects.filter(pk=visit["id"]).update(checked_in_at=timezone.now() - timedelta(minutes=25))
        urgent = self.check_in(Patient.objects.create(full_name="Urgent", sex="Male", phone="2"), esi=1)
        queue = self.as_user("nurse").get("/api/queue").data
        self.assertEqual([q["id"] for q in queue], [urgent["id"], visit["id"]])
        self.assertEqual(queue[1]["position"], 2)
        self.assertGreaterEqual(queue[1]["waitingMinutes"], 25)
        self.assertEqual(queue[1]["wait"], f"{queue[1]['waitingMinutes']} min")

    def test_dashboard_metrics_come_from_records(self):
        first = self.check_in()
        Visit.objects.filter(pk=first["id"]).update(checked_in_at=timezone.now() - timedelta(minutes=30))
        self.as_user("reception").post(f"/api/visits/{first['id']}/call")
        self.as_user("doctor").post(f"/api/visits/{first['id']}/start")
        self.check_in(Patient.objects.create(full_name="Second", sex="Male", phone="3"), esi=2)
        data = self.as_user("doctor").get("/api/dashboard").data
        self.assertEqual((data["patientsToday"], data["currentlyWaiting"], data["inConsultation"], data["emergencyCases"]),
                         (2, 1, 1, 1))
        self.assertGreaterEqual(data["averageWaitMinutes"], 30)
        self.assertEqual(data["byStatus"], {"in_progress": 1, "waiting": 1})


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
