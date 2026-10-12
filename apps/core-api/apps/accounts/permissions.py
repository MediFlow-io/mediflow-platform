from rest_framework import permissions

from .models import User

Role = User.Role

# Staff who may see patient-identifiable data. IT and students are deliberately excluded.
PHI_READ_ROLES = frozenset({Role.ADMIN, Role.DOCTOR, Role.NURSE, Role.RECEPTION, Role.LAB, Role.PHARMACY})
PATIENT_WRITE_ROLES = frozenset({Role.ADMIN, Role.DOCTOR, Role.NURSE, Role.RECEPTION})
STAFF_ROLES = frozenset(choice for choice in Role.values if choice != Role.STUDENT)


def has_role(user, roles) -> bool:
    return bool(user and user.is_authenticated and user.role in roles)


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, {Role.ADMIN})


class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, STAFF_ROLES)


class CanReadPHI(permissions.BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, PHI_READ_ROLES)
