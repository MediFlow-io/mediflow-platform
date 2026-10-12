/**
 * Assumptions:
 * - This component is rendered inside a React Router v6 router.
 * - AuthProvider supplies isLoading and isAuthenticated through useAuth().
 * - The backend remains responsible for enforcing authentication and authorization.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

/**
 * Protect a route from unauthenticated access.
 *
 * Loading is displayed while the provider restores the session. Unauthenticated
 * users are redirected with the attempted location so login can return them to it.
 *
 * @param {{children?: import("react").ReactNode}} props - Optional wrapped route content.
 * @returns {JSX.Element} Protected content, nested outlet, loading status, or redirect.
 *
 * @example
 * import { Route } from "react-router-dom";
 *
 * <Route element={<ProtectedRoute />}>
 *   <Route path="/appointments" element={<AppointmentsPage />} />
 * </Route>;
 *
 * @example
 * <ProtectedRoute>
 *   <AppointmentsPage />
 * </ProtectedRoute>;
 */
export function ProtectedRoute({ children }) {
  const { isLoading, isAuthenticated } = useAuth();
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

  return children ?? <Outlet />;
}
