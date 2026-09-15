from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .managers import CustomUserManager

# 11-digit phone number validator
phone_regex_validator = RegexValidator(
    regex=r'^\d{11}$',
    message="Phone number must be exactly 11 digits."
)


class RoleChoices(models.TextChoices):
    ADMIN = 'Admin', 'Admin'
    DOCTOR = 'Doctor', 'Doctor'
    NURSE = 'Nurse', 'Nurse'
    RECEPTION = 'Reception', 'Reception'
    LAB = 'Lab', 'Lab'
    PHARMACY = 'Pharmacy', 'Pharmacy'
    IT = 'IT', 'IT'
    STUDENT = 'Student', 'Student'


class GenderChoices(models.TextChoices):
    MALE = 'Male', 'Male'
    FEMALE = 'Female', 'Female'
    OTHER = 'Other', 'Other'


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for MediFlow hospital backend.
    Uses unique_id (Matric No or Staff ID) as the USERNAME_FIELD.
    """
    unique_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Matriculation number for students or Staff ID for personnel (e.g. SEN/22/9269 or 2018002)."
    )
    name = models.CharField(max_length=255, help_text="Full Name")
    email = models.EmailField(unique=True, db_index=True, help_text="Unique email address")
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.STUDENT,
        help_text="Role within the MediFlow hospital system"
    )

    # Standard flags
    is_active = models.BooleanField(default=True, help_text="Designates whether this user account is active.")
    is_staff = models.BooleanField(default=False, help_text="Designates whether the user can log into the admin site.")
    is_superuser = models.BooleanField(default=False, help_text="Designates whether the user has all permissions.")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'unique_id'
    REQUIRED_FIELDS = ['email', 'name']

    objects = CustomUserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.unique_id} - {self.name} ({self.role})"


class StudentProfile(models.Model):
    """
    Detailed profile information specific to student patients registered in MediFlow.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    gender = models.CharField(max_length=10, choices=GenderChoices.choices)
    dob = models.DateField(help_text="Date of birth (must be at least 16 years old)")
    address = models.TextField(help_text="Residential or campus address")
    department = models.CharField(max_length=100, help_text="Academic department")
    level = models.CharField(max_length=20, help_text="Academic level (e.g. 100, 200, 300, 400, 500)")
    phone = models.CharField(max_length=11, help_text="11-digit phone number")
    health_card_no = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Auto-generated Health Card Number formatted as <number>/<registration_year>"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.name} - Health Card: {self.health_card_no}"

    @classmethod
    def generate_next_health_card_no(cls, year=None):
        """
        Generates the next unique health card number in format: <number>/<registration_year>
        E.g., 0001/2026, 0002/2026.
        """
        if year is None:
            year = timezone.now().year

        suffix = f"/{year}"
        records = cls.objects.filter(health_card_no__endswith=suffix).values_list('health_card_no', flat=True)
        max_num = 0
        for record in records:
            parts = record.split('/')
            if len(parts) == 2 and parts[1] == str(year):
                try:
                    num = int(parts[0])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue

        next_num = max_num + 1
        candidate = f"{next_num:04d}/{year}"
        while cls.objects.filter(health_card_no=candidate).exists():
            next_num += 1
            candidate = f"{next_num:04d}/{year}"

        return candidate


class StaffProfile(models.Model):
    """
    Profile information specific to hospital personnel (Doctors, Nurses, Admins, etc.)
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )
    name = models.CharField(max_length=255, help_text="Staff full name")
    gender = models.CharField(max_length=10, choices=GenderChoices.choices)
    department = models.CharField(
        max_length=100,
        help_text="Hospital department (e.g. Cardiology, IT, General Practice, Pharmacy, Lab)"
    )
    phone_number = models.CharField(
        max_length=11,
        validators=[phone_regex_validator],
        help_text="11-digit phone number"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.user.unique_id}) - {self.department}"
