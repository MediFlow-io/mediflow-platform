"""Insurance claims (NHIS/NHIA and HMOs): GET /api/claims/insurance.

One row per completed visit by an insured patient, with what an HMO needs to pay for it: the enrolment
number, scheme, diagnoses and what was prescribed. ?download=csv downloads the same rows as a spreadsheet.
There is no live link to the NHIA: their claims portal isn't public, so the file is what gets submitted.
Admins and the front desk may export; every export is audited (counts only, never clinical text).
"""
import csv
import io
from datetime import date, datetime, time, timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.emr.models import Diagnosis, Prescription
from apps.operations.audit import record

from .models import Patient, Visit

COLUMNS = [
    ("claimDate", "Date of service"), ("visitNumber", "Visit number"), ("hospitalNumber", "Hospital number"),
    ("patientName", "Patient"), ("enrolmentNumber", "NHIA / HMO number"), ("scheme", "Scheme"), ("hmo", "HMO"),
    ("coverExpires", "Cover expires"), ("department", "Department"), ("diagnoses", "Diagnoses"),
    ("prescriptions", "Prescriptions"), ("clinician", "Clinician"),
]


class CanExportClaims(permissions.BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, {User.Role.ADMIN, User.Role.RECEPTION})


def _day(value, fallback):
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({"detail": f"Dates look like 2026-11-30, not {value!r}."})


def _period(params):
    today = timezone.localdate()
    start = _day(params.get("from"), today.replace(day=1))
    end = _day(params.get("to"), today)
    if end < start:
        raise ValidationError({"detail": "'to' is before 'from'."})
    if (end - start).days > 366:
        raise ValidationError({"detail": "Export at most a year at a time."})
    return start, end


def claim_rows(start, end, scheme=""):
    tz = timezone.get_current_timezone()
    visits = (Visit.objects
              .filter(status=Visit.Status.COMPLETED, patient__payment_category=Patient.PaymentCategory.INSURANCE,
                      completed_at__gte=datetime.combine(start, time.min, tz),
                      completed_at__lt=datetime.combine(end + timedelta(days=1), time.min, tz))
              .select_related("patient", "department", "assigned_clinician").order_by("completed_at"))
    if scheme:
        visits = visits.filter(patient__insurance_scheme=scheme)
    visits = list(visits)
    ids = [v.id for v in visits]
    diagnoses, prescriptions = {}, {}
    for d in Diagnosis.objects.filter(visit_id__in=ids).exclude(status=Diagnosis.Status.ENTERED_IN_ERROR).order_by("id"):
        diagnoses.setdefault(d.visit_id, []).append(f"{d.description} ({d.code})" if d.code else d.description)
    for p in Prescription.objects.filter(visit_id__in=ids).exclude(status=Prescription.Status.CANCELLED).order_by("id"):
        prescriptions.setdefault(p.visit_id, []).append(" ".join(x for x in (p.drug, p.dose, p.frequency, p.duration) if x))
    rows = []
    for v in visits:
        patient, clinician = v.patient, v.assigned_clinician
        rows.append({
            "claimDate": timezone.localtime(v.completed_at).date().isoformat(),
            "visitNumber": v.visit_number,
            "hospitalNumber": patient.hospital_number,
            "patientName": patient.full_name,
            "enrolmentNumber": patient.insurance_number,
            "scheme": patient.get_insurance_scheme_display() if patient.insurance_scheme else "",
            "hmo": patient.hmo_name,
            "coverExpires": patient.insurance_expires.isoformat() if patient.insurance_expires else "",
            "department": v.department.name,
            "diagnoses": "; ".join(diagnoses.get(v.id, [])),
            "prescriptions": "; ".join(prescriptions.get(v.id, [])),
            "clinician": (clinician.display_name or clinician.username) if clinician else "",
        })
    return rows


class InsuranceClaimsView(APIView):
    permission_classes = [CanExportClaims]

    def get(self, request):
        start, end = _period(request.query_params)
        scheme = request.query_params.get("scheme", "")
        if scheme and scheme not in Patient.InsuranceScheme.values:
            raise ValidationError({"detail": f"Unknown scheme. Use one of: {', '.join(Patient.InsuranceScheme.values)}."})
        rows = claim_rows(start, end, scheme)
        as_csv = request.query_params.get("download") == "csv"  # "format" is DRF's own parameter
        record(request.user, "claims.exported", "claims", "", visits=len(rows), scheme=scheme or "all",
               start=start.isoformat(), end=end.isoformat(), csv=as_csv)
        if not as_csv:
            return Response({"from": start, "to": end, "scheme": scheme, "count": len(rows), "claims": rows})
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([label for _, label in COLUMNS])
        for row in rows:
            # A leading = + - @ would make spreadsheets run the cell as a formula.
            writer.writerow([("'" + str(row[key])) if str(row[key])[:1] in "=+-@" else row[key] for key, _ in COLUMNS])
        response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="insurance-claims-{start}-to-{end}.csv"'
        return response
