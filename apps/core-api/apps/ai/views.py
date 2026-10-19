from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.operations.audit import record

from . import client

TRIAGE_ROLES = frozenset({User.Role.ADMIN, User.Role.DOCTOR, User.Role.NURSE})
TRIAGE_FIELDS = ("chief_complaint", "age_years", "pain_score", "vitals")
UNAVAILABLE = {"detail": "The AI assistant is unavailable right now. Please try again or ask a clinician."}


class AIThrottle(UserRateThrottle):
    scope = "ai"


class AskView(APIView):
    """First-aid Q&A for any signed-in user (students included)."""
    throttle_classes = [AIThrottle]

    def post(self, request):
        question = request.data.get("question")
        if not isinstance(question, str) or not question.strip() or len(question) > 500:
            return Response({"detail": "question must be 1-500 characters."}, status=400)
        try:
            return Response(client.call("/ai/ask", {"question": question.strip()}))
        except client.AIRejected as error:
            return Response({"detail": str(error)}, status=400)
        except client.AIUnavailable:
            return Response(UNAVAILABLE, status=503)


class TriageSuggestView(APIView):
    """ESI suggestion for clinical staff. Advisory only: it never changes a visit."""
    throttle_classes = [AIThrottle]

    def post(self, request):
        if not has_role(request.user, TRIAGE_ROLES):
            return Response({"detail": "Only nurses, doctors and admins can request triage suggestions."}, status=403)
        # Forward clinical signals only. Names and record identifiers never leave the core API.
        payload = {key: request.data[key] for key in TRIAGE_FIELDS if key in request.data}
        try:
            suggestion = client.call("/ai/triage", payload)
        except client.AIRejected as error:
            return Response({"detail": str(error)}, status=400)
        except client.AIUnavailable:
            return Response(UNAVAILABLE, status=503)
        record(request.user, "ai.triage_suggested", "ai", "", suggested_esi=suggestion.get("suggested_esi"),
               model_version=suggestion.get("model_version"))
        return Response(suggestion)


class RiskScoreView(APIView):
    """NEWS2 early-warning score from vital signs, for clinical staff. Advisory only."""
    throttle_classes = [AIThrottle]

    def post(self, request):
        if not has_role(request.user, TRIAGE_ROLES):
            return Response({"detail": "Only nurses, doctors and admins can request risk scores."}, status=403)
        payload = {key: request.data[key] for key in ("vitals", "on_oxygen", "new_confusion") if key in request.data}
        try:
            result = client.call("/ai/risk-score", payload)
        except client.AIRejected as error:
            return Response({"detail": str(error)}, status=400)
        except client.AIUnavailable:
            return Response(UNAVAILABLE, status=503)
        record(request.user, "ai.risk_scored", "ai", "", score=result.get("score"), risk=result.get("risk"),
               model_version=result.get("model_version"))
        return Response(result)


class InsightsView(APIView):
    """GET /api/ai/insights (admin): expected waits per department and where flow is getting stuck.

    Django aggregates the last 14 days of visits itself and sends only numbers to the AI service.
    """
    throttle_classes = [AIThrottle]

    def get(self, request):
        if not has_role(request.user, {User.Role.ADMIN}):
            return Response({"detail": "Only administrators can see flow insights."}, status=403)
        from .insights import flow_numbers

        numbers = flow_numbers()
        try:
            found = client.call("/ai/bottleneck", {"departments": numbers["bottleneck_departments"], "hours": numbers["hours"]})
            departments = []
            if numbers["departments"]:
                # One call for every department: a new arrival waits behind everyone already waiting.
                queues = [{"name": d["name"], "ahead": d["waiting_now"], "clinicians": d["clinicians_now"],
                           "recent_service_minutes": numbers["service_minutes"].get(d["name"], [])} for d in numbers["departments"]]
                estimates = client.call("/ai/wait-time", {"queues": queues})["estimates"]
                departments = [{"name": d["name"], "waitingNow": d["waiting_now"], "checkIns": d["check_ins"],
                                "expectedWaitForNewArrival": e} for d, e in zip(numbers["departments"], estimates)]
        except client.AIRejected as error:
            return Response({"detail": str(error)}, status=400)
        except client.AIUnavailable:
            return Response(UNAVAILABLE, status=503)
        record(request.user, "ai.insights_viewed", "ai", "", findings=len(found.get("findings", [])))
        return Response({"periodDays": numbers["period_days"], "generatedAt": numbers["generated_at"],
                         "departments": departments, "findings": found.get("findings", []),
                         "modelVersion": found.get("model_version")})
