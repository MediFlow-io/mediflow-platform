/**
 * Assumptions:
 * - This component is rendered inside a React Router v6 router and AuthProvider.
 * - roles contains backend role values understood by AuthContext.hasRole().
 * - The backend remains responsible for every authentication and authorization decision.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

/*
 * UI-only guard. Backend MUST enforce role checks on every endpoint.
 * Never rely on this for security.
 */

/**
 * Render content only when the authenticated user has one of the required roles.
 *
 * @param {{roles: string[], children?: import("react").ReactNode, fallback?: import("react").ReactNode}} props - Guard props.
 * @returns {JSX.Element} Protected content, fallback, loading status, or redirect.
 *
 * @example
 * import { RoleGuard } from "./RoleGuard";
 *
 * <RoleGuard roles={["doctor", "nurse"]}>
 *   <PatientRecords />
 * </RoleGuard>;
 *
 * @example
 * <Route element={<RoleGuard roles={["admin"]} />}>
 *   <Route path="/admin" element={<AdminDashboard />} />
 * </Route>;
 */
export function RoleGuard({ roles, children, fallback = null }) {
  const { isLoading, isAuthenticated, hasRole } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        role="status"
        aria-live="polite"
        aria-label="Restoring your session"
        className="flex min-h-[12rem] items-center justify-center"
      >
        <span
          aria-hidden="true"
          className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600"
        />
        <span className="sr-only">Restoring your session...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!Array.isArray(roles) || !hasRole(...roles)) {
    return fallback || <Navigate to="/unauthorized" replace />;
  }

  return children ?? <Outlet />;
}
