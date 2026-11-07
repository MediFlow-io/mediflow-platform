"""EMR Lite: the clinical record of a visit. Deliberately small (see docs/handbook): what a campus health
centre needs to treat, prescribe, refer and admit, nothing more.

Records are never deleted. Mistakes are marked "entered in error" (diagnoses) or "cancelled"
(prescriptions), so the history of what was recorded stays intact. Every read and write is audited.
"""
from django.conf import settings
from django.db import models

from apps.patients.models import Patient, Visit

USER = settings.AUTH_USER_MODEL


class Consultation(models.Model):
    """The clinician's notes for a visit (history, examination, plan). One per visit, edited in place."""
    visit = models.OneToOneField(Visit, on_delete=models.PROTECT, related_name="consultation")
    notes = models.TextField()
    clinician = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")


class Diagnosis(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENTERED_IN_ERROR = "entered_in_error", "Entered in error"

    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name="diagnoses")
    description = models.CharField(max_length=200)
    code = models.CharField(max_length=16, blank=True, default="")  # optional ICD-10, e.g. J06.9
    primary = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    recorded_by = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-primary", "created_at")


class Prescription(models.Model):
    class Status(models.TextChoices):
        PRESCRIBED = "prescribed", "Prescribed"
        DISPENSED = "dispensed", "Dispensed"
        CANCELLED = "cancelled", "Cancelled"

    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name="prescriptions")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="prescriptions")  # for pharmacy lists
    drug = models.CharField(max_length=120)
    dose = models.CharField(max_length=60)              # e.g. 500 mg
    route = models.CharField(max_length=30, default="oral")
    frequency = models.CharField(max_length=60)         # e.g. three times a day
    duration = models.CharField(max_length=60, blank=True, default="")  # e.g. 5 days
    instructions = models.CharField(max_length=300, blank=True, default="")  # shown to the patient
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PRESCRIBED)
    prescribed_by = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    dispensed_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    dispensed_at = models.DateTimeField(null=True, blank=True)
    cancelled_reason = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ("created_at",)


class Referral(models.Model):
    class Urgency(models.TextChoices):
        ROUTINE = "routine", "Routine"
        URGENT = "urgent", "Urgent"
        EMERGENCY = "emergency", "Emergency"

    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name="referrals")
    destination = models.CharField(max_length=200)     # hospital, specialist or service
    reason = models.TextField()
    urgency = models.CharField(max_length=10, choices=Urgency.choices, default=Urgency.ROUTINE)
    referred_by = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class Admission(models.Model):
    """Observation / sick-bay admission from a visit, until discharge."""
    visit = models.OneToOneField(Visit, on_delete=models.PROTECT, related_name="admission")
    ward = models.CharField(max_length=60)
    admitted_by = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")
    admitted_at = models.DateTimeField(auto_now_add=True)
    discharged_at = models.DateTimeField(null=True, blank=True)
    discharged_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    discharge_summary = models.TextField(blank=True, default="")
