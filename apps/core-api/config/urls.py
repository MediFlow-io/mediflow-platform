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
from apps.patients.views import DepartmentViewSet, PatientViewSet, VisitViewSet
from apps.operations.views import DashboardView, HealthView, QueueView
from apps.ai.views import AskView, TriageSuggestView

router = DefaultRouter()
router.trailing_slash = ""  # Existing MediFlow frontend calls /api/patients, not /api/patients/.
router.register("users", UserViewSet, basename="user")
router.register("patients", PatientViewSet, basename="patient")
router.register("departments", DepartmentViewSet, basename="department")
router.register("visits", VisitViewSet, basename="visit")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/session", SessionView.as_view()),
    path("api/login", LoginView.as_view()), path("api/login/", LoginView.as_view()),
    path("api/logout", LogoutView.as_view()), path("api/logout/", LogoutView.as_view()),
    path("api/register", RegisterView.as_view()), path("api/register/", RegisterView.as_view()),
    path("api/me", MeView.as_view()), path("api/me/", MeView.as_view()),
    path("api/me/health", MyHealthView.as_view()), path("api/me/health/", MyHealthView.as_view()),
    path("api/queue", QueueView.as_view()), path("api/queue/", QueueView.as_view()),
    path("api/dashboard", DashboardView.as_view()), path("api/dashboard/", DashboardView.as_view()),
    path("api/auth/login", LoginView.as_view()), path("api/auth/login/", LoginView.as_view()),
    path("api/auth/logout", LogoutView.as_view()), path("api/auth/logout/", LogoutView.as_view()),
    path("api/auth/register/student", StudentRegisterView.as_view()), path("api/auth/register/student/", StudentRegisterView.as_view()),
    path("api/auth/register/staff", StaffRegisterView.as_view()), path("api/auth/register/staff/", StaffRegisterView.as_view()),
    path("api/auth/token/refresh", TokenRefreshView.as_view()), path("api/auth/token/refresh/", TokenRefreshView.as_view()),
    path("api/auth/jwks", JwksView.as_view()), path(".well-known/jwks.json", JwksView.as_view()),
    path("api/auth/change-password", ChangePasswordView.as_view()), path("api/auth/change-password/", ChangePasswordView.as_view()),
    path("api/health", HealthView.as_view()),
    path("api/ai/ask", AskView.as_view()), path("api/ai/ask/", AskView.as_view()),
    path("api/ai/triage", TriageSuggestView.as_view()), path("api/ai/triage/", TriageSuggestView.as_view()),
    path("api/", include(router.urls)),
]
