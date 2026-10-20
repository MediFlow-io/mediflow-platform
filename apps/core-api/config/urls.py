from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.accounts.views import (
    ChangePasswordView,
    JwksView,
    LoginView,
    LogoutView,
    MeView,
    MyHealthView,
    RegisterView,
    SessionView,
    StaffRegisterView,
    StudentRegisterView,
    TokenRefreshView,
    UserViewSet,
)
from apps.patients.views import DepartmentViewSet, PatientViewSet
from apps.operations.views import HealthView
from apps.operations.audit_api import AuditLogListView
from apps.ai.views import AskView, TriageSuggestView
from apps.clinic import views as clinic

router = DefaultRouter()
router.trailing_slash = ""  # Existing MediFlow frontend calls /api/patients, not /api/patients/.
router.register("users", UserViewSet, basename="user")
router.register("patients", PatientViewSet, basename="patient")
router.register("departments", DepartmentViewSet, basename="department")
# /api/visits, /api/queue and /api/dashboard are served by the Go patient-flow service (ADR-0002).

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/session", SessionView.as_view()),
    path("api/login", LoginView.as_view()), path("api/login/", LoginView.as_view()),
    path("api/logout", LogoutView.as_view()), path("api/logout/", LogoutView.as_view()),
    path("api/register", RegisterView.as_view()), path("api/register/", RegisterView.as_view()),
    path("api/me", MeView.as_view()), path("api/me/", MeView.as_view()),
    path("api/me/health", MyHealthView.as_view()), path("api/me/health/", MyHealthView.as_view()),
    path("api/auth/login", LoginView.as_view()), path("api/auth/login/", LoginView.as_view()),
    path("api/auth/logout", LogoutView.as_view()), path("api/auth/logout/", LogoutView.as_view()),
    path("api/auth/register/student", StudentRegisterView.as_view()), path("api/auth/register/student/", StudentRegisterView.as_view()),
    path("api/auth/register/staff", StaffRegisterView.as_view()), path("api/auth/register/staff/", StaffRegisterView.as_view()),
    path("api/auth/token/refresh", TokenRefreshView.as_view()), path("api/auth/token/refresh/", TokenRefreshView.as_view()),
    path("api/auth/jwks", JwksView.as_view()), path(".well-known/jwks.json", JwksView.as_view()),
    path("api/auth/change-password", ChangePasswordView.as_view()), path("api/auth/change-password/", ChangePasswordView.as_view()),
    path("api/health", HealthView.as_view()),
    # Prometheus metrics at /metrics. Not routed by the public Nginx (only /api/* is), so internal only.
    path("", include("django_prometheus.urls")),
    path("api/audit-logs", AuditLogListView.as_view()), path("api/audit-logs/", AuditLogListView.as_view()),
    path("api/ai/ask", AskView.as_view()), path("api/ai/ask/", AskView.as_view()),
    path("api/ai/triage", TriageSuggestView.as_view()), path("api/ai/triage/", TriageSuggestView.as_view()),
    # Clinic settings: read by everyone signed in, changed by admins (edited from the Laravel console).
    path("api/clinic/settings", clinic.ClinicSettingsView.as_view()),
    path("api/clinic/queue-settings", clinic.QueueSettingsView.as_view()),
    path("api/clinic/hours", clinic.HoursView.as_view()),
    path("api/clinic/holidays", clinic.HolidayListView.as_view()),
    path("api/clinic/holidays/<int:pk>", clinic.HolidayDetailView.as_view()),
    path("api/clinic/shifts", clinic.ShiftListView.as_view()),
    path("api/clinic/shifts/<int:pk>", clinic.ShiftDetailView.as_view()),
    path("api/", include(router.urls)),
]
