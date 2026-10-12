/**
 * Assumptions:
 * - AuthProvider supplies the complete value described below.
 * - Consumers access this context through the useAuth() hook.
 * - A null default makes using the context outside AuthProvider detectable by the hook.
 */

import { createContext } from "react";

/**
 * Authentication context shared by AuthProvider and useAuth().
 *
 * @typedef {object} AuthContextValue
 * @property {{id: string|number, email: string, fullName: string, role: string, roles: string[], mfaEnabled: boolean}|null} user
 * @property {boolean} isAuthenticated
 * @property {boolean} isLoading
 * @property {(email: string, password: string, mfaCode?: string) => Promise<void>} login
 * @property {() => Promise<void>} logout
 * @property {() => Promise<void>} refreshUser
 * @property {(...roles: string[]) => boolean} hasRole
 * @property {(permission: string) => boolean} hasPermission
 */

/**
 * React context containing the current authentication state and actions.
 *
 * Do not import this directly - use useAuth() hook.
 *
 * @type {import("react").Context<AuthContextValue|null>}
 */
export const AuthContext = createContext(null);
