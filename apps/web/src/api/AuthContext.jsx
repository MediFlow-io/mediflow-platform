import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi, clearTokens, getAccessToken, getRefreshToken, onSessionExpired, setTokens } from "./client";

const AuthContext = createContext(null);

const toUser = (data) => ({
  id: data.id,
  unique_id: data.unique_id,
  name: data.name,
  email: data.email,
  role: data.role,
  mfaSetupRequired: Boolean(data.mfa_setup_required),
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // "checking" while a stored token is being verified after a page reload.
  const [status, setStatus] = useState(() => (getAccessToken() ? "checking" : "signed-out"));

  const signOutLocally = useCallback(() => {
    clearTokens();
    setUser(null);
    setStatus("signed-out");
  }, []);

  useEffect(() => onSessionExpired(signOutLocally), [signOutLocally]);

  useEffect(() => {
    if (status !== "checking") return;
    authApi
      .me()
      .then((data) => {
        setUser(toUser(data));
        setStatus("signed-in");
      })
      .catch(signOutLocally);
  }, [status, signOutLocally]);

  const finishSignIn = useCallback((data) => {
    setTokens({ access: data.access, refresh: data.refresh });
    setUser(toUser(data));
    setStatus("signed-in");
    return data;
  }, []);

  // Returns { mfaRequired, mfaToken } when the account uses two-step sign-in; call verifyMfa next.
  const login = useCallback(async (unique_id, password) => {
    const data = await authApi.loginStudent(unique_id, password);
    if (data.mfa_required) return { mfaRequired: true, mfaToken: data.mfa_token };
    return finishSignIn(data);
  }, [finishSignIn]);

  const verifyMfa = useCallback(async (mfaToken, code) => finishSignIn(await authApi.verifyMfa(mfaToken, code)), [finishSignIn]);

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    try {
      if (refresh) await authApi.logout(refresh);
    } catch {
      // Signing out locally is what matters; the refresh token expires on its own.
    } finally {
      signOutLocally();
    }
  }, [signOutLocally]);

  return (
    <AuthContext.Provider value={{ user, status, isAuthenticated: status === "signed-in", login, verifyMfa, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
