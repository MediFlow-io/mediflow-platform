from django.urls import path

from .views import (
    ChangePasswordView,
    CustomTokenRefreshView,
    LoginView,
    LogoutView,
    StaffRegistrationView,
    StudentRegistrationView,
)

app_name = 'auth'

urlpatterns = [
    path('register/student/', StudentRegistrationView.as_view(), name='register-student'),
    path('register/staff/', StaffRegistrationView.as_view(), name='register-staff'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]
