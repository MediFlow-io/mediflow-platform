from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        DOCTOR = "doctor", "Doctor"
        NURSE = "nurse", "Nurse / Triage"
        RECEPTION = "reception", "Reception"
        LAB = "lab", "Laboratory"
        PHARMACY = "pharmacy", "Pharmacy"
        IT = "it", "IT"
        STUDENT = "student", "Student"
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.RECEPTION)
    display_name = models.CharField(max_length=150, blank=True)

    @property
    def can_manage_users(self):
        return self.role == self.Role.ADMIN
