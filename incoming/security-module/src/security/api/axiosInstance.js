/**
 * Assumptions:
 * - VITE_API_URL contains the backend API origin or base path.
 * - The backend uses cookies for refresh-token and CSRF protection.
 * - Authentication headers and 401 handling are attached separately by authInterceptor.js.
 */

import axios from "axios";

/**
 * Shared raw Axios client for API requests.
 *
 * Authentication logic intentionally does not belong here. The auth interceptor
 * attaches access tokens and handles authentication failures separately.
 *
 * @example
 * import { api } from "@/security/api/axiosInstance";
 *
 * const response = await api.get("/appointments");
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});
