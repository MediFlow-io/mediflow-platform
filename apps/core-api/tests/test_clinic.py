from datetime import date, timedelta

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.clinic.models import Holiday, QueueSettings, ServiceHours, StaffShift
from apps.operations.models import AuditLog
from apps.patients.models import Department

FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST_HASHER
class ClinicSettingsTests(TestCase):
    def setUp(self):
        for role in ("admin", "doctor", "nurse", "student"):
            User.objects.create_user(username=role, password="safe-password-123", role=role, display_name=role.title())
        self.opd = Department.objects.create(name="Outpatient", code="opd")

    def as_user(self, username):
        client = APIClient()
        client.force_authenticate(User.objects.get(username=username))
        return client

    def test_everyone_signed_in_reads_settings_but_only_admins_change_them(self):
        self.assertEqual(APIClient().get("/api/clinic/settings").status_code, 401)
        student = self.as_user("student")
        data = student.get("/api/clinic/settings").json()
        self.assertEqual(data["queue"]["esi2_target_minutes"], 10)
        self.assertNotIn("onDutyNow", data)  # staffing is for staff
        self.assertEqual(student.put("/api/clinic/queue-settings", {"long_wait_minutes": 5}, format="json").status_code, 403)
        self.assertEqual(self.as_user("doctor").post("/api/clinic/holidays", {"date": "2030-01-01", "name": "x"}, format="json").status_code, 403)

    def test_admin_updates_queue_settings_and_it_is_audited(self):
        admin = self.as_user("admin")
        res = admin.put("/api/clinic/queue-settings", {"long_wait_minutes": 45, "esi3_target_minutes": 20}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        settings = QueueSettings.load()
        self.assertEqual((settings.long_wait_minutes, settings.esi3_target_minutes, settings.esi2_target_minutes), (45, 20, 10))
        self.assertEqual(QueueSettings.objects.count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="settings.queue_updated").exists())
        self.assertEqual(admin.put("/api/clinic/queue-settings", {"slot_minutes": 7}, format="json").status_code, 400)

    def test_hours_replace_a_week_per_department(self):
        admin = self.as_user("admin")
        week = [{"weekday": d, "opens": "08:00", "closes": "16:00"} for d in range(1, 6)]
        self.assertEqual(admin.put("/api/clinic/hours", {"department": None, "days": week}, format="json").status_code, 200)
        friday_short = [{"weekday": 5, "opens": "08:00", "closes": "12:00"}]
        res = admin.put("/api/clinic/hours", {"department": self.opd.id, "days": friday_short}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()[0]["day"], "Fri")
        self.assertEqual(ServiceHours.objects.filter(department=None).count(), 5)
        self.assertEqual(ServiceHours.objects.filter(department=self.opd).count(), 1)
        # Replacing, not appending; an empty week removes the department's own hours.
        admin.put("/api/clinic/hours", {"department": self.opd.id, "days": []}, format="json")
        self.assertFalse(ServiceHours.objects.filter(department=self.opd).exists())

    def test_hours_validation(self):
        admin = self.as_user("admin")
        bad = {"department": None, "days": [{"weekday": 1, "opens": "16:00", "closes": "08:00"}]}
        self.assertEqual(admin.put("/api/clinic/hours", bad, format="json").status_code, 400)
        twice = {"department": None, "days": [{"weekday": 1, "opens": "08:00", "closes": "09:00"}] * 2}
        self.assertEqual(admin.put("/api/clinic/hours", twice, format="json").status_code, 400)
        self.assertEqual(admin.put("/api/clinic/hours", {"department": None, "days": [{"weekday": 7, "opens": "08:00", "closes": "09:00"}]}, format="json").status_code, 400)

    def test_holidays(self):
        admin = self.as_user("admin")
        future = date.today() + timedelta(days=10)
        res = admin.post("/api/clinic/holidays", {"date": future.isoformat(), "name": "Founders' Day"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        Holiday.objects.create(date=date.today() - timedelta(days=30), name="Past")
        self.assertEqual(admin.post("/api/clinic/holidays", {"date": future.isoformat(), "name": "Twice"}, format="json").status_code, 400)
        self.assertEqual([h["name"] for h in self.as_user("student").get("/api/clinic/settings").json()["holidays"]], ["Founders' Day"])
        self.assertEqual(len(admin.get("/api/clinic/holidays?upcoming=1").json()), 1)
        self.assertEqual(admin.delete(f"/api/clinic/holidays/{res.json()['id']}").status_code, 204)
        self.assertTrue(AuditLog.objects.filter(action="settings.holiday_removed").exists())

    def test_shifts_and_on_duty_counts(self):
        admin = self.as_user("admin")
        doctor = User.objects.get(username="doctor")
        res = admin.post("/api/clinic/shifts", {"user": doctor.id, "department": self.opd.id, "weekday": 1,
                                                "starts": "08:00", "ends": "14:00"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual((res.json()["day"], res.json()["role"]), ("Mon", "doctor"))
        student = User.objects.get(username="student")
        self.assertEqual(admin.post("/api/clinic/shifts", {"user": student.id, "department": self.opd.id, "weekday": 1,
                                                           "starts": "08:00", "ends": "14:00"}, format="json").status_code, 400)
        self.assertEqual(self.as_user("student").get("/api/clinic/shifts").status_code, 403)
        self.assertEqual(len(self.as_user("nurse").get("/api/clinic/shifts?weekday=1").json()), 1)
        # A shift covering all of today makes the doctor "on duty now".
        from django.utils import timezone
        today = (timezone.localtime().weekday() + 1) % 7
        StaffShift.objects.create(user=doctor, department=self.opd, weekday=today, starts="00:00", ends="23:59:59")
        self.assertEqual(self.as_user("nurse").get("/api/clinic/settings").json()["onDutyNow"], {"doctor": 1})
