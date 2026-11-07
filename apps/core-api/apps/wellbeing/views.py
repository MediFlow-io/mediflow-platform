"""GET / POST /api/me/daily-check: the signed-in person's daily health check-in (students and staff).

POST sends the answers; the AI service turns them, plus what the record says (current medicines, long-term
conditions, diagnoses from the last 14 days), into tips. Checking in again the same day replaces the answer.
GET returns today's result (if any) and the last 7 days. Only ever the caller's own check-ins.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai import client
from apps.ai.views import AIThrottle, UNAVAILABLE
from apps.operations.audit import record

from .models import DailyCheckIn

ANSWERS = ("sleep_hours", "water_glasses", "stress", "symptoms")


def out(checkin):
    return {"day": checkin.day, "feeling": checkin.feeling, "status": checkin.status, **checkin.result,
            "answers": checkin.answers}


def context_for(user):
    """What the record adds to the check-in. Clinical text stays general: no names or identifiers."""
    from apps.emr.models import Diagnosis, Prescription
    from apps.patients.models import Patient

    patient = Patient.objects.filter(user=user).first()
    if patient is None:
        return {}
    since = timezone.now() - timedelta(days=14)
    medicines = (Prescription.objects.filter(patient=patient, created_at__gte=since)
                 .exclude(status=Prescription.Status.CANCELLED).values_list("drug", flat=True)[:10])
    diagnoses = (Diagnosis.objects.filter(visit__patient=patient, created_at__gte=since)
                 .exclude(status=Diagnosis.Status.ENTERED_IN_ERROR).values_list("description", flat=True)[:10])
    return {"medicines": list(medicines), "chronic_conditions": list(patient.chronic_conditions or [])[:20],
            "recent_diagnoses": list(diagnoses)}


class DailyCheckView(APIView):
    throttle_classes = [AIThrottle]

    def get(self, request):
        today = timezone.localdate()
        recent = list(DailyCheckIn.objects.filter(user=request.user, day__gt=today - timedelta(days=7)))
        todays = next((c for c in recent if c.day == today), None)
        return Response({"today": out(todays) if todays else None,
                         "week": [{"day": c.day, "feeling": c.feeling, "status": c.status} for c in recent]})

    def post(self, request):
        feeling = request.data.get("feeling")
        if not isinstance(feeling, int) or not 1 <= feeling <= 5:
            return Response({"detail": "feeling must be a whole number from 1 to 5."}, status=400)
        answers = {key: request.data[key] for key in ANSWERS if request.data.get(key) not in (None, "")}
        today = timezone.localdate()
        try:
            result = client.call("/ai/daily-check", {"feeling": feeling, **answers, **context_for(request.user),
                                                     "day": today.isoformat()})
        except client.AIRejected:
            return Response({"detail": "Some answers aren't valid. Check them and try again."}, status=400)
        except client.AIUnavailable:
            return Response(UNAVAILABLE, status=503)
        checkin, _ = DailyCheckIn.objects.update_or_create(
            user=request.user, day=today,
            defaults={"feeling": feeling, "answers": answers, "status": result.get("status", "good"),
                      "result": {"headline": result.get("headline", ""), "tips": result.get("tips", []),
                                 "disclaimer": result.get("disclaimer", "")}})
        record(request.user, "wellbeing.checked_in", "user", request.user.id, status=checkin.status)
        return Response(out(checkin), status=201)
