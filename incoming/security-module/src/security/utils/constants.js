/**
 * Assumptions:
 * - Backend role values are lowercase strings, matching Role.value in rbac.py.
 * - Frontend consumers need permission strings, matching Permission.value in rbac.py.
 *
 * This MUST stay in sync with backend/security/authorization/rbac.py.
 * This is for UI only - the backend is the source of truth.
 * If backend and frontend disagree, the backend wins.
 */

/** Supported user roles. */
export const ROLES = Object.freeze({
  STUDENT: "student",
  STAFF: "staff",
  NURSE: "nurse",
  DOCTOR: "doctor",
  ADMIN: "admin",
});

/** Fine-grained permissions used across the application. */
export const PERMISSIONS = Object.freeze({
  APPOINTMENT_CREATE: "appointment_create",
  APPOINTMENT_READ_OWN: "appointment_read_own",
  APPOINTMENT_READ_ANY: "appointment_read_any",
  APPOINTMENT_CANCEL_OWN: "appointment_cancel_own",
  APPOINTMENT_CANCEL_ANY: "appointment_cancel_any",
  RECORD_READ: "record_read",
  RECORD_WRITE: "record_write",
  RECORD_DELETE: "record_delete",
  USER_CREATE: "user_create",
  USER_READ: "user_read",
  USER_UPDATE: "user_update",
  USER_DELETE: "user_delete",
  ADMIN_ACCESS: "admin_access",
});

/** Role-to-permission assignments mirrored from the backend RBAC policy. */
export const ROLE_PERMISSIONS = Object.freeze({
  [ROLES.STUDENT]: Object.freeze([
    PERMISSIONS.APPOINTMENT_CREATE,
    PERMISSIONS.APPOINTMENT_READ_OWN,
    PERMISSIONS.APPOINTMENT_CANCEL_OWN,
  ]),
  [ROLES.STAFF]: Object.freeze([
    PERMISSIONS.APPOINTMENT_CREATE,
    PERMISSIONS.APPOINTMENT_READ_OWN,
    PERMISSIONS.APPOINTMENT_CANCEL_OWN,
  ]),
  [ROLES.NURSE]: Object.freeze([
    PERMISSIONS.APPOINTMENT_READ_ANY,
    PERMISSIONS.APPOINTMENT_CANCEL_ANY,
    PERMISSIONS.RECORD_READ,
    PERMISSIONS.USER_READ,
  ]),
  [ROLES.DOCTOR]: Object.freeze([
    PERMISSIONS.APPOINTMENT_READ_ANY,
    PERMISSIONS.RECORD_READ,
    PERMISSIONS.RECORD_WRITE,
    PERMISSIONS.USER_READ,
  ]),
  [ROLES.ADMIN]: Object.freeze([
    PERMISSIONS.APPOINTMENT_CREATE,
    PERMISSIONS.APPOINTMENT_READ_OWN,
    PERMISSIONS.APPOINTMENT_READ_ANY,
    PERMISSIONS.APPOINTMENT_CANCEL_OWN,
    PERMISSIONS.APPOINTMENT_CANCEL_ANY,
    PERMISSIONS.RECORD_READ,
    PERMISSIONS.RECORD_WRITE,
    PERMISSIONS.RECORD_DELETE,
    PERMISSIONS.USER_CREATE,
    PERMISSIONS.USER_READ,
    PERMISSIONS.USER_UPDATE,
    PERMISSIONS.USER_DELETE,
    PERMISSIONS.ADMIN_ACCESS,
  ]),
});

/**
 * Return the permissions granted to a role.
 *
 * @param {string} role - A value from ROLES.
 * @returns {string[]} A new permission array, or an empty array for an unknown role.
 */
export function getPermissionsForRole(role) {
  return [...(ROLE_PERMISSIONS[role] || [])];
}

/**
 * Usage example:
 *
 * import { ROLES, PERMISSIONS, getPermissionsForRole } from "./constants";
 *
 * const permissions = getPermissionsForRole(ROLES.STUDENT);
 * const canBook = permissions.includes(PERMISSIONS.APPOINTMENT_CREATE);
 */
