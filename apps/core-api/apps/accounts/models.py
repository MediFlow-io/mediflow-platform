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


class TotpDevice(models.Model):
    """An authenticator app (TOTP) for two-factor sign-in. Unconfirmed until the first code is checked."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="totp_device")
    secret = models.CharField(max_length=64)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    # The last accepted time step, so a code can't be used twice.
    last_step = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
