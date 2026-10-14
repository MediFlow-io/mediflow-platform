from rest_framework import serializers
from apps.accounts.models import User
from .models import Department, Patient

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
