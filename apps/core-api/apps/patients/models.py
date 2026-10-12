import uuid
from django.conf import settings
from django.db import models

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=24, unique=True)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Patient(models.Model):
    class Sex(models.TextChoices): MALE = "Male", "Male"; FEMALE = "Female", "Female"; OTHER = "Other", "Other"
    hospital_number = models.CharField(max_length=32, unique=True, editable=False)
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=8, choices=Sex.choices)
    phone = models.CharField(max_length=30)
    address = models.TextField(blank=True)
    next_of_kin = models.CharField(max_length=200, blank=True)
    next_of_kin_phone = models.CharField(max_length=30, blank=True)
    allergies = models.TextField(blank=True)
    medical_history = models.TextField(blank=True)
    complaint = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def save(self, *args, **kwargs):
        if not self.hospital_number: self.hospital_number = f"MF-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    def __str__(self): return f"{self.hospital_number}: {self.full_name}"

class Visit(models.Model):
    class Status(models.TextChoices): WAITING = "waiting", "Waiting"; CALLED = "called", "Called"; IN_PROGRESS = "in_progress", "In progress"; COMPLETED = "completed", "Completed"; CANCELLED = "cancelled", "Cancelled"
    visit_number = models.CharField(max_length=36, unique=True, editable=False)
    patient = models.ForeignKey(Patient, related_name="visits", on_delete=models.PROTECT)
    department = models.ForeignKey(Department, related_name="visits", on_delete=models.PROTECT)
    esi = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAITING)
    arrival_mode = models.CharField(max_length=32, default="walk_in")
    checked_in_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_clinician = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_visits")
    class Meta: ordering = ("esi", "checked_in_at")
    def save(self, *args, **kwargs):
        if not self.visit_number: self.visit_number = f"V-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)
    def clean(self):
        from django.core.exceptions import ValidationError
        if not 1 <= self.esi <= 5: raise ValidationError({"esi": "ESI must be from 1 (most urgent) to 5."})
