import uuid

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.operations.audit import record
from config.jwt_keys import public_jwk

from .models import User
from .permissions import STAFF_ROLES, IsAdmin
from . import mfa
from .throttles import LoginRateThrottle, RefreshRateThrottle, RegisterRateThrottle
from .serializers import UserSerializer


def user_response(user):
    display_name = user.display_name or user.get_full_name() or user.username
    return {
        "id": user.id,
        "username": user.username,
        "staffId": user.username,
        "unique_id": user.username,
        "displayName": display_name,
        "name": display_name,
        "email": user.email or "",
        "role": user.role,
    }


def issue_tokens(user):
    """Signed RS256 pair. role/name are re-read from the database on every refresh."""
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["name"] = user.display_name or user.username
    access = str(refresh.access_token)
    # "token" is kept for older clients that read a single token field.
    return {"access": access, "refresh": str(refresh), "token": access}


def revoke_all_refresh_tokens(user):
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def weak_password(password, username):
    """Return a message if the password fails AUTH_PASSWORD_VALIDATORS, else None."""
    try:
        validate_password(password, User(username=username))
    except ValidationError as error:
        return " ".join(error.messages)
    return None


def requested_username(data):
    return data.get("unique_id") or data.get("staffId") or data.get("username")


class SessionView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(user_response(request.user))


class JwksView(APIView):
    """Public verifying key for other MediFlow services (gateway, future queue/AI/ops services)."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"keys": [public_jwk(settings.JWT_PUBLIC_KEY)]})


# Staff and students sign in on separate pages. A page that names its portal only accepts its own people,
# so a student can't land in the staff app (or the reverse). Clients that don't say are unaffected.
WRONG_PORTAL = {
    "staff": "This is the staff sign-in. Students sign in on the student portal.",
    "student": "This is the student portal. Staff sign in on the staff portal.",
}


def wrong_portal(user, portal):
    if portal not in WRONG_PORTAL:
        return False
    return (user.role == User.Role.STUDENT) != (portal == "student")


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]
    authentication_classes = []

    def post(self, request):
        username = (
            request.data.get("staffId")
            or request.data.get("username")
            or request.data.get("unique_id")
            or request.data.get("email")
        )
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "staffId and password are required."}, status=400)

        user = authenticate(request, username=username, password=password)
        if not user or not user.is_active:
            record(None, "auth.login_failed", "user", username)
            return Response({"detail": "Invalid credentials."}, status=401)

        portal = request.data.get("portal")
        if wrong_portal(user, portal):
            record(user, "auth.wrong_portal", "user", user.id, portal=portal)
            return Response({"detail": WRONG_PORTAL[portal], "code": "wrong_portal"}, status=403)

        if mfa.enabled_for(user):
            # Password is right; tokens only after the authenticator code (POST /api/auth/mfa/verify).
            record(user, "auth.mfa_challenged", "user", user.id)
            return Response({"mfa_required": True, "mfa_token": mfa.challenge_for(user),
                             "detail": "Enter the 6-digit code from your authenticator app."})

        login(request, user)
        record(user, "auth.login", "user", user.id)
        payload = user_response(user)
        payload.update({"message": "Login successful", **issue_tokens(user)})
        if mfa.required_for(user):
            payload["mfa_setup_required"] = True
        return Response(payload)


class LogoutView(APIView):
    # Allowed without a valid access token so a client holding only an expired
    # access token can still revoke its refresh token.
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_refresh = request.data.get("refresh")
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass  # Already expired or revoked: the outcome the caller wants.
        if request.user and request.user.is_authenticated:
            record(request.user, "auth.logout", "user", request.user.id)
        logout(request)
        return Response({"message": "Logged out successfully."})


class MeView(APIView):
    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(user_response(request.user))


class MyHealthView(APIView):
    """A signed-in person's own record (e.g. the student dashboard).

    Only the record linked to the caller's account (Patient.user) is returned.
    Clinician-facing fields (diagnosis, treatment, internal notes) are not included.
    """

    def get(self, request):
        from apps.patients.models import Patient, Visit

        patient = Patient.objects.filter(user=request.user).first()
        if patient is None:
            return Response({"linked": False, "patient": None, "activeVisit": None, "latestVitals": None, "visits": []})

        record(request.user, "patient.self_viewed", "patient", patient.pk)
        visits = list(patient.visits.select_related("department", "assigned_clinician").order_by("-checked_in_at")[:20])
        active = next((v for v in visits if v.status in Visit.ACTIVE_STATUSES), None)
        active_payload = None
        if active:
            ahead = None
            if active.status == Visit.Status.WAITING:
                # Same ordering as the queue: lower ESI first, then earlier check-in.
                ahead = Visit.objects.filter(department=active.department, status=Visit.Status.WAITING).filter(
                    Q(esi__lt=active.esi) | Q(esi=active.esi, checked_in_at__lt=active.checked_in_at)).count()
            active_payload = {
                "visitNumber": active.visit_number,
                "department": active.department.name,
                "status": active.status,
                "checkedInAt": active.checked_in_at,
                "calledAt": active.called_at,
                "startedAt": active.started_at,
                "patientsAhead": ahead,
            }

        # Latest vital signs taken at a check-in (numbers only; the complaint text stays with staff).
        measured = next((v for v in visits if any(getattr(v, f) is not None for f in
                         ("heart_rate", "resp_rate", "spo2", "temperature_c", "systolic_bp", "pain_score"))), None)
        latest_vitals = None
        if measured:
            latest_vitals = {
                "recordedAt": measured.checked_in_at, "heartRate": measured.heart_rate, "respRate": measured.resp_rate,
                "spo2": measured.spo2, "temperatureC": float(measured.temperature_c) if measured.temperature_c is not None else None,
                "systolicBp": measured.systolic_bp, "painScore": measured.pain_score,
            }

        def clinician(visit):
            user = visit.assigned_clinician
            return (user.display_name or user.username) if user else None

        return Response({
            "linked": True,
            "patient": {
                "hospitalNumber": patient.hospital_number, "fullName": patient.full_name,
                "dateOfBirth": patient.date_of_birth, "sex": patient.sex, "allergies": patient.allergies,
                "medicalHistory": patient.medical_history, "nextOfKin": patient.next_of_kin,
                "nextOfKinPhone": patient.next_of_kin_phone,
            },
            "activeVisit": active_payload,
            "latestVitals": latest_vitals,
            "visits": [{"visitNumber": v.visit_number, "checkedInAt": v.checked_in_at, "department": v.department.name,
                        "status": v.status, "clinician": clinician(v), "completedAt": v.completed_at} for v in visits],
        })


class RegisterView(APIView):
    """Legacy self-registration used by the FUTA frontend's register page."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        username = requested_username(request.data)
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "staffId and password are required."}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"detail": "Account already exists."}, status=400)

        # A client-supplied role is ignored: self-registration must never grant admin or clinical roles.
        # TODO(decision): self-registered staff still get reception access to patient data. Consider
        # creating them inactive until an admin approves, or retiring this route for /api/auth/register/staff.
        if problem := weak_password(password, username):
            return Response({"detail": problem}, status=400)

        user = User.objects.create_user(
            username=username,
            password=password,
            email=request.data.get("email", ""),
            role=User.Role.RECEPTION,
            display_name=request.data.get("name") or request.data.get("displayName") or username,
        )
        record(user, "auth.self_register", "user", user.id, role=user.role)
        payload = user_response(user)
        payload.update({"message": "Account created successfully."})
        return Response(payload, status=201)


class StudentRegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        username = requested_username(request.data)
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "unique_id and password are required."}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"detail": "Account already exists."}, status=400)

        display_name = request.data.get("name") or request.data.get("full_name") or username
        if problem := weak_password(password, username):
            return Response({"detail": problem}, status=400)

        user = User.objects.create_user(
            username=username,
            password=password,
            email=request.data.get("email", ""),
            role=User.Role.STUDENT,
            display_name=display_name,
        )
        record(user, "auth.self_register", "user", user.id, role=user.role)
        payload = user_response(user)
        payload.update({
            "message": "Student account created successfully.",
            "health_card_no": f"MF-{uuid.uuid4().hex[:10].upper()}",
        })
        return Response(payload, status=201)


class StaffRegisterView(APIView):
    """Admins create staff accounts. Previously open to anyone, including role=admin."""
    permission_classes = [IsAdmin]

    def post(self, request):
        username = requested_username(request.data)
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "unique_id and password are required."}, status=400)

        role = str(request.data.get("role") or User.Role.RECEPTION).lower()
        if role not in STAFF_ROLES:
            return Response({"detail": f"role must be one of: {', '.join(sorted(STAFF_ROLES))}."}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"detail": "Account already exists."}, status=400)

        if problem := weak_password(password, username):
            return Response({"detail": problem}, status=400)

        user = User.objects.create_user(
            username=username,
            password=password,
            email=request.data.get("email", ""),
            role=role,
            display_name=request.data.get("name") or username,
        )
        record(request.user, "staff.create", "user", user.id, role=role)
        payload = user_response(user)
        payload.update({
            "message": "Staff account created successfully.",
            "profile": {"name": user.display_name or user.username},
        })
        return Response(payload, status=201)


class TokenRefreshView(APIView):
    """Rotates the refresh token: the presented one is revoked and a fresh pair is returned."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RefreshRateThrottle]
    authentication_classes = []

    def post(self, request):
        try:
            refresh = RefreshToken(request.data.get("refresh") or "")
        except TokenError:
            return Response({"detail": "Refresh token is invalid, expired, or revoked."}, status=401)

        user = User.objects.filter(id=refresh.payload.get(settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")),
                                   is_active=True).first()
        if not user:
            return Response({"detail": "Refresh token is invalid, expired, or revoked."}, status=401)

        refresh.blacklist()
        return Response(issue_tokens(user))


class ChangePasswordView(APIView):
    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password", new_password)
        if not old_password or not new_password:
            return Response({"detail": "old_password and new_password are required."}, status=400)
        if new_password != confirm_password:
            return Response({"detail": "New passwords do not match."}, status=400)
        if not request.user.check_password(old_password):
            return Response({"detail": "Current password is incorrect."}, status=400)
        try:
            validate_password(new_password, request.user)
        except ValidationError as error:
            return Response({"detail": " ".join(error.messages)}, status=400)

        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        # Sign out every other device; this caller gets a fresh pair.
        revoke_all_refresh_tokens(request.user)
        record(request.user, "auth.password_changed", "user", request.user.id)
        return Response({"message": "Password changed successfully.", **issue_tokens(request.user)})


class UserViewSet(viewsets.ModelViewSet):
    """Admin staff management. Accounts are deactivated, never deleted, so audit history stays intact.

    Filters: ?role=doctor  ?active=true  ?search=name-or-username
    """
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        users = User.objects.all().order_by("username")
        params = self.request.query_params
        if role := params.get("role"):
            users = users.filter(role=role)
        if params.get("active") in ("true", "false"):
            users = users.filter(is_active=params["active"] == "true")
        if search := params.get("search", "").strip():
            users = users.filter(Q(username__icontains=search) | Q(display_name__icontains=search))
        return users

    def perform_create(self, serializer):
        user = serializer.save()
        record(self.request.user, "staff.create", "user", user.id, role=user.role)

    def perform_update(self, serializer):
        target = serializer.instance
        data = serializer.validated_data
        if target.pk == self.request.user.pk and (data.get("is_active") is False or data.get("role", target.role) != target.role):
            from rest_framework.exceptions import ValidationError as DRFValidationError
            raise DRFValidationError({"detail": "You cannot deactivate yourself or change your own role."})
        user = serializer.save()
        if data.get("is_active") is False:
            revoke_all_refresh_tokens(user)  # signs them out everywhere at once
        record(self.request.user, "staff.update", "user", user.id,
               fields=sorted(k for k in data if k != "password"), password_reset="password" in data)
