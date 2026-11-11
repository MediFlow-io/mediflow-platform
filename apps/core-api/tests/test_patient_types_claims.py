import csv
import io
from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.emr.models import Diagnosis, Prescription
from apps.operations.models import AuditLog
from apps.patients.models import Department, Patient, Visit

FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST_HASHER
class PatientTypeTests(TestCase):
    def setUp(self):
        self.reception = User.objects.create_user(username="reception", password="safe-password-123", role="reception")
        self.client = APIClient()
        self.client.force_authenticate(self.reception)

    def create(self, **fields):
        return self.client.post("/api/patients", {"fullName": "Synthetic Patient", "sex": "Female", "phone": "0", **fields}, format="json")

    def test_students_and_staff_have_their_own_fields(self):
        res = self.create(patientType="student", schoolId="SEN/22/9269", unit="Software Engineering", level="300")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual((res.data["patientType"], res.data["schoolId"], res.data["level"]), ("student", "SEN/22/9269", "300"))
        staff = self.create(patientType="staff", schoolId="STF/0042", unit="Bursary")
        self.assertEqual(staff.status_code, 201, staff.content)
        self.assertEqual(self.create(patientType="staff", level="300").status_code, 400)  # only students have a level
        self.assertEqual(self.create().data["patientType"], "visitor")

    def test_search_finds_matric_and_insurance_numbers(self):
        self.create(patientType="student", schoolId="SEN/22/9269")
        self.create(paymentCategory="insurance", insuranceScheme="tiship", insuranceNumber="TS-1234")
        for query in ("SEN/22", "TS-12"):
            self.assertEqual(len(self.client.get("/api/patients", {"search": query}).data), 1, query)

    def test_insured_patients_need_a_number_and_show_cover_status(self):
        missing = self.create(paymentCategory="insurance")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("insuranceNumber", missing.data)
        today = timezone.localdate()
        expired = self.create(paymentCategory="insurance", insuranceScheme="nhia", insuranceNumber="NHIA-1",
                              hmoName="Example HMO", insuranceExpires=(today - timedelta(days=1)).isoformat())
        self.assertEqual(expired.data["insuranceStatus"], "expired")
        renewed = self.client.patch(f"/api/patients/{expired.data['id']}", {"insuranceExpires": (today + timedelta(days=30)).isoformat()}, format="json")
        self.assertEqual(renewed.data["insuranceStatus"], "active")
        # A partial update still checks the record as a whole.
        self.assertEqual(self.client.patch(f"/api/patients/{expired.data['id']}", {"insuranceNumber": ""}, format="json").status_code, 400)
        self.assertEqual(self.create(paymentCategory="cash").data["insuranceStatus"], "none")
        self.assertEqual(Patient(payment_category="insurance").insurance_status(date(2026, 1, 1)), "unknown")


@FAST_HASHER
class InsuranceClaimsTests(TestCase):
    def setUp(self):
        for role in ("admin", "reception", "doctor", "student"):
            User.objects.create_user(username=role, password="safe-password-123", role=role, display_name=role.title())
        opd = Department.objects.create(name="Outpatient", code="opd")
        insured = Patient.objects.create(full_name="Insured Student", sex="Female", phone="0", payment_category="insurance",
                                         insurance_scheme="tiship", insurance_number="TS-1", hmo_name="Example HMO")
        cash = Patient.objects.create(full_name="Cash Patient", sex="Male", phone="0", payment_category="cash")
        now = timezone.now()
        doctor = User.objects.get(username="doctor")
        self.claim = Visit.objects.create(patient=insured, department=opd, status=Visit.Status.COMPLETED, completed_at=now,
                                          assigned_clinician=doctor)
        Diagnosis.objects.create(visit=self.claim, description="Malaria, uncomplicated", code="B54")
        Diagnosis.objects.create(visit=self.claim, description="Wrong one", status=Diagnosis.Status.ENTERED_IN_ERROR)
        Prescription.objects.create(visit=self.claim, patient=insured, drug="Artemether-lumefantrine", dose="80/480 mg",
                                    frequency="twice a day", duration="3 days")
        Prescription.objects.create(visit=self.claim, patient=insured, drug="Cancelled drug", dose="1", frequency="once",
                                    status=Prescription.Status.CANCELLED)
        Visit.objects.create(patient=insured, department=opd, status=Visit.Status.WAITING)              # not finished
        Visit.objects.create(patient=cash, department=opd, status=Visit.Status.COMPLETED, completed_at=now)  # not insured

    def as_user(self, username):
        client = APIClient()
        client.force_authenticate(User.objects.get(username=username))
        return client

    def test_only_admin_and_front_desk_export(self):
        for role, code in [("admin", 200), ("reception", 200), ("doctor", 403), ("student", 403)]:
            self.assertEqual(self.as_user(role).get("/api/claims/insurance").status_code, code, role)

    def test_one_row_per_completed_insured_visit(self):
        res = self.as_user("reception").get("/api/claims/insurance")
        self.assertEqual(res.data["count"], 1)
        row = res.data["claims"][0]
        self.assertEqual(row["visitNumber"], self.claim.visit_number)
        self.assertEqual((row["enrolmentNumber"], row["scheme"], row["hmo"]), ("TS-1", "TISHIP (tertiary students)", "Example HMO"))
        self.assertEqual(row["diagnoses"], "Malaria, uncomplicated (B54)")
        self.assertEqual(row["prescriptions"], "Artemether-lumefantrine 80/480 mg twice a day 3 days")
        self.assertEqual(row["clinician"], "Doctor")
        self.assertEqual(self.as_user("admin").get("/api/claims/insurance", {"scheme": "nhia"}).data["count"], 0)

    def test_csv_download_and_audit(self):
        res = self.as_user("admin").get("/api/claims/insurance", {"download": "csv"})
        self.assertEqual(res["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", res["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(res.content.decode())))
        self.assertEqual(rows[0][0], "Date of service")
        self.assertEqual(rows[1][4], "TS-1")
        log = AuditLog.objects.get(action="claims.exported")
        self.assertEqual(log.details["visits"], 1)
        self.assertNotIn("Malaria", str(log.details))

    def test_bad_periods_are_refused(self):
        client = self.as_user("admin")
        self.assertEqual(client.get("/api/claims/insurance", {"from": "30-11-2026"}).status_code, 400)
        self.assertEqual(client.get("/api/claims/insurance", {"from": "2026-11-02", "to": "2026-11-01"}).status_code, 400)
        self.assertEqual(client.get("/api/claims/insurance", {"from": "2024-01-01", "to": "2026-01-01"}).status_code, 400)
        self.assertEqual(client.get("/api/claims/insurance", {"scheme": "nope"}).status_code, 400)
