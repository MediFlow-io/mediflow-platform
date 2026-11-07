from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.emr.models import Prescription
from apps.operations.models import AuditLog
from apps.patients.models import Department, Patient, Visit

FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST_HASHER
class EmrTests(TestCase):
    def setUp(self):
        for role in ("admin", "doctor", "nurse", "reception", "lab", "pharmacy", "student"):
            User.objects.create_user(username=role, password="safe-password-123", role=role, display_name=role.title())
        self.opd = Department.objects.create(name="Outpatient", code="opd")
        self.student = User.objects.get(username="student")
        self.patient = Patient.objects.create(full_name="Synthetic Patient", sex="Female", phone="0", allergies="Penicillin",
                                              user=self.student, chronic_conditions=["Asthma"])
        self.visit = Visit.objects.create(patient=self.patient, department=self.opd, esi=3, status=Visit.Status.IN_PROGRESS)

    def as_user(self, username):
        client = APIClient()
        client.force_authenticate(User.objects.get(username=username))
        return client

    def url(self, path=""):
        return f"/api/emr/visits/{self.visit.id}{path}"

    def test_who_can_read_the_record(self):
        for role, code in [("doctor", 200), ("nurse", 200), ("admin", 200), ("reception", 403), ("lab", 403),
                           ("pharmacy", 403), ("student", 403)]:
            self.assertEqual(self.as_user(role).get(self.url()).status_code, code, role)
        self.assertEqual(APIClient().get(self.url()).status_code, 401)
        self.assertTrue(AuditLog.objects.filter(action="emr.visit_viewed", actor__username="doctor").exists())

    def test_consultation_notes_are_written_then_edited_and_never_audited_as_text(self):
        nurse, doctor = self.as_user("nurse"), self.as_user("doctor")
        res = nurse.put(self.url("/consultation"), {"notes": "Wheeze on exam."}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        res = doctor.put(self.url("/consultation"), {"notes": "Wheeze on exam. Plan: salbutamol."}, format="json")
        self.assertEqual((res.status_code, res.json()["clinician"], res.json()["updatedBy"]), (200, "Nurse", "Doctor"))
        self.assertEqual(self.as_user("reception").put(self.url("/consultation"), {"notes": "x"}, format="json").status_code, 403)
        self.assertEqual(doctor.put(self.url("/consultation"), {"notes": "  "}, format="json").status_code, 400)
        self.assertFalse(any("salbutamol" in str(log.details) for log in AuditLog.objects.all()))

    def test_diagnoses_primary_and_entered_in_error(self):
        doctor = self.as_user("doctor")
        self.assertEqual(self.as_user("nurse").post(self.url("/diagnoses"), {"description": "x"}, format="json").status_code, 403)
        first = doctor.post(self.url("/diagnoses"), {"description": "Asthma exacerbation", "code": "J45.901", "primary": True}, format="json").json()
        second = doctor.post(self.url("/diagnoses"), {"description": "Viral URTI", "primary": True}, format="json").json()
        record = doctor.get(self.url()).json()
        self.assertEqual([d["primary"] for d in record["diagnoses"]], [True, False])  # the newer primary wins
        self.assertEqual(record["diagnoses"][0]["id"], second["id"])
        res = doctor.post(f"/api/emr/diagnoses/{first['id']}/entered-in-error")
        self.assertEqual(res.json()["status"], "entered_in_error")
        self.assertEqual(len(doctor.get(self.url()).json()["diagnoses"]), 2, "never deleted")

    def test_prescribe_dispense_and_cancel(self):
        doctor, pharmacy = self.as_user("doctor"), self.as_user("pharmacy")
        body = {"drug": "Salbutamol inhaler", "dose": "2 puffs", "frequency": "as needed", "duration": "2 weeks",
                "instructions": "Shake before use"}
        rx = doctor.post(self.url("/prescriptions"), body, format="json").json()
        other = doctor.post(self.url("/prescriptions"), {"drug": "Paracetamol", "dose": "1 g", "frequency": "every 6 hours"}, format="json").json()
        self.assertEqual(self.as_user("nurse").post(self.url("/prescriptions"), body, format="json").status_code, 403)

        work = pharmacy.get("/api/emr/prescriptions").json()
        self.assertEqual([(p["drug"], p["allergies"]) for p in work], [("Salbutamol inhaler", "Penicillin"), ("Paracetamol", "Penicillin")])
        self.assertEqual(self.as_user("reception").get("/api/emr/prescriptions").status_code, 403)

        self.assertEqual(doctor.post(f"/api/emr/prescriptions/{rx['id']}/dispense").status_code, 403, "only pharmacy dispenses")
        res = pharmacy.post(f"/api/emr/prescriptions/{rx['id']}/dispense")
        self.assertEqual((res.status_code, res.json()["status"], res.json()["dispensed_by"]), (200, "dispensed", "Pharmacy"))
        self.assertEqual(pharmacy.post(f"/api/emr/prescriptions/{rx['id']}/dispense").status_code, 409)
        self.assertEqual(doctor.post(f"/api/emr/prescriptions/{other['id']}/cancel", {}, format="json").status_code, 400)
        self.assertEqual(doctor.post(f"/api/emr/prescriptions/{other['id']}/cancel", {"reason": "Duplicate"}, format="json").json()["status"], "cancelled")
        self.assertEqual(doctor.post(f"/api/emr/prescriptions/{other['id']}/delete").status_code, 404)
        self.assertEqual(pharmacy.get("/api/emr/prescriptions?status=dispensed").json()[0]["id"], rx["id"])
        self.assertEqual(pharmacy.get("/api/emr/prescriptions?status=bogus").status_code, 400)

        # The patient sees what to take (not cancelled ones), and nothing about why.
        meds = self.as_user("student").get("/api/me/medications").json()
        self.assertEqual([(m["drug"], m["status"], m["instructions"]) for m in meds["medications"]],
                         [("Salbutamol inhaler", "dispensed", "Shake before use")])
        self.assertNotIn("diagnosis", str(meds).lower())

    def test_referral_admission_and_discharge(self):
        doctor, nurse = self.as_user("doctor"), self.as_user("nurse")
        res = doctor.post(self.url("/referrals"), {"destination": "FMC Owo, chest clinic", "reason": "Poor control", "urgency": "urgent"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(nurse.post(self.url("/admission"), {}, format="json").status_code, 400)
        self.assertEqual(nurse.post(self.url("/admission"), {"ward": "Observation bay 2"}, format="json").status_code, 201)
        self.assertEqual(nurse.post(self.url("/admission"), {"ward": "Again"}, format="json").status_code, 409)
        self.assertEqual(nurse.post(self.url("/discharge"), {"summary": "Settled with nebuliser."}, format="json").status_code, 200)
        self.assertEqual(nurse.post(self.url("/discharge"), {"summary": "Again"}, format="json").status_code, 409)
        self.assertEqual(nurse.post(self.url("/explode"), {}, format="json").status_code, 404)
        record = doctor.get(self.url()).json()
        self.assertEqual(record["referrals"][0]["urgency"], "urgent")
        self.assertEqual(record["admission"]["ward"], "Observation bay 2")
        self.assertIsNotNone(record["admission"]["dischargedAt"])

    def test_cancelled_visits_take_no_records_and_history_lists_all_visits(self):
        cancelled = Visit.objects.create(patient=self.patient, department=self.opd, esi=4, status=Visit.Status.CANCELLED)
        doctor = self.as_user("doctor")
        res = doctor.post(f"/api/emr/visits/{cancelled.id}/diagnoses", {"description": "x"}, format="json")
        self.assertEqual(res.status_code, 400)
        doctor.post(self.url("/diagnoses"), {"description": "Asthma"}, format="json")
        history = doctor.get(f"/api/emr/patients/{self.patient.id}/history").json()
        self.assertEqual(history["patient"]["chronicConditions"], ["Asthma"])
        self.assertEqual(len(history["visits"]), 2)
        self.assertEqual(self.as_user("pharmacy").get(f"/api/emr/patients/{self.patient.id}/history").status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action="emr.history_viewed").exists())

    def test_patient_payment_and_chronic_conditions(self):
        reception = self.as_user("reception")
        res = reception.patch(f"/api/patients/{self.patient.id}", {"paymentCategory": "insurance", "insuranceNumber": "NHIA-123",
                                                                     "chronicConditions": [" Asthma ", "asthma", "Sickle cell disease", ""]}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["chronicConditions"], ["Asthma", "Sickle cell disease"])
        self.assertEqual((res.json()["paymentCategory"], res.json()["insuranceNumber"]), ("insurance", "NHIA-123"))
        self.assertEqual(reception.patch(f"/api/patients/{self.patient.id}", {"paymentCategory": "barter"}, format="json").status_code, 400)
        self.assertEqual(Prescription.objects.count(), 0)
