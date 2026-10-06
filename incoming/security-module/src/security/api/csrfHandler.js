/**
 * Assumptions:
 * - The backend sets an XSRF-TOKEN cookie on GET /api/csrf-token.
 * - The frontend sends the token as X-CSRF-TOKEN for state-changing requests.
 * - Axios is available as a project dependency and is configured to send credentials.
 *
 * CSRF protection flow:
 * Backend sets a CSRF cookie (not HttpOnly). Frontend reads it and sends it
 * in the X-CSRF-TOKEN header. Backend compares cookie + header. Attacker
 * can't read the cookie cross-origin, so they can't forge the header.
 */

import axios from "axios";

const CSRF_COOKIE_NAME = "XSRF-TOKEN";
const CSRF_ENDPOINT = "/api/csrf-token";

/**
 * Read the backend-issued CSRF token from document.cookie.
 *
 * @returns {string|null} The decoded CSRF token, or null when unavailable.
 */
export function getCsrfToken() {
  if (typeof document === "undefined" || !document.cookie) {
    return null;
  }

  const cookie = document.cookie
    .split(";")
    .map((entry) => entry.trim())
    .find((entry) => entry.startsWith(`${CSRF_COOKIE_NAME}=`));

  if (!cookie) {
    return null;
  }

  const value = cookie.slice(CSRF_COOKIE_NAME.length + 1);
  try {
    return decodeURIComponent(value);
  } catch {
    return value || null;
  }
}

/**
 * Ask the backend to issue or refresh the CSRF cookie.
 *
 * @returns {Promise<import("axios").AxiosResponse>} Axios response from the CSRF endpoint.
 * @throws {Error} When the backend request fails.
 */
export function refreshCsrfToken() {
  return axios.get(CSRF_ENDPOINT, { withCredentials: true });
}

/**
 * Usage example:
 *
 * import { getCsrfToken, refreshCsrfToken } from "./csrfHandler";
 *
 * await refreshCsrfToken();
 * const csrfToken = getCsrfToken();
 * axios.post("/api/appointments", data, {
 *   headers: { "X-CSRF-TOKEN": csrfToken },
 *   withCredentials: true,
 * });
 */
