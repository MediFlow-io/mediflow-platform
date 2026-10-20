"""Notification tables. Written only by the Flask notification service (apps/notifications, ADR-0002);
the schema lives here so there is one migration history."""
from django.conf import settings
from django.db import models


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications", on_delete=models.CASCADE)
    kind = models.CharField(max_length=40)          # e.g. visit.called, appointment.confirmed
    title = models.CharField(max_length=140)
    body = models.TextField(blank=True, default="")
    link = models.CharField(max_length=40, blank=True, default="")  # where the app should open, e.g. "appointments"
    # Stops the same event producing the same notification twice (retries, several listeners).
    dedupe_key = models.CharField(max_length=120, unique=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["recipient", "read_at", "created_at"])]


class Delivery(models.Model):
    """One attempt to send a notification over a channel other than in-app."""
    notification = models.ForeignKey(Notification, related_name="deliveries", on_delete=models.CASCADE)
    channel = models.CharField(max_length=10)       # email, sms
    status = models.CharField(max_length=10)        # sent, failed, skipped
    detail = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField()
