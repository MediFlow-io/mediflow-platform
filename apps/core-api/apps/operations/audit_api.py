"""Read-only audit log API for the admin console (apps/admin-console).

The audit log is append-only and shared by every service (ADR-0002); this endpoint only reads it.
Viewing the log is itself audited.
"""
from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import IsAdmin

from .audit import record
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", read_only=True, default=None)
    actor_role = serializers.CharField(source="actor.role", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ("id", "created_at", "actor", "actor_role", "action", "entity_type", "entity_id", "details")


class AuditPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def parse_day(value, name):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError({name: "Use the format YYYY-MM-DD."})


class AuditLogListView(generics.ListAPIView):
    """GET /api/audit-logs — admins only.

    Filters: ?action=patient. (prefix)  ?actor=username  ?entity_type=patient  ?entity_id=12
             ?since=YYYY-MM-DD  ?until=YYYY-MM-DD (inclusive, hospital time zone)
    """
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
    pagination_class = AuditPagination

    def get_queryset(self):
        params = self.request.query_params
        logs = AuditLog.objects.select_related("actor").order_by("-created_at", "-id")
        if action := params.get("action", "").strip():
            logs = logs.filter(action__startswith=action)
        if actor := params.get("actor", "").strip():
            logs = logs.filter(actor__username=actor)
        if entity_type := params.get("entity_type", "").strip():
            logs = logs.filter(entity_type=entity_type)
        if entity_id := params.get("entity_id", "").strip():
            logs = logs.filter(entity_id=entity_id)
        tz = timezone.get_current_timezone()
        if since := params.get("since"):
            logs = logs.filter(created_at__gte=datetime.combine(parse_day(since, "since"), time.min, tz))
        if until := params.get("until"):
            logs = logs.filter(created_at__lt=datetime.combine(parse_day(until, "until") + timedelta(days=1), time.min, tz))
        return logs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        filters = {k: v for k, v in request.query_params.items() if k in ("action", "actor", "entity_type", "entity_id", "since", "until")}
        record(request.user, "audit.viewed", "audit", "", filters=filters)
        return response
