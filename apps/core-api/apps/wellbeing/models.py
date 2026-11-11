from django.conf import settings
from django.db import models


class DailyCheckIn(models.Model):
    """One person's daily health check-in: their answers and the tips they were given. One per day."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_checkins")
    day = models.DateField()
    feeling = models.PositiveSmallIntegerField()        # 1 = very unwell ... 5 = great
    answers = models.JSONField(default=dict)             # sleep, water, stress, symptoms
    status = models.CharField(max_length=12)             # good, watch, see_clinic, urgent
    result = models.JSONField(default=dict)              # headline and tips shown
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-day",)
        constraints = [models.UniqueConstraint(fields=["user", "day"], name="one_checkin_per_day")]
