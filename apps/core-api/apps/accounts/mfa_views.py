"""Two-factor endpoints under /api/auth/mfa/ (see mfa.py for the flow)."""
from django.contrib.auth import login
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.operations.audit import record

from . import mfa
from .models import TotpDevice, User
from .permissions import STAFF_ROLES, IsAdmin, IsStaff


class MfaRateThrottle(SimpleRateThrottle):
    """Code guesses per client IP (shares the login rate)."""
    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": "mfa", "ident": self.get_ident(request)}


class MfaVerifyView(APIView):
    """POST /api/auth/mfa/verify {mfa_token, code}: the second step of signing in."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [MfaRateThrottle]

    def post(self, request):
        from .views import issue_tokens, user_response

        user = mfa.user_from_challenge(str(request.data.get("mfa_token", "")))
        if user is None:
            return Response({"detail": "The sign-in took too long. Please enter your password again."}, status=401)
        device = TotpDevice.objects.filter(user=user, confirmed_at__isnull=False).first()
        if device is None or not mfa.check_code(device, request.data.get("code", "")):
            record(None, "auth.mfa_failed", "user", user.pk)
            return Response({"detail": "That code isn't right. Use the current code from your authenticator app."}, status=401)
        login(request, user)
        record(user, "auth.login", "user", user.pk, mfa=True)
        payload = user_response(user)
        payload.update({"message": "Login successful", **issue_tokens(user)})
        return Response(payload)


class MfaStatusView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response({"enabled": mfa.enabled_for(request.user), "required": mfa.required_for(request.user)})


class MfaSetupView(APIView):
    """POST: a new secret and QR code. Replaces an unfinished setup; refused while 2FA is on."""
    permission_classes = [IsStaff]

    def post(self, request):
        if mfa.enabled_for(request.user):
            return Response({"detail": "Two-step sign-in is already on. Turn it off first to change authenticator."}, status=409)
        return Response(mfa.start_setup(request.user))


class MfaConfirmView(APIView):
    """POST {code}: the first code from the app proves it's set up; 2FA is on from now."""
    permission_classes = [IsStaff]

    def post(self, request):
        device = TotpDevice.objects.filter(user=request.user, confirmed_at__isnull=True).first()
        if device is None:
            return Response({"detail": "Start the setup first."}, status=400)
        if not mfa.check_code(device, request.data.get("code", "")):
            return Response({"code": ["That code isn't right. Check the time on your phone and try the next code."]}, status=400)
        from django.utils import timezone
        device.confirmed_at = timezone.now()
        device.save(update_fields=["confirmed_at"])
        record(request.user, "auth.mfa_enabled", "user", request.user.pk)
        return Response({"enabled": True})


class MfaDisableView(APIView):
    """POST {password, code}: turn 2FA off (not allowed where the role requires it)."""
    permission_classes = [IsStaff]

    def post(self, request):
        if mfa.required_for(request.user):
            return Response({"detail": "Your role requires two-step sign-in, so it can't be turned off."}, status=400)
        device = TotpDevice.objects.filter(user=request.user, confirmed_at__isnull=False).first()
        if device is None:
            return Response({"detail": "Two-step sign-in is not on."}, status=400)
        if not request.user.check_password(str(request.data.get("password", ""))) or not mfa.check_code(device, request.data.get("code", "")):
            return Response({"detail": "Your password or code isn't right."}, status=400)
        device.delete()
        record(request.user, "auth.mfa_disabled", "user", request.user.pk)
        return Response({"enabled": False})


class MfaResetView(APIView):
    """POST /api/users/{id}/reset-mfa (admin): for a lost phone. The user sets it up again."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk, role__in=STAFF_ROLES)
        deleted, _ = TotpDevice.objects.filter(user=user).delete()
        record(request.user, "auth.mfa_reset", "user", user.pk, had_device=bool(deleted))
        return Response({"reset": bool(deleted)}, status=status.HTTP_200_OK)
