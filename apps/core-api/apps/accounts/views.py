import uuid

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
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


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
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

        login(request, user)
        record(user, "auth.login", "user", user.id)
        payload = user_response(user)
        payload.update({"message": "Login successful", **issue_tokens(user)})
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


class RegisterView(APIView):
    """Legacy self-registration used by the FUTA frontend's register page."""
    permission_classes = [permissions.AllowAny]

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

    def post(self, request):
        username = requested_username(request.data)
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "unique_id and password are required."}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"detail": "Account already exists."}, status=400)

        display_name = request.data.get("name") or request.data.get("full_name") or username
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
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
