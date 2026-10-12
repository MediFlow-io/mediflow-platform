from datetime import date, timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import GenderChoices, RoleChoices, StudentProfile, User


class AuthenticationAPITests(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth:register-student')
        self.staff_register_url = reverse('auth:register-staff')
        self.login_url = reverse('auth:login')
        self.token_refresh_url = reverse('auth:token-refresh')
        self.logout_url = reverse('auth:logout')
        self.change_password_url = reverse('auth:change-password')

        self.student_payload = {
            'name': 'Johnathan Doe',
            'unique_id': 'SEN/22/9269',
            'email': 'john.doe@mediflow.edu',
            'password': 'SecureHospitalPass2026!',
            'gender': 'Male',
            'dob': '2004-03-15',
            'address': 'Hall 4, Block B, University Campus',
            'department': 'Software Engineering',
            'level': '300',
            'phone': '08012345678',
        }

    def test_student_registration_success(self):
        response = self.client.post(self.register_url, self.student_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('health_card_no', response.data)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['unique_id'], 'SEN/22/9269')
        self.assertEqual(response.data['role'], 'Student')
        current_year = timezone.now().year
        self.assertTrue(response.data['health_card_no'].endswith(f"/{current_year}"))

        # Verify database
        user = User.objects.get(unique_id='SEN/22/9269')
        self.assertTrue(user.check_password(self.student_payload['password']))
        self.assertEqual(user.student_profile.department, 'Software Engineering')
        self.assertEqual(user.student_profile.phone, '08012345678')

    def test_student_registration_underage(self):
        # Student age 14
        underage_date = (timezone.now().date() - timedelta(days=14 * 365)).isoformat()
        payload = self.student_payload.copy()
        payload['unique_id'] = 'SEN/22/9999'
        payload['email'] = 'underage@mediflow.edu'
        payload['dob'] = underage_date

        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('dob', response.data)

    def test_student_registration_invalid_matric_format(self):
        payload = self.student_payload.copy()
        payload['unique_id'] = 'INVALID_MATRIC'
        payload['email'] = 'invalid@mediflow.edu'

        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unique_id', response.data)

    def test_student_registration_invalid_phone_number(self):
        payload = self.student_payload.copy()
        payload['unique_id'] = 'SEN/22/1010'
        payload['email'] = 'phone@mediflow.edu'
        payload['phone'] = '12345'  # not 11 digits

        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_student_registration_weak_password(self):
        payload = self.student_payload.copy()
        payload['unique_id'] = 'SEN/22/2020'
        payload['email'] = 'weak@mediflow.edu'
        payload['password'] = '123'

        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_login_success(self):
        # First register student
        self.client.post(self.register_url, self.student_payload, format='json')

        login_payload = {
            'unique_id': 'SEN/22/9269',
            'password': 'SecureHospitalPass2026!',
        }
        response = self.client.post(self.login_url, login_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('role', response.data)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['role'], 'Student')
        self.assertEqual(response.data['unique_id'], 'SEN/22/9269')

    def test_login_invalid_password(self):
        self.client.post(self.register_url, self.student_payload, format='json')

        login_payload = {
            'unique_id': 'SEN/22/9269',
            'password': 'WrongPassword123!',
        }
        response = self.client.post(self.login_url, login_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)

    def test_login_nonexistent_user(self):
        login_payload = {
            'unique_id': 'NON/00/0000',
            'password': 'SomePassword123!',
        }
        response = self.client.post(self.login_url, login_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        self.client.post(self.register_url, self.student_payload, format='json')
        login_res = self.client.post(
            self.login_url,
            {'unique_id': 'SEN/22/9269', 'password': 'SecureHospitalPass2026!'},
            format='json'
        )
        refresh_token = login_res.data['refresh']

        refresh_res = self.client.post(self.token_refresh_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_res.data)

    def test_logout_and_token_blacklist(self):
        self.client.post(self.register_url, self.student_payload, format='json')
        login_res = self.client.post(
            self.login_url,
            {'unique_id': 'SEN/22/9269', 'password': 'SecureHospitalPass2026!'},
            format='json'
        )
        access_token = login_res.data['access']
        refresh_token = login_res.data['refresh']

        # Logout requires Bearer token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_res = self.client.post(self.logout_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)
        self.assertEqual(logout_res.data['detail'], 'Successfully logged out.')

        # Attempting to refresh with the blacklisted token should fail with 401
        second_refresh_res = self.client.post(self.token_refresh_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(second_refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_unauthenticated(self):
        self.client.credentials()  # clear auth
        response = self.client.post(self.logout_url, {'refresh': 'dummy_token'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_success(self):
        self.client.post(self.register_url, self.student_payload, format='json')
        login_res = self.client.post(
            self.login_url,
            {'unique_id': 'SEN/22/9269', 'password': 'SecureHospitalPass2026!'},
            format='json'
        )
        access_token = login_res.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        change_payload = {
            'old_password': 'SecureHospitalPass2026!',
            'new_password': 'BrandNewHospitalPass99!',
            'confirm_password': 'BrandNewHospitalPass99!',
        }
        res = self.client.post(self.change_password_url, change_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['detail'], 'Password changed successfully.')

        # Try logging in with old password (should fail)
        old_login = self.client.post(
            self.login_url,
            {'unique_id': 'SEN/22/9269', 'password': 'SecureHospitalPass2026!'},
            format='json'
        )
        self.assertEqual(old_login.status_code, status.HTTP_401_UNAUTHORIZED)

        # Login with new password (should succeed)
        new_login = self.client.post(
            self.login_url,
            {'unique_id': 'SEN/22/9269', 'password': 'BrandNewHospitalPass99!'},
            format='json'
        )
        self.assertEqual(new_login.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old_password(self):
        self.client.post(self.register_url, self.student_payload, format='json')
        login_res = self.client.post(
            self.login_url,
            {'unique_id': 'SEN/22/9269', 'password': 'SecureHospitalPass2026!'},
            format='json'
        )
        access_token = login_res.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        change_payload = {
            'old_password': 'IncorrectOldPassword!',
            'new_password': 'BrandNewHospitalPass99!',
            'confirm_password': 'BrandNewHospitalPass99!',
        }
        res = self.client.post(self.change_password_url, change_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('old_password', res.data)

    def test_change_password_mismatch(self):
        self.client.post(self.register_url, self.student_payload, format='json')
        login_res = self.client.post(
            self.login_url,
            {'unique_id': 'SEN/22/9269', 'password': 'SecureHospitalPass2026!'},
            format='json'
        )
        access_token = login_res.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        change_payload = {
            'old_password': 'SecureHospitalPass2026!',
            'new_password': 'BrandNewHospitalPass99!',
            'confirm_password': 'DifferentHospitalPass99!',
        }
        res = self.client.post(self.change_password_url, change_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', res.data)

    def test_staff_registration_by_admin_success(self):
        # Create an admin user
        admin_user = User.objects.create_user(
            unique_id='STAFF/ADMIN/01',
            email='admin@mediflow.org',
            password='AdminPassword123!',
            name='Hospital Admin',
            role=RoleChoices.ADMIN,
            is_staff=True
        )
        refresh = RefreshToken.for_user(admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        staff_payload = {
            'unique_id': '2018002',
            'email': 'doctor.smith@mediflow.org',
            'password': 'DoctorPassword123!',
            'role': 'Doctor',
            'name': 'Dr. Sarah Smith',
            'gender': 'Female',
            'department': 'Cardiology',
            'phone_number': '08012345678',
        }
        response = self.client.post(self.staff_register_url, staff_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['unique_id'], '2018002')
        self.assertEqual(response.data['role'], 'Doctor')
        self.assertIn('profile', response.data)
        self.assertEqual(response.data['profile']['department'], 'Cardiology')
        self.assertEqual(response.data['profile']['phone_number'], '08012345678')

        # Verify database
        user = User.objects.get(unique_id='2018002')
        self.assertEqual(user.role, RoleChoices.DOCTOR)
        self.assertEqual(user.staff_profile.name, 'Dr. Sarah Smith')
        self.assertEqual(user.staff_profile.department, 'Cardiology')

    def test_staff_registration_by_superuser_success(self):
        super_user = User.objects.create_superuser(
            unique_id='SUPER/01',
            email='super@mediflow.org',
            password='SuperPassword123!',
            name='Super Administrator'
        )
        refresh = RefreshToken.for_user(super_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        staff_payload = {
            'unique_id': '2018003',
            'email': 'nurse.mary@mediflow.org',
            'password': 'NursePassword123!',
            'role': 'Nurse',
            'name': 'Mary Johnson',
            'gender': 'Female',
            'department': 'Emergency',
            'phone_number': '08098765432',
        }
        response = self.client.post(self.staff_register_url, staff_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['unique_id'], '2018003')
        self.assertEqual(response.data['role'], 'Nurse')

    def test_staff_registration_by_non_admin_forbidden(self):
        # Register a normal student
        self.client.post(self.register_url, self.student_payload, format='json')
        login_res = self.client.post(
            self.login_url,
            {'unique_id': 'SEN/22/9269', 'password': 'SecureHospitalPass2026!'},
            format='json'
        )
        access_token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        staff_payload = {
            'unique_id': '2018004',
            'email': 'hacker.staff@mediflow.org',
            'password': 'SomePassword123!',
            'role': 'Doctor',
            'name': 'Fake Doctor',
            'gender': 'Male',
            'department': 'IT',
            'phone_number': '08012345678',
        }
        response = self.client.post(self.staff_register_url, staff_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_registration_unauthenticated(self):
        self.client.credentials()  # Clear auth
        staff_payload = {
            'unique_id': '2018005',
            'email': 'anon@mediflow.org',
            'password': 'SomePassword123!',
            'role': 'Doctor',
            'name': 'Anonymous Doc',
            'gender': 'Male',
            'department': 'General Practice',
            'phone_number': '08012345678',
        }
        response = self.client.post(self.staff_register_url, staff_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_registration_disallow_student_role(self):
        admin_user = User.objects.create_user(
            unique_id='STAFF/ADMIN/02',
            email='admin2@mediflow.org',
            password='AdminPassword123!',
            name='Hospital Admin Two',
            role=RoleChoices.ADMIN,
            is_staff=True
        )
        refresh = RefreshToken.for_user(admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        staff_payload = {
            'unique_id': '2018006',
            'email': 'badstudent@mediflow.org',
            'password': 'SecureHospitalPass2026!',
            'role': 'Student',
            'name': 'Student as Staff',
            'gender': 'Male',
            'department': 'Pharmacy',
            'phone_number': '08012345678',
        }
        response = self.client.post(self.staff_register_url, staff_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)

    def test_staff_registration_invalid_phone(self):
        admin_user = User.objects.create_user(
            unique_id='STAFF/ADMIN/03',
            email='admin3@mediflow.org',
            password='AdminPassword123!',
            name='Hospital Admin Three',
            role=RoleChoices.ADMIN,
            is_staff=True
        )
        refresh = RefreshToken.for_user(admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        staff_payload = {
            'unique_id': '2018007',
            'email': 'badphone@mediflow.org',
            'password': 'SecureHospitalPass2026!',
            'role': 'Lab',
            'name': 'Lab Scientist',
            'gender': 'Male',
            'department': 'Haematology',
            'phone_number': '080123',  # Less than 11 digits
        }
        response = self.client.post(self.staff_register_url, staff_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)

