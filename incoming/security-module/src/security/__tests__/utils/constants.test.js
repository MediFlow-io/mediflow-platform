import { describe, expect, it } from "vitest";
import {
  PERMISSIONS,
  ROLE_PERMISSIONS,
  ROLES,
  getPermissionsForRole,
} from "../../utils/constants";

describe("security utils constants", () => {
  it("exports the supported roles as immutable values", () => {
    expect(ROLES).toEqual({
      STUDENT: "student",
      STAFF: "staff",
      NURSE: "nurse",
      DOCTOR: "doctor",
      ADMIN: "admin",
    });
    expect(Object.isFrozen(ROLES)).toBe(true);
  });

  it("exports the complete permission catalog as immutable values", () => {
    expect(Object.keys(PERMISSIONS)).toHaveLength(13);
    expect(PERMISSIONS).toEqual({
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
    expect(Object.isFrozen(PERMISSIONS)).toBe(true);
  });

  it("mirrors the backend role-permission assignments", () => {
    expect(ROLE_PERMISSIONS).toEqual({
      student: [
        "appointment_create",
        "appointment_read_own",
        "appointment_cancel_own",
      ],
      staff: [
        "appointment_create",
        "appointment_read_own",
        "appointment_cancel_own",
      ],
      nurse: [
        "appointment_read_any",
        "appointment_cancel_any",
        "record_read",
        "user_read",
      ],
      doctor: [
        "appointment_read_any",
        "record_read",
        "record_write",
        "user_read",
      ],
      admin: [
        "appointment_create",
        "appointment_read_own",
        "appointment_read_any",
        "appointment_cancel_own",
        "appointment_cancel_any",
        "record_read",
        "record_write",
        "record_delete",
        "user_create",
        "user_read",
        "user_update",
        "user_delete",
        "admin_access",
      ],
    });

    expect(Object.isFrozen(ROLE_PERMISSIONS)).toBe(true);
    Object.values(ROLE_PERMISSIONS).forEach((permissions) => {
      expect(Object.isFrozen(permissions)).toBe(true);
    });
  });

  it("returns permissions for each known role", () => {
    expect(getPermissionsForRole(ROLES.STUDENT)).toEqual([
      PERMISSIONS.APPOINTMENT_CREATE,
      PERMISSIONS.APPOINTMENT_READ_OWN,
      PERMISSIONS.APPOINTMENT_CANCEL_OWN,
    ]);
    expect(getPermissionsForRole(ROLES.NURSE)).toContain(PERMISSIONS.RECORD_READ);
    expect(getPermissionsForRole(ROLES.DOCTOR)).toContain(PERMISSIONS.RECORD_WRITE);
    expect(getPermissionsForRole(ROLES.ADMIN)).toContain(PERMISSIONS.ADMIN_ACCESS);
  });

  it("returns a defensive copy instead of the frozen role array", () => {
    const permissions = getPermissionsForRole(ROLES.STUDENT);
    permissions.push("unexpected_permission");

    expect(permissions).toHaveLength(4);
    expect(getPermissionsForRole(ROLES.STUDENT)).toHaveLength(3);
  });

  it.each([undefined, null, "", "unknown", 0])(
    "returns no permissions for invalid role %p",
    (role) => {
      expect(getPermissionsForRole(role)).toEqual([]);
    },
  );

  it("does not expose executable or HTML permission values", () => {
    const allValues = [
      ...Object.values(ROLES),
      ...Object.values(PERMISSIONS),
      ...Object.values(ROLE_PERMISSIONS).flat(),
    ];

    expect(allValues.some((value) => /<script|javascript:/i.test(value))).toBe(false);
  });
});
