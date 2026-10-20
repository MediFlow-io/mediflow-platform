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
    # Optional login account (e.g. a student) that may view this record via /api/me/health.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="patient_record")
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
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_clinician = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_visits")
    # Triage observations recorded at check-in (written by the Go patient-flow service; schema owned here).
    chief_complaint = models.TextField(blank=True, default="")
    pain_score = models.PositiveSmallIntegerField(null=True, blank=True)
    heart_rate = models.PositiveSmallIntegerField(null=True, blank=True)      # beats/min
    resp_rate = models.PositiveSmallIntegerField(null=True, blank=True)       # breaths/min
    spo2 = models.PositiveSmallIntegerField(null=True, blank=True)            # %
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    systolic_bp = models.PositiveSmallIntegerField(null=True, blank=True)     # mmHg
    avpu = models.CharField(max_length=1, blank=True, default="")             # A, V, P or U
    ACTIVE_STATUSES = (Status.WAITING, Status.CALLED, Status.IN_PROGRESS)
    class Meta: ordering = ("esi", "checked_in_at")
    def save(self, *args, **kwargs):
        if not self.visit_number: self.visit_number = f"V-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)
    def clean(self):
        from django.core.exceptions import ValidationError
        if not 1 <= self.esi <= 5: raise ValidationError({"esi": "ESI must be from 1 (most urgent) to 5."})

class Appointment(models.Model):
    """A booked or requested clinic slot. Written by the Go patient-flow service (ADR-0002); schema owned here.

    requested ──confirm──▶ confirmed ──check-in──▶ checked_in (a Visit is created)
        │──decline──▶ declined        │
        └────────────cancel───────────┴──▶ cancelled
    """
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"; CONFIRMED = "confirmed", "Confirmed"; DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"; CHECKED_IN = "checked_in", "Checked in"
    reference = models.CharField(max_length=12, unique=True)
    patient = models.ForeignKey(Patient, related_name="appointments", on_delete=models.PROTECT)
    department = models.ForeignKey(Department, related_name="appointments", on_delete=models.PROTECT)
    scheduled_for = models.DateTimeField()
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED)
    staff_note = models.TextField(blank=True, default="")  # shown to the patient, e.g. why a request was declined
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="appointments_requested")
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="appointments_handled")
    visit = models.OneToOneField(Visit, null=True, blank=True, on_delete=models.SET_NULL, related_name="appointment")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ("scheduled_for",)
        indexes = [models.Index(fields=["status", "scheduled_for"])]
