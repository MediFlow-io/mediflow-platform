from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.operations.audit import record
from apps.operations.models import AuditLog


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuditLogApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="x-safe-password", role="admin")
        self.nurse = User.objects.create_user(username="nurse", password="x-safe-password", role="nurse")
        record(self.nurse, "patient.viewed", "patient", 7)
        record(self.nurse, "patient.updated", "patient", 7, fields=["allergies"])
        record(self.admin, "auth.login", "user", self.admin.id)
        old = record(None, "auth.login_failed", "user", "ghost") or AuditLog.objects.latest("id")
        AuditLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_admin_only(self):
        self.assertEqual(APIClient().get("/api/audit-logs").status_code, 401)
        self.assertEqual(self.client_for(self.nurse).get("/api/audit-logs").status_code, 403)

    def test_lists_newest_first_with_actor_and_pagination(self):
        data = self.client_for(self.admin).get("/api/audit-logs?page_size=2").data
        self.assertEqual(data["count"], 4)
        self.assertEqual(len(data["results"]), 2)
        self.assertIsNotNone(data["next"])
        first = data["results"][0]
        self.assertEqual((first["action"], first["actor"], first["actor_role"]), ("auth.login", "admin", "admin"))

    def test_filters(self):
        client = self.client_for(self.admin)
        actions = lambda q: [r["action"] for r in client.get(f"/api/audit-logs?{q}").data["results"]]
        self.assertEqual(actions("action=patient."), ["patient.updated", "patient.viewed"])
        self.assertEqual(actions("actor=nurse&entity_id=7"), ["patient.updated", "patient.viewed"])
        today = timezone.localdate().isoformat()
        self.assertNotIn("auth.login_failed", actions(f"since={today}&until={today}"))
        self.assertEqual(client.get("/api/audit-logs?since=13-10-2026").status_code, 400)

    def test_viewing_the_log_is_audited(self):
        self.client_for(self.admin).get("/api/audit-logs?action=patient.")
        entry = AuditLog.objects.filter(action="audit.viewed").get()
        self.assertEqual((entry.actor, entry.details), (self.admin, {"filters": {"action": "patient."}}))

    def test_department_changes_are_audited(self):
        client = self.client_for(self.admin)
        created = client.post("/api/departments", {"name": "Dental", "code": "dental"}, format="json")
        self.assertEqual(created.status_code, 201)
        client.patch(f"/api/departments/{created.data['id']}", {"active": False}, format="json")
        actions = list(AuditLog.objects.filter(entity_type="department").values_list("action", flat=True))
        self.assertEqual(sorted(actions), ["department.created", "department.updated"])
