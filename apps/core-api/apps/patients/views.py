# Visits, the queue and the flow dashboard are served by the Go patient-flow service
# (apps/patient-flow, ADR-0002). This app still owns patients and departments.
from django.db.models import Q
from rest_framework import permissions, viewsets
from apps.accounts.permissions import PATIENT_WRITE_ROLES, PHI_READ_ROLES, IsAdmin, has_role
from apps.operations.audit import record
from .models import Department, Patient
from .serializers import DepartmentSerializer, PatientSerializer

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
    def perform_create(self, serializer):
        department = serializer.save()
        record(self.request.user, "department.created", "department", department.pk, code=department.code)
    def perform_update(self, serializer):
        department = serializer.save()
        record(self.request.user, "department.updated", "department", department.pk, fields=sorted(serializer.validated_data), active=department.active)
