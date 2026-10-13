from django.db import connection
from django.db.models import Count
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.permissions import CanReadPHI, IsStaff
from apps.patients.models import Visit

def minutes_between(start, end):
    return max(0, int((end - start).total_seconds() // 60))

class QueueView(APIView):
    """Waiting patients, most urgent (ESI) first, then first come first served."""
    permission_classes = [CanReadPHI]

    def get(self, request):
        department = request.query_params.get("department")
        visits = Visit.objects.select_related("patient", "department").filter(status=Visit.Status.WAITING)
        if department:
            visits = visits.filter(department__code=department)

        now = timezone.now()
        queue = []
        for position, visit in enumerate(visits.order_by("esi", "checked_in_at"), start=1):
            waited = minutes_between(visit.checked_in_at, now)
            queue.append({
                "id": visit.id,
                "visitId": visit.visit_number,
                "patientId": visit.patient_id,
                "fullName": visit.patient.full_name,
                "hospitalNumber": visit.patient.hospital_number,
                "department": visit.department.code,
                "priority": visit.esi,
                "status": "Urgent" if visit.esi <= 2 else "Waiting",
                "position": position,
                "arrival": timezone.localtime(visit.checked_in_at).strftime("%H:%M"),
                # Time actually waited so far (previously a made-up position x 10 min estimate).
                "waitingMinutes": waited,
                "wait": f"{waited} min",
            })
        return Response(queue)

class DashboardView(APIView):
    """Today's operational numbers, all computed from visit records."""
    permission_classes = [IsStaff]

    def get(self, request):
        now, today = timezone.now(), timezone.localdate()
        visits = Visit.objects.filter(checked_in_at__date=today)
        waits = [minutes_between(v.checked_in_at, v.called_at or v.started_at)
                 for v in visits.exclude(called_at__isnull=True, started_at__isnull=True)]
        waiting_now = Visit.objects.filter(status=Visit.Status.WAITING)
        oldest = waiting_now.order_by("checked_in_at").values_list("checked_in_at", flat=True).first()
        return Response({
            "patientsToday": visits.values("patient").distinct().count(),
            "currentlyWaiting": waiting_now.count(),
            "inConsultation": Visit.objects.filter(status=Visit.Status.IN_PROGRESS).count(),
            "completedToday": visits.filter(status=Visit.Status.COMPLETED).count(),
            "emergencyCases": waiting_now.filter(esi__lte=2).count(),
            "averageWaitMinutes": round(sum(waits) / len(waits)) if waits else None,
            "longestCurrentWaitMinutes": minutes_between(oldest, now) if oldest else None,
            "byDepartment": list(visits.values("department__name").annotate(total=Count("id")).order_by("department__name")),
            "byStatus": {row["status"]: row["total"] for row in visits.values("status").annotate(total=Count("id"))},
        })

class HealthView(APIView):
    """Liveness + database check for container health checks. Reveals nothing sensitive."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})
