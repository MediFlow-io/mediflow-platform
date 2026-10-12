/**
 * Assumptions:
 * - The application renders AuthProvider inside a React Router v6 router.
 * - The API returns an accessToken and user after successful login.
 * - Refresh authentication is maintained by an HttpOnly cookie; access tokens stay in memory.
 * - AuthContext consumers use the useAuth() hook rather than importing the context directly.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "./AuthContext";
import { api } from "../api/axiosInstance";
import { setupInterceptors } from "../api/authInterceptor";
import {
  clearAccessToken,
  setAccessToken,
} from "./tokenManager";
import { getPermissionsForRole } from "../utils/constants";

/**
 * Error thrown when the backend requires a second-factor code before login completes.
 */
export class MFARequiredError extends Error {
  constructor() {
    super("Multi-factor authentication is required.");
    this.name = "MFARequiredError";
  }
}

/**
 * Provide authentication state and actions to the application.
 *
 * @param {{children: import("react").ReactNode}} props - Provider props.
 * @returns {JSX.Element} Authentication context provider.
 */
export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const isAuthenticated = Boolean(user);

  const handleUnauthorized = useCallback(() => {
    clearAccessToken();
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  useEffect(() => {
    const interceptorIds = setupInterceptors(api, {
      onUnauthorized: handleUnauthorized,
    });

    return () => {
      api.interceptors.request.eject(interceptorIds.requestInterceptorId);
      api.interceptors.response.eject(interceptorIds.responseInterceptorId);
    };
  }, [handleUnauthorized]);

  const refreshUser = useCallback(async () => {
    try {
      const response = await api.get("/api/auth/me");
      const nextUser = response.data?.user ?? response.data;
      setUser(nextUser || null);
    } catch (error) {
      if (error?.response?.status === 401) {
        handleUnauthorized();
        return;
      }
      throw error;
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    let isMounted = true;

    async function restoreSession() {
      try {
        const response = await api.get("/api/auth/me");
        if (isMounted) {
          const restoredUser = response.data?.user ?? response.data;
          setUser(restoredUser || null);
        }
      } catch (error) {
        if (isMounted && error?.response?.status === 401) {
          clearAccessToken();
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    restoreSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (email, password, mfaCode) => {
    const payload = { email, password };
    if (mfaCode) {
      payload.mfaCode = mfaCode;
    }

    try {
      const response = await api.post("/api/auth/login", payload);
      const data = response.data || {};

      if (data.mfaRequired || data.mfa_required) {
        throw new MFARequiredError();
      }

      setAccessToken(data.accessToken);
      setUser(data.user);
    } catch (error) {
      if (error instanceof MFARequiredError) {
        throw error;
      }

      if (error?.response?.data?.mfaRequired || error?.response?.data?.mfa_required) {
        throw new MFARequiredError();
      }

      throw new Error("Invalid credentials");
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      clearAccessToken();
      setUser(null);
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  const hasRole = useCallback(
    (...roles) => Boolean(user?.role && roles.includes(user.role)),
    [user],
  );

  const hasPermission = useCallback(
    (permission) => {
      if (!user?.role || typeof permission !== "string") {
        return false;
      }

      return getPermissionsForRole(user.role).includes(permission);
    },
    [user],
  );

  const contextValue = useMemo(
    () => ({
      user,
      isAuthenticated,
      isLoading,
      login,
      logout,
      refreshUser,
      hasRole,
      hasPermission,
    }),
    [
      user,
      isAuthenticated,
      isLoading,
      login,
      logout,
      refreshUser,
      hasRole,
      hasPermission,
    ],
  );

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

/**
 * Usage example:
 *
 * import { AuthProvider } from "./security/auth/AuthProvider";
 *
 * <BrowserRouter>
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 * </BrowserRouter>;
 */
