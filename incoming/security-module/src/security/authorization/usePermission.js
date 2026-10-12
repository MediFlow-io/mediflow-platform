/**
 * Assumptions:
 * - useAuth() is called inside AuthProvider.
 * - AuthContext.hasRole and hasPermission contain the canonical UI-side checks.
 * - The backend independently enforces every role and permission decision.
 */

import { useAuth } from "../auth/useAuth";

/**
 * Return reusable role and permission checks for component logic.
 *
 * @returns {{hasRole: (...roles: string[]) => boolean, hasPermission: (permission: string) => boolean, hasAnyRole: (...roles: string[]) => boolean, hasAnyPermission: (...permissions: string[]) => boolean}} Authorization helpers.
 *
 * @example
 * import { PERMISSIONS } from "../utils/constants";
 * import { usePermission } from "./usePermission";
 *
 * function RecordActions() {
 *   const { hasPermission } = usePermission();
 *
 *   return hasPermission(PERMISSIONS.RECORD_DELETE) ? (
 *     <button type="button">Delete record</button>
 *   ) : null;
 * }
 */
export function usePermission() {
  const { hasRole, hasPermission } = useAuth();

  const hasAnyRole = (...roles) => roles.some((role) => hasRole(role));
  const hasAnyPermission = (...permissions) => (
    permissions.some((permission) => hasPermission(permission))
  );

  return {
    hasRole,
    hasPermission,
    hasAnyRole,
    hasAnyPermission,
  };
}
