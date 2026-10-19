from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.ai import client as ai_client
from apps.ai.insights import flow_numbers
from apps.operations.models import AuditLog
from apps.patients.models import Department, Patient, Visit

PASSWORD = "safe-password-123"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AiInsightTests(TestCase):
    def setUp(self):
        for role in ("admin", "nurse", "reception"):
            User.objects.create_user(username=role, password=PASSWORD, role=role)
        self.opd = Department.objects.create(name="Outpatient", code="opd")
        self.patient = Patient.objects.create(full_name="Synthetic", sex="Female", phone="0")

    def as_user(self, username):
        client = APIClient()
        client.force_authenticate(User.objects.get(username=username))
        return client

    def visit(self, status, wait=None, call=None, consult=None, esi=3, ago_minutes=120):
        t0 = timezone.now() - timedelta(minutes=ago_minutes)
        v = Visit.objects.create(patient=self.patient, department=self.opd, esi=esi, status=status)
        called = t0 + timedelta(minutes=wait) if wait is not None else None
        started = called + timedelta(minutes=call) if called and call is not None else None
        completed = started + timedelta(minutes=consult) if started and consult is not None else None
        Visit.objects.filter(pk=v.pk).update(checked_in_at=t0, called_at=called, started_at=started, completed_at=completed)
        return v

    @mock.patch.object(ai_client, "call", return_value={"score": 5, "risk": "medium", "model_version": "news2-rcp-2017"})
    def test_risk_score_for_clinical_staff_only_and_only_vitals_are_sent(self, call):
        body = {"vitals": {"heart_rate": 120}, "on_oxygen": True, "patient": 7, "chief_complaint": "private"}
        self.assertEqual(self.as_user("reception").post("/api/ai/risk-score", body, format="json").status_code, 403)
        res = self.as_user("nurse").post("/api/ai/risk-score", body, format="json")
        self.assertEqual(res.json()["risk"], "medium")
        call.assert_called_once_with("/ai/risk-score", {"vitals": {"heart_rate": 120}, "on_oxygen": True})
        log = AuditLog.objects.get(action="ai.risk_scored")
        self.assertEqual(log.details["score"], 5)

    def test_flow_numbers_are_aggregates(self):
        self.visit(Visit.Status.COMPLETED, wait=20, call=5, consult=10)
        self.visit(Visit.Status.COMPLETED, wait=40, call=5, consult=20, esi=4)
        self.visit(Visit.Status.WAITING)
        self.visit(Visit.Status.COMPLETED, wait=5, call=1, consult=5, ago_minutes=20 * 24 * 60)  # outside 14 days
        n = flow_numbers()
        [opd] = n["departments"]
        self.assertEqual((opd["check_ins"], opd["waiting_now"], opd["clinicians_now"]), (3, 1, 1))
        self.assertEqual((opd["avg_wait_minutes"], opd["avg_call_to_start_minutes"], opd["avg_consult_minutes"]), (30.0, 5.0, 15.0))
        self.assertEqual(opd["seen_within_target_percent"], 100.0)  # ESI 3 in 20 ≤ 30; ESI 4 in 40 ≤ 60
        self.assertEqual(sorted(n["service_minutes"]["Outpatient"]), [10.0, 20.0])
        self.assertNotIn("clinicians_now", n["bottleneck_departments"][0])
        self.assertNotIn("Synthetic", str(n))

    def test_insights_for_admins_combine_ai_answers(self):
        self.visit(Visit.Status.WAITING)

        def fake(path, payload):
            if path == "/ai/bottleneck":
                return {"findings": [{"severity": "high", "department": "Outpatient", "stage": "waiting", "message": "m"}],
                        "model_version": "flow-stats-test"}
            return {"estimates": [{"name": q["name"], "expected_minutes": 15, "low_minutes": 5, "high_minutes": 25,
                                   "confidence": "low"} for q in payload["queues"]]}

        with mock.patch.object(ai_client, "call", side_effect=fake) as call:
            self.assertEqual(self.as_user("nurse").get("/api/ai/insights").status_code, 403)
            res = self.as_user("admin").get("/api/ai/insights").json()
        self.assertEqual(res["departments"][0]["expectedWaitForNewArrival"]["high_minutes"], 25)
        self.assertEqual(res["departments"][0]["waitingNow"], 1)
        self.assertEqual(res["findings"][0]["stage"], "waiting")
        wait_calls = [c for c in call.call_args_list if c.args[0] == "/ai/wait-time"]
        self.assertEqual(len(wait_calls), 1, "one call for all departments")
        self.assertEqual(wait_calls[0].args[1]["queues"][0]["ahead"], 1)

    @mock.patch.object(ai_client, "call", side_effect=ai_client.AIUnavailable)
    def test_insights_say_when_the_ai_service_is_down(self, _):
        self.assertEqual(self.as_user("admin").get("/api/ai/insights").status_code, 503)
