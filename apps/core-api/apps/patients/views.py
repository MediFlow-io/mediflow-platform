from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.permissions import PATIENT_WRITE_ROLES, PHI_READ_ROLES, IsAdmin, has_role
from apps.operations.audit import record
from .flow import TRANSITIONS, TransitionError, apply_transition
from .models import Department, Patient, Visit
from .serializers import DepartmentSerializer, PatientSerializer, VisitSerializer

class CanManagePatients(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS: return has_role(request.user, PHI_READ_ROLES)
        return has_role(request.user, PATIENT_WRITE_ROLES)
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS: return True
        return request.user.role in ("admin", "doctor", "reception")

class PatientViewSet(viewsets.ModelViewSet):
    """Every access to an identifiable record is audited. Search text is never stored (it may be a name)."""
    serializer_class = PatientSerializer
    permission_classes = [CanManagePatients]
    def get_queryset(self):
        query = self.request.query_params.get("search", "").strip()
        patients = Patient.objects.select_related("user").order_by("-created_at")
        if query: patients = patients.filter(Q(full_name__icontains=query) | Q(hospital_number__icontains=query) | Q(phone__icontains=query))
        return patients
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record(request.user, "patient.listed", "patient", "", results=len(response.data), searched=bool(request.query_params.get("search")))
        return response
    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        record(request.user, "patient.viewed", "patient", kwargs["pk"])
        return response
    def perform_create(self, serializer):
        patient = serializer.save()
        record(self.request.user, "patient.created", "patient", patient.pk)
    def perform_update(self, serializer):
        patient = serializer.save()
        record(self.request.user, "patient.updated", "patient", patient.pk, fields=sorted(serializer.validated_data))
    def perform_destroy(self, instance):
        record(self.request.user, "patient.deleted", "patient", instance.pk, hospital_number=instance.hospital_number)
        instance.delete()

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    def get_permissions(self):
        return [permissions.IsAuthenticated()] if self.request.method in permissions.SAFE_METHODS else [IsAdmin()]

class VisitViewSet(viewsets.ModelViewSet):
    """Check-ins. Filters: ?status=waiting,called  ?department=opd  ?patient=12  ?today=true"""
    serializer_class = VisitSerializer
    permission_classes = [CanManagePatients]
    def get_queryset(self):
        visits = Visit.objects.select_related("patient", "department", "assigned_clinician")
        params = self.request.query_params
        if statuses := [s for s in params.get("status", "").split(",") if s]:
            visits = visits.filter(status__in=statuses)
        if department := params.get("department"):
            visits = visits.filter(department__code=department)
        if patient := params.get("patient"):
            visits = visits.filter(patient_id=patient)
        if params.get("today") == "true":
            from django.utils import timezone
            visits = visits.filter(checked_in_at__date=timezone.localdate())
        return visits
    def perform_create(self, serializer):
        visit = serializer.save()
        record(self.request.user, "visit.checked_in", "visit", visit.pk, esi=visit.esi, department=visit.department.code)
    def perform_update(self, serializer):
        visit = serializer.save()
        record(self.request.user, "visit.updated", "visit", visit.pk, fields=sorted(serializer.validated_data))

    def _transition(self, request, pk, name):
        # Roles are checked per action in flow.py (nurses may start/complete but not edit visits).
        if not str(pk).isdigit() or not Visit.objects.filter(pk=pk).exists():
            return Response({"detail": "Not found."}, status=404)
        try:
            visit = apply_transition(int(pk), name, request.user)
        except TransitionError as error:
            return Response({"detail": str(error)}, status=error.status_code)
        record(request.user, f"visit.{name}", "visit", visit.pk, status=visit.status)
        return Response(VisitSerializer(visit).data)

    @action(detail=True, methods=["post"])
    def call(self, request, pk=None): return self._transition(request, pk, "call")
    @action(detail=True, methods=["post"])
    def start(self, request, pk=None): return self._transition(request, pk, "start")
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None): return self._transition(request, pk, "complete")
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None): return self._transition(request, pk, "cancel")

assert set(TRANSITIONS) == {"call", "start", "complete", "cancel"}, "add a route for every transition"
