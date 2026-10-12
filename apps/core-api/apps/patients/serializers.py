from rest_framework import serializers
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
    class Meta:
        model = Patient
        fields = ("id", "hospitalNumber", "fullName", "dateOfBirth", "sex", "phone", "address", "nextOfKin", "nextOfKinPhone", "allergies", "medicalHistory", "complaint", "diagnosis", "treatment", "notes", "created_at", "updated_at")
        extra_kwargs = {"address": {"required": False}, "allergies": {"required": False}, "complaint": {"required": False}, "diagnosis": {"required": False}, "treatment": {"required": False}, "notes": {"required": False}}

class VisitSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    patient_hospital_number = serializers.CharField(source="patient.hospital_number", read_only=True)
    class Meta:
        model = Visit
        fields = ("id", "visit_number", "patient", "patient_name", "patient_hospital_number", "department", "esi", "status", "arrival_mode", "checked_in_at", "called_at", "completed_at", "assigned_clinician")
        read_only_fields = ("visit_number", "checked_in_at", "called_at", "completed_at")
    def validate_esi(self, value):
        if not 1 <= value <= 5: raise serializers.ValidationError("ESI must be from 1 to 5.")
        return value
