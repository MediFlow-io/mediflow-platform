from django.db.models import Q
from rest_framework import permissions, viewsets
from apps.accounts.permissions import PATIENT_WRITE_ROLES, PHI_READ_ROLES, IsAdmin, has_role
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
    serializer_class = PatientSerializer
    permission_classes = [CanManagePatients]
    def get_queryset(self):
        query = self.request.query_params.get("search", "").strip()
        patients = Patient.objects.all().order_by("-created_at")
        if query: patients = patients.filter(Q(full_name__icontains=query) | Q(hospital_number__icontains=query) | Q(phone__icontains=query))
        return patients

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    def get_permissions(self):
        return [permissions.IsAuthenticated()] if self.request.method in permissions.SAFE_METHODS else [IsAdmin()]

class VisitViewSet(viewsets.ModelViewSet):
    queryset = Visit.objects.select_related("patient", "department", "assigned_clinician")
    serializer_class = VisitSerializer
    permission_classes = [CanManagePatients]
