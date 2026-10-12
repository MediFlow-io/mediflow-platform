from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.patients.models import Department, Patient, Visit

class CoreApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="safe-password", role="admin", is_staff=True)
        self.doctor = User.objects.create_user(username="doctor", password="safe-password", role="doctor")
        self.department = Department.objects.create(name="Outpatient", code="opd")
        self.client = APIClient()

    def login(self, username="admin"):
        response = self.client.post("/api/login", {"staffId": username, "password": "safe-password"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_frontend_login_contract(self):
        self.login()
        self.assertEqual(self.client.get("/api/me").data["role"], "admin")

    def test_patient_crud_contract_uses_camel_case_fields(self):
        self.login()
        created = self.client.post("/api/patients", {"fullName": "Amina Yusuf", "sex": "Female", "phone": "08000000000", "medicalHistory": "None"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.data["hospitalNumber"].startswith("MF-"))
        self.assertEqual(self.client.get(f"/api/patients/{created.data['id']}").data["fullName"], "Amina Yusuf")

    def test_queue_is_esi_then_fcfs(self):
        first = Patient.objects.create(full_name="First", sex="Male", phone="1")
        urgent = Patient.objects.create(full_name="Urgent", sex="Female", phone="2")
        Visit.objects.create(patient=first, department=self.department, esi=3)
        Visit.objects.create(patient=urgent, department=self.department, esi=1)
        self.login()
        queue = self.client.get("/api/queue").data
        self.assertEqual([item["fullName"] for item in queue], ["Urgent", "First"])
