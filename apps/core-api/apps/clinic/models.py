"""Clinic settings: opening hours, holidays, queue rules and staff shifts.

Stored here (Django owns the schema and the API); edited from the Laravel admin console; read by the Go
patient-flow service for appointment slots and queue targets, and by the notification service.
Weekdays use 0 = Sunday … 6 = Saturday, the same as Go's time.Weekday and PostgreSQL's EXTRACT(DOW).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
WEEKDAY_CHOICES = list(enumerate(WEEKDAYS))


class ServiceHours(models.Model):
    """When a department takes appointments. Rows with no department are the clinic-wide default.
    A department with no rows of its own uses the default; a weekday with no row is closed."""
    department = models.ForeignKey("patients.Department", null=True, blank=True, on_delete=models.CASCADE,
                                   related_name="service_hours")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    opens = models.TimeField()
    closes = models.TimeField()

    class Meta:
        ordering = ("department_id", "weekday")
        constraints = [
            models.UniqueConstraint(fields=["department", "weekday"], name="clinic_hours_one_per_day"),
            models.UniqueConstraint(fields=["weekday"], condition=models.Q(department__isnull=True),
                                    name="clinic_default_hours_one_per_day"),
            models.CheckConstraint(condition=models.Q(closes__gt=models.F("opens")), name="clinic_hours_close_after_open"),
        ]

    def clean(self):
        if self.opens and self.closes and self.closes <= self.opens:
            raise ValidationError({"closes": "Closing time must be after opening time."})


class Holiday(models.Model):
    """The whole clinic is closed for appointments on this date."""
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ("date",)


class QueueSettings(models.Model):
    """One row (id = 1). Targets are the longest a patient of each ESI level should wait to be seen."""
    esi1_target_minutes = models.PositiveSmallIntegerField(default=0)
    esi2_target_minutes = models.PositiveSmallIntegerField(default=10)
    esi3_target_minutes = models.PositiveSmallIntegerField(default=30)
    esi4_target_minutes = models.PositiveSmallIntegerField(default=60)
    esi5_target_minutes = models.PositiveSmallIntegerField(default=120)
    # Waiting longer than this triggers a long-delay notification (patient) and shows on the dashboard.
    long_wait_minutes = models.PositiveSmallIntegerField(default=60)
    # "Your turn is near" when this many patients or fewer are ahead.
    turn_near_ahead = models.PositiveSmallIntegerField(default=2)
    slot_minutes = models.PositiveSmallIntegerField(default=15)
    max_days_ahead = models.PositiveSmallIntegerField(default=60)
    min_notice_minutes = models.PositiveSmallIntegerField(default=15)
    max_open_appointments = models.PositiveSmallIntegerField(default=3)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "QueueSettings":
        return cls.objects.get_or_create(pk=1)[0]


class StaffShift(models.Model):
    """When a staff member works, by weekday. Used for "doctors available" and the doctor-schedule view."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shifts")
    department = models.ForeignKey("patients.Department", on_delete=models.CASCADE, related_name="shifts")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    starts = models.TimeField()
    ends = models.TimeField()

    class Meta:
        ordering = ("weekday", "starts")
        constraints = [models.CheckConstraint(condition=models.Q(ends__gt=models.F("starts")), name="clinic_shift_ends_after_start")]
