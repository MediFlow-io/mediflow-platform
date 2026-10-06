/**
 * Assumptions:
 * - AuthContext is provided by AuthProvider higher in the React tree.
 * - AuthContext uses null as its default value to detect provider misuse.
 */

import { useContext } from "react";
import { AuthContext } from "./AuthContext";

/**
 * Consume authentication state and actions from AuthProvider.
 *
 * @returns {import("./AuthContext").AuthContextValue} Current authentication context value.
 * @throws {Error} If called outside AuthProvider.
 *
 * @example
 * import { useAuth } from "./useAuth";
 *
 * function AccountMenu() {
 *   const { user, logout } = useAuth();
 *   return <button onClick={logout}>{user.fullName}</button>;
 * }
 */
export function useAuth() {
  const context = useContext(AuthContext);

  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}
