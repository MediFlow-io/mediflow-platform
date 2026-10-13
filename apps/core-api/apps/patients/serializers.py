from rest_framework import serializers
from apps.accounts.models import User
from .models import Department, Patient, Visit

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta: model = Department; fields = ("id", "name", "code", "active")

class PatientSerializer(serializers.ModelSerializer):
    hospitalNumber = serializers.CharField(source="hospital_number", read_only=True)
    fullName = serializers.CharField(source="full_name")
    dateOfBirth = serializers.DateField(source="date_of_birth", required=False, allow_null=True)
    nextOfKin = serializers.CharField(source="next_of_kin", required=False, allow_blank=True)
    nextOfKinPhone = serializers.CharField(source="next_of_kin_phone", required=False, allow_blank=True)
    medicalHistory = serializers.CharField(source="medical_history", required=False, allow_blank=True)
    # Username of the login account (e.g. a student) allowed to view this record. "" unlinks.
    linkedAccount = serializers.CharField(required=False, allow_blank=True, write_only=True)
    linkedAccountName = serializers.CharField(source="user.username", read_only=True, default=None)
    class Meta:
        model = Patient
        fields = ("id", "hospitalNumber", "fullName", "dateOfBirth", "sex", "phone", "address", "nextOfKin", "nextOfKinPhone", "allergies", "medicalHistory", "complaint", "diagnosis", "treatment", "notes", "linkedAccount", "linkedAccountName", "created_at", "updated_at")
        extra_kwargs = {"address": {"required": False}, "allergies": {"required": False}, "complaint": {"required": False}, "diagnosis": {"required": False}, "treatment": {"required": False}, "notes": {"required": False}}

    def validate_linkedAccount(self, value):
        if not value:
            return None
        user = User.objects.filter(username=value, is_active=True).first()
        if not user:
            raise serializers.ValidationError("No active account with that username.")
        other = Patient.objects.filter(user=user).exclude(pk=getattr(self.instance, "pk", None)).first()
        if other:
            raise serializers.ValidationError("That account is already linked to another patient record.")
        return user

    def _apply_link(self, validated_data):
        if "linkedAccount" in validated_data:
            validated_data["user"] = validated_data.pop("linkedAccount")
        return validated_data

    def create(self, validated_data):
        return super().create(self._apply_link(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._apply_link(validated_data))

class VisitSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    patient_hospital_number = serializers.CharField(source="patient.hospital_number", read_only=True)
    department_code = serializers.CharField(source="department.code", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    assigned_clinician_name = serializers.SerializerMethodField()

    def get_assigned_clinician_name(self, visit):
        user = visit.assigned_clinician
        return (user.display_name or user.username) if user else None

    def validate(self, attrs):
        patient = attrs.get("patient")
        if self.instance is None and patient and patient.visits.filter(status__in=Visit.ACTIVE_STATUSES).exists():
            raise serializers.ValidationError({"patient": "This patient already has an active visit."})
        department = attrs.get("department")
        if department and not department.active:
            raise serializers.ValidationError({"department": "This department is not active."})
        return attrs
    class Meta:
        model = Visit
        fields = ("id", "visit_number", "patient", "patient_name", "patient_hospital_number", "department", "department_code", "department_name", "esi", "status", "arrival_mode", "checked_in_at", "called_at", "started_at", "completed_at", "assigned_clinician", "assigned_clinician_name")
        # Status changes only through the lifecycle actions (apps/patients/flow.py).
        read_only_fields = ("visit_number", "status", "checked_in_at", "called_at", "started_at", "completed_at")
    def validate_esi(self, value):
        if not 1 <= value <= 5: raise serializers.ValidationError("ESI must be from 1 to 5.")
        return value
