from datetime import date
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from users.models import GenderChoices, RoleChoices, StudentProfile, User


class UserModelTests(TestCase):
    def test_create_user_success(self):
        user = User.objects.create_user(
            unique_id='SEN/22/9269',
            email='student@mediflow.edu',
            password='StrongPassword123!',
            name='Jane Doe',
            role=RoleChoices.STUDENT
        )
        self.assertEqual(user.unique_id, 'SEN/22/9269')
        self.assertEqual(user.email, 'student@mediflow.edu')
        self.assertEqual(user.name, 'Jane Doe')
        self.assertEqual(user.role, RoleChoices.STUDENT)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('StrongPassword123!'))

    def test_create_superuser_success(self):
        admin_user = User.objects.create_superuser(
            unique_id='STAFF/ADMIN/001',
            email='admin@mediflow.org',
            password='SuperAdminPassword123!',
            name='Admin User'
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_active)
        self.assertEqual(admin_user.role, RoleChoices.ADMIN)

    def test_create_user_missing_unique_id(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                unique_id='',
                email='test@mediflow.org',
                password='StrongPassword123!',
                name='Test User'
            )

    def test_create_user_missing_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                unique_id='DOC/001',
                email='',
                password='StrongPassword123!',
                name='Test Doctor'
            )

    def test_create_superuser_missing_staff_flag(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                unique_id='STAFF/002',
                email='staff2@mediflow.org',
                password='StrongPassword123!',
                is_staff=False
            )

    def test_duplicate_unique_id_raises_integrity_error(self):
        User.objects.create_user(
            unique_id='NURSE/001',
            email='nurse1@mediflow.org',
            password='StrongPassword123!',
            name='Nurse One'
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                unique_id='NURSE/001',
                email='nurse2@mediflow.org',
                password='StrongPassword123!',
                name='Nurse Two'
            )

    def test_duplicate_email_raises_integrity_error(self):
        User.objects.create_user(
            unique_id='PHARM/001',
            email='pharmacy@mediflow.org',
            password='StrongPassword123!',
            name='Pharmacist One'
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                unique_id='PHARM/002',
                email='pharmacy@mediflow.org',
                password='StrongPassword123!',
                name='Pharmacist Two'
            )

    def test_health_card_number_generation_format_and_sequence(self):
        user1 = User.objects.create_user(
            unique_id='SEN/22/0001',
            email='u1@mediflow.edu',
            password='StrongPassword123!',
            name='Student One'
        )
        card1 = StudentProfile.generate_next_health_card_no(year=2026)
        self.assertEqual(card1, '0001/2026')

        StudentProfile.objects.create(
            user=user1,
            gender=GenderChoices.FEMALE,
            dob=date(2005, 5, 12),
            address='Dorm 1',
            department='Nursing',
            level='200',
            phone='08011111111',
            health_card_no=card1
        )

        card2 = StudentProfile.generate_next_health_card_no(year=2026)
        self.assertEqual(card2, '0002/2026')
