"""EMR Lite API, under /api/emr/ (the /api/visits paths belong to the Go service).

Who may do what:
- read a visit's clinical record or a patient's history: admin, doctor, nurse
- consultation notes and admissions: doctor, nurse
- diagnoses, prescriptions, referrals: doctor
- prescriptions list and dispensing: pharmacy (doctors and nurses may read the list)
Every read and write is audited; clinical text never goes into the audit details.
"""
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.operations.audit import record
from apps.patients.models import Patient, Visit

from .models import Admission, Consultation, Diagnosis, Prescription, Referral

Role = User.Role
READ = {Role.ADMIN, Role.DOCTOR, Role.NURSE}
NOTES = {Role.DOCTOR, Role.NURSE}
DOCTOR = {Role.DOCTOR}
PRESCRIPTION_LIST = {Role.PHARMACY, Role.DOCTOR, Role.NURSE, Role.ADMIN}
DISPENSE = {Role.PHARMACY}


def roles(allowed, write=None):
    """Permission: `allowed` may read; `write` (default: same) may change."""
    class Permission(permissions.BasePermission):
        def has_permission(self, request, view):
            wanted = allowed if request.method in permissions.SAFE_METHODS else (write or allowed)
            return has_role(request.user, wanted)
    return Permission


def name(user):
    return (user.display_name or user.username) if user else None


def open_visit(visit_id) -> Visit:
    visit = get_object_or_404(Visit.objects.select_related("patient", "department"), pk=visit_id)
    if visit.status == Visit.Status.CANCELLED:
        raise ValidationError({"visit": ["This visit was cancelled; nothing can be recorded on it."]})
    return visit


# ---------------------------------------------------------------- serializers

class DiagnosisSerializer(serializers.ModelSerializer):
    recorded_by = serializers.SerializerMethodField()

    class Meta:
        model = Diagnosis
        fields = ("id", "description", "code", "primary", "status", "recorded_by", "created_at")
        read_only_fields = ("status",)

    def get_recorded_by(self, obj):
        return name(obj.recorded_by)


class PrescriptionSerializer(serializers.ModelSerializer):
    prescribed_by = serializers.SerializerMethodField()
    dispensed_by = serializers.SerializerMethodField()
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    hospital_number = serializers.CharField(source="patient.hospital_number", read_only=True)
    visit_number = serializers.CharField(source="visit.visit_number", read_only=True)
    allergies = serializers.CharField(source="patient.allergies", read_only=True)

    class Meta:
        model = Prescription
        fields = ("id", "visit", "visit_number", "patient", "patient_name", "hospital_number", "allergies", "drug", "dose",
                  "route", "frequency", "duration", "instructions", "status", "prescribed_by", "created_at",
                  "dispensed_by", "dispensed_at", "cancelled_reason")
        read_only_fields = ("visit", "patient", "status", "dispensed_at", "cancelled_reason")

    def get_prescribed_by(self, obj):
        return name(obj.prescribed_by)

    def get_dispensed_by(self, obj):
        return name(obj.dispensed_by)


class ReferralSerializer(serializers.ModelSerializer):
    referred_by = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = ("id", "destination", "reason", "urgency", "referred_by", "created_at")

    def get_referred_by(self, obj):
        return name(obj.referred_by)


def admission_json(a: Admission | None):
    if a is None:
        return None
    return {"id": a.id, "ward": a.ward, "admittedAt": a.admitted_at, "admittedBy": name(a.admitted_by),
            "dischargedAt": a.discharged_at, "dischargedBy": name(a.discharged_by), "dischargeSummary": a.discharge_summary}


def consultation_json(c: Consultation | None):
    if c is None:
        return None
    return {"notes": c.notes, "clinician": name(c.clinician), "createdAt": c.created_at, "updatedAt": c.updated_at,
            "updatedBy": name(c.updated_by)}


def visit_record(visit: Visit) -> dict:
    return {
        "visit": {"id": visit.id, "visitNumber": visit.visit_number, "status": visit.status, "esi": visit.esi,
                  "department": visit.department.name, "checkedInAt": visit.checked_in_at,
                  "patient": {"id": visit.patient_id, "fullName": visit.patient.full_name,
                              "hospitalNumber": visit.patient.hospital_number, "allergies": visit.patient.allergies,
                              "chronicConditions": visit.patient.chronic_conditions}},
        "consultation": consultation_json(getattr(visit, "consultation", None)),
        "diagnoses": DiagnosisSerializer(visit.diagnoses.select_related("recorded_by"), many=True).data,
        "prescriptions": PrescriptionSerializer(visit.prescriptions.select_related("prescribed_by", "dispensed_by", "patient", "visit"), many=True).data,
        "referrals": ReferralSerializer(visit.referrals.select_related("referred_by"), many=True).data,
        "admission": admission_json(getattr(visit, "admission", None)),
    }


# ---------------------------------------------------------------- views

class VisitRecordView(APIView):
    """GET /api/emr/visits/{id}: the visit's whole clinical record."""
    permission_classes = [roles(READ)]

    def get(self, request, visit_id):
        visit = get_object_or_404(Visit.objects.select_related("patient", "department"), pk=visit_id)
        record(request.user, "emr.visit_viewed", "visit", visit.pk)
        return Response(visit_record(visit))


class ConsultationView(APIView):
    """PUT /api/emr/visits/{id}/consultation {notes}: write or replace the notes."""
    permission_classes = [roles(READ, NOTES)]

    def put(self, request, visit_id):
        visit = open_visit(visit_id)
        notes = str(request.data.get("notes", "")).strip()
        if not notes:
            raise ValidationError({"notes": ["Write the consultation notes."]})
        if len(notes) > 20_000:
            raise ValidationError({"notes": ["Notes are limited to 20,000 characters."]})
        consultation, created = Consultation.objects.get_or_create(
            visit=visit, defaults={"notes": notes, "clinician": request.user, "updated_by": request.user})
        if not created:
            consultation.notes, consultation.updated_by = notes, request.user
            consultation.save(update_fields=["notes", "updated_by", "updated_at"])
        record(request.user, "emr.consultation_saved", "visit", visit.pk, created=created)
        return Response(consultation_json(consultation), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class DiagnosisCreateView(APIView):
    permission_classes = [roles(READ, DOCTOR)]

    def post(self, request, visit_id):
        visit = open_visit(visit_id)
        serializer = DiagnosisSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get("primary"):
                visit.diagnoses.filter(primary=True).update(primary=False)
            diagnosis = serializer.save(visit=visit, recorded_by=request.user)
        record(request.user, "emr.diagnosis_added", "visit", visit.pk, diagnosis=diagnosis.pk, coded=bool(diagnosis.code))
        return Response(DiagnosisSerializer(diagnosis).data, status=status.HTTP_201_CREATED)


class DiagnosisErrorView(APIView):
    """POST /api/emr/diagnoses/{id}/entered-in-error: diagnoses are never deleted."""
    permission_classes = [roles(DOCTOR)]

    def post(self, request, pk):
        diagnosis = get_object_or_404(Diagnosis, pk=pk)
        diagnosis.status, diagnosis.primary = Diagnosis.Status.ENTERED_IN_ERROR, False
        diagnosis.save(update_fields=["status", "primary"])
        record(request.user, "emr.diagnosis_entered_in_error", "visit", diagnosis.visit_id, diagnosis=diagnosis.pk)
        return Response(DiagnosisSerializer(diagnosis).data)


class PrescriptionCreateView(APIView):
    permission_classes = [roles(READ, DOCTOR)]

    def post(self, request, visit_id):
        visit = open_visit(visit_id)
        serializer = PrescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prescription = serializer.save(visit=visit, patient=visit.patient, prescribed_by=request.user)
        record(request.user, "emr.prescription_added", "visit", visit.pk, prescription=prescription.pk)
        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)


class PrescriptionListView(APIView):
    """GET /api/emr/prescriptions?status=prescribed: the pharmacy's work list (oldest first)."""
    permission_classes = [roles(PRESCRIPTION_LIST)]

    def get(self, request):
        wanted = request.query_params.get("status", Prescription.Status.PRESCRIBED)
        if wanted not in Prescription.Status.values:
            raise ValidationError({"status": [f"Use one of: {', '.join(Prescription.Status.values)}."]})
        items = (Prescription.objects.filter(status=wanted).select_related("patient", "visit", "prescribed_by", "dispensed_by")
                 .order_by("created_at" if wanted == Prescription.Status.PRESCRIBED else "-created_at")[:200])
        record(request.user, "emr.prescriptions_listed", "prescription", "", status=wanted, results=len(items))
        return Response(PrescriptionSerializer(items, many=True).data)


class PrescriptionActionView(APIView):
    """POST /api/emr/prescriptions/{id}/dispense (pharmacy) or /cancel {reason} (doctor)."""

    def get_permissions(self):
        if self.kwargs["action"] not in ("dispense", "cancel"):
            raise Http404
        return [roles(DISPENSE if self.kwargs["action"] == "dispense" else DOCTOR)()]

    def post(self, request, pk, action):
        with transaction.atomic():
            prescription = get_object_or_404(Prescription.objects.select_for_update(), pk=pk)
            if prescription.status != Prescription.Status.PRESCRIBED:
                return Response({"detail": f"This prescription is already {prescription.status}."}, status=status.HTTP_409_CONFLICT)
            if action == "dispense":
                prescription.status, prescription.dispensed_by, prescription.dispensed_at = (
                    Prescription.Status.DISPENSED, request.user, timezone.now())
            else:
                reason = str(request.data.get("reason", "")).strip()[:200]
                if not reason:
                    raise ValidationError({"reason": ["Say why it is cancelled."]})
                prescription.status, prescription.cancelled_reason = Prescription.Status.CANCELLED, reason
            prescription.save()
        record(request.user, f"emr.prescription_{'dispensed' if action == 'dispense' else 'cancelled'}", "visit",
               prescription.visit_id, prescription=prescription.pk)
        return Response(PrescriptionSerializer(prescription).data)


class ReferralCreateView(APIView):
    permission_classes = [roles(READ, DOCTOR)]

    def post(self, request, visit_id):
        visit = open_visit(visit_id)
        serializer = ReferralSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        referral = serializer.save(visit=visit, referred_by=request.user)
        record(request.user, "emr.referral_added", "visit", visit.pk, referral=referral.pk, urgency=referral.urgency)
        return Response(ReferralSerializer(referral).data, status=status.HTTP_201_CREATED)


class AdmissionView(APIView):
    """POST /api/emr/visits/{id}/admission {ward}; POST /api/emr/visits/{id}/discharge {summary}."""
    permission_classes = [roles(READ, NOTES)]

    def post(self, request, visit_id, action):
        if action not in ("admission", "discharge"):
            raise Http404
        visit = open_visit(visit_id)
        if action == "admission":
            ward = str(request.data.get("ward", "")).strip()[:60]
            if not ward:
                raise ValidationError({"ward": ["Which ward or bay?"]})
            if Admission.objects.filter(visit=visit).exists():
                return Response({"detail": "This visit already has an admission."}, status=status.HTTP_409_CONFLICT)
            admission = Admission.objects.create(visit=visit, ward=ward, admitted_by=request.user)
            record(request.user, "emr.admitted", "visit", visit.pk, ward=ward)
            return Response(admission_json(admission), status=status.HTTP_201_CREATED)
        admission = get_object_or_404(Admission, visit=visit)
        if admission.discharged_at:
            return Response({"detail": "The patient was already discharged."}, status=status.HTTP_409_CONFLICT)
        summary = str(request.data.get("summary", "")).strip()
        if not summary:
            raise ValidationError({"summary": ["Write a short discharge summary."]})
        admission.discharged_at, admission.discharged_by, admission.discharge_summary = timezone.now(), request.user, summary
        admission.save()
        record(request.user, "emr.discharged", "visit", visit.pk)
        return Response(admission_json(admission))


class PatientHistoryView(APIView):
    """GET /api/emr/patients/{id}/history: every visit's clinical record, newest first (up to 50 visits)."""
    permission_classes = [roles(READ)]

    def get(self, request, patient_id):
        patient = get_object_or_404(Patient, pk=patient_id)
        visits = (Visit.objects.filter(patient=patient).select_related("patient", "department")
                  .order_by("-checked_in_at")[:50])
        record(request.user, "emr.history_viewed", "patient", patient.pk)
        return Response({"patient": {"id": patient.id, "fullName": patient.full_name, "hospitalNumber": patient.hospital_number,
                                     "allergies": patient.allergies, "chronicConditions": patient.chronic_conditions},
                         "visits": [visit_record(v) for v in visits]})


class MyMedicationsView(APIView):
    """GET /api/me/medications: the signed-in patient's own prescriptions (what to take, not why)."""

    def get(self, request):
        patient = Patient.objects.filter(user=request.user).first()
        if patient is None:
            return Response({"linked": False, "medications": []})
        items = patient.prescriptions.exclude(status=Prescription.Status.CANCELLED).order_by("-created_at")[:50]
        record(request.user, "emr.medications_self_viewed", "patient", patient.pk)
        return Response({"linked": True, "medications": [
            {"drug": p.drug, "dose": p.dose, "route": p.route, "frequency": p.frequency, "duration": p.duration,
             "instructions": p.instructions, "status": p.status, "prescribedAt": p.created_at, "dispensedAt": p.dispensed_at}
            for p in items]})
