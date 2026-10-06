/**
 * Assumptions:
 * - This component is rendered inside AuthProvider.
 * - Permissions are backend-defined strings exposed through AuthContext.hasPermission().
 * - A supplied anyOf list uses OR semantics: one matching permission is sufficient.
 */

import { useAuth } from "../auth/useAuth";

/*
 * Use for hiding buttons/links the user can't use.
 * Backend MUST re-verify on the actual endpoint.
 */

/**
 * Render UI only when the current user has the required permission.
 *
 * @param {{permission?: string, anyOf?: string[], children: import("react").ReactNode, fallback?: import("react").ReactNode}} props - Gate props.
 * @returns {import("react").ReactNode} Children when authorized, otherwise fallback.
 *
 * @example
 * import { PERMISSIONS } from "../utils/constants";
 * import { PermissionGate } from "./PermissionGate";
 *
 * <PermissionGate permission={PERMISSIONS.ADMIN_ACCESS}>
 *   <a href="/admin">Admin Panel</a>
 * </PermissionGate>;
 */
export function PermissionGate({
  permission,
  anyOf,
  children,
  fallback = null,
}) {
  const { hasPermission } = useAuth();
  const hasRequiredPermission = typeof permission === "string"
    ? hasPermission(permission)
    : Array.isArray(anyOf) && anyOf.some((item) => hasPermission(item));

  return hasRequiredPermission ? children : fallback;
}
