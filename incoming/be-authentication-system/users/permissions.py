from rest_framework.permissions import BasePermission
from .models import RoleChoices


class IsAdminUserRole(BasePermission):
    """
    Custom permission to restrict access to users who have role == 'Admin'
    or are superusers (is_superuser == True).
    """
    message = "Only administrators can register new staff members."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == RoleChoices.ADMIN or request.user.is_superuser)
        )
