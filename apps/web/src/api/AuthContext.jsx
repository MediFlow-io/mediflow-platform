import { createContext, useContext, useState, useCallback } from "react";
import { authApi, setTokens, clearTokens, getAccessToken } from "./client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  const login = useCallback(async (unique_id, password) => {
    const data = await authApi.loginStudent(unique_id, password);
    setTokens({ access: data.access, refresh: data.refresh });
    setUser({
      id: data.id,
      unique_id: data.unique_id,
      name: data.name,
      email: data.email,
      role: data.role,
    });
    return data;
  }, []);

  const logout = useCallback(async () => {
    const refresh = localStorage.getItem("mediflow_refresh_token");
    try {
      if (refresh) await authApi.logout(refresh);
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  const isAuthenticated = Boolean(getAccessToken());

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
