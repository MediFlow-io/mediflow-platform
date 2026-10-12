"""Role-based access control (RBAC) for the FUTA health system.

This is the single source of truth for authorization. Update here, not in scattered if-statements.

The policy is intentionally centralized so that permissions can be reviewed,
rotated, and audited in one place instead of being duplicated across views and
service methods.
"""

from __future__ import annotations

from enum import Enum, auto


class Role(Enum):
    """Supported user roles in the healthcare platform."""

    STUDENT = "student"
    STAFF = "staff"
    NURSE = "nurse"
    DOCTOR = "doctor"
    ADMIN = "admin"


class Permission(Enum):
    """Fine-grained permissions used across the application."""

    APPOINTMENT_CREATE = "appointment_create"
    APPOINTMENT_READ_OWN = "appointment_read_own"
    APPOINTMENT_READ_ANY = "appointment_read_any"
    APPOINTMENT_CANCEL_OWN = "appointment_cancel_own"
    APPOINTMENT_CANCEL_ANY = "appointment_cancel_any"
    RECORD_READ = "record_read"
    RECORD_WRITE = "record_write"
    RECORD_DELETE = "record_delete"
    USER_CREATE = "user_create"
    USER_READ = "user_read"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    ADMIN_ACCESS = "admin_access"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.STUDENT: {
        Permission.APPOINTMENT_CREATE,
        Permission.APPOINTMENT_READ_OWN,
        Permission.APPOINTMENT_CANCEL_OWN,
    },
    Role.STAFF: {
        Permission.APPOINTMENT_CREATE,
        Permission.APPOINTMENT_READ_OWN,
        Permission.APPOINTMENT_CANCEL_OWN,
    },
    Role.NURSE: {
        Permission.APPOINTMENT_READ_ANY,
        Permission.APPOINTMENT_CANCEL_ANY,
        Permission.RECORD_READ,
        Permission.USER_READ,
    },
    Role.DOCTOR: {
        Permission.APPOINTMENT_READ_ANY,
        Permission.RECORD_READ,
        Permission.RECORD_WRITE,
        Permission.USER_READ,
    },
    Role.ADMIN: {
        Permission.APPOINTMENT_CREATE,
        Permission.APPOINTMENT_READ_OWN,
        Permission.APPOINTMENT_READ_ANY,
        Permission.APPOINTMENT_CANCEL_OWN,
        Permission.APPOINTMENT_CANCEL_ANY,
        Permission.RECORD_READ,
        Permission.RECORD_WRITE,
        Permission.RECORD_DELETE,
        Permission.USER_CREATE,
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.USER_DELETE,
        Permission.ADMIN_ACCESS,
    },
}


def has_permission(role: Role, permission: Permission) -> bool:
    """Return whether a role includes the requested permission."""
    if not isinstance(role, Role):
        raise TypeError("role must be a Role enum value")
    if not isinstance(permission, Permission):
        raise TypeError("permission must be a Permission enum value")

    return permission in ROLE_PERMISSIONS.get(role, set())


def get_permissions(role: Role) -> set[Permission]:
    """Return the full set of permissions granted to a role."""
    if not isinstance(role, Role):
        raise TypeError("role must be a Role enum value")

    return set(ROLE_PERMISSIONS.get(role, set()))


__all__ = ["Role", "Permission", "ROLE_PERMISSIONS", "has_permission", "get_permissions"]
