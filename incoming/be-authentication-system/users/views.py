from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .permissions import IsAdminUserRole
from .serializers import (
    ChangePasswordRequestSerializer,
    ChangePasswordResponseSerializer,
    ErrorResponseSerializer,
    LoginRequestSerializer,
    LoginResponseSerializer,
    LogoutRequestSerializer,
    LogoutResponseSerializer,
    StaffRegistrationResponseSerializer,
    StaffRegistrationSerializer,
    StudentRegistrationResponseSerializer,
    StudentRegistrationSerializer,
)

User = get_user_model()


class StudentRegistrationView(APIView):
    """
    Endpoint for registering new student patients in the MediFlow system.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Student Registration",
        description=(
            "Registers a new student patient account. Requires a valid matriculation format "
            "(e.g. SEN/22/9269), minimum age of 16, and an 11-digit phone number. "
            "Automatically generates a Health Card Number formatted as <number>/<registration_year>."
        ),
        tags=['Authentication'],
        request=StudentRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                response=StudentRegistrationResponseSerializer,
                description="Student successfully registered."
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Validation error (e.g. invalid matric, underage, duplicate email/id)."
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = StudentRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response_serializer = StudentRegistrationResponseSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class StaffRegistrationView(APIView):
    """
    Endpoint for registering new hospital staff members.
    Restricted to Admin users.
    """
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    @extend_schema(
        summary="Register a new Staff member",
        description=(
            "Registers a new hospital staff member (Admin, Doctor, Nurse, Reception, Lab, Pharmacy, IT) "
            "and creates their associated staff profile. Restricted to administrators."
        ),
        tags=['Authentication'],
        request=StaffRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                response=StaffRegistrationResponseSerializer,
                description="Staff member successfully registered."
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Validation error (e.g. invalid role, duplicate unique_id or email, phone format)."
            ),
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Unauthorized (missing or invalid Bearer token)."
            ),
            403: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Forbidden (only administrators can register staff members)."
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = StaffRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response_serializer = StaffRegistrationResponseSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    Endpoint for authenticating users and issuing JWT access and refresh tokens.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="User Login",
        description=(
            "Authenticates a user via their unique_id (Matric No or Staff ID) and password. "
            "Returns JWT access and refresh tokens, user role, and ID."
        ),
        tags=['Authentication'],
        request=LoginRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=LoginResponseSerializer,
                description="Authentication successful. Returns tokens and user details."
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Bad request (missing required credentials)."
            ),
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Unauthorized (invalid credentials or inactive account)."
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        unique_id = serializer.validated_data['unique_id'].strip()
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(unique_id__iexact=unique_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid credentials or account does not exist."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {"detail": "Invalid credentials. Password does not match."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {"detail": "This account is inactive. Please contact system administration."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate JWT tokens via SimpleJWT
        refresh = RefreshToken.for_user(user)

        response_data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'role': user.role,
            'id': user.id,
            'unique_id': user.unique_id,
            'name': user.name,
            'email': user.email,
        }

        return Response(response_data, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        summary="Token Refresh",
        description=(
            "Takes a valid refresh token and returns a new access token "
            "(and rotated refresh token if token rotation is enabled)."
        ),
        tags=['Authentication'],
        responses={
            200: OpenApiResponse(
                description="Token successfully refreshed."
            ),
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Refresh token is expired, invalid, or blacklisted."
            ),
        }
    )
)
class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom wrapper around SimpleJWT TokenRefreshView with OpenAPI documentation.
    """
    pass


class LogoutView(APIView):
    """
    Endpoint for revoking the authenticated user's refresh token.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="User Logout",
        description=(
            "Blacklists the provided refresh token so it cannot be reused to obtain "
            "new access tokens. Requires Bearer authentication."
        ),
        tags=['Authentication'],
        request=LogoutRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=LogoutResponseSerializer,
                description="Token successfully blacklisted."
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Invalid, expired, or already blacklisted token."
            ),
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Unauthorized (missing or invalid Bearer token)."
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = LogoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh_token = serializer.validated_data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK
            )
        except (TokenError, InvalidToken) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChangePasswordView(APIView):
    """
    Endpoint for allowing an authenticated user to change their password.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change Password",
        description=(
            "Accepts old_password, new_password, and confirm_password. "
            "Enforces password strength validators and checks that the current password matches. "
            "Requires Bearer authentication."
        ),
        tags=['Authentication'],
        request=ChangePasswordRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=ChangePasswordResponseSerializer,
                description="Password successfully changed."
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Validation error (incorrect current password, passwords mismatch, or weak password)."
            ),
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Unauthorized (missing or invalid Bearer token)."
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK
        )
