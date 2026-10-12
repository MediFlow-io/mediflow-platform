/**
 * Assumptions:
 * - api is the configured Axios instance from axiosInstance.js.
 * - The refresh endpoint rotates the refresh token in an HttpOnly cookie and returns
 *   a new access token in accessToken, access, or token.
 * - onUnauthorized is responsible for application-level navigation or auth-state cleanup.
 * - This is client-side convenience logic; the backend remains the security authority.
 */

import { getCsrfToken } from "./csrfHandler";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "../auth/tokenManager";

const REFRESH_ENDPOINT = "/api/auth/refresh";
const HTTP_METHODS_WITHOUT_BODY = new Set(["GET", "HEAD", "OPTIONS"]);

/**
 * Read a response header from either AxiosHeaders or a plain object.
 *
 * @param {object} headers - Axios response headers.
 * @param {string} name - Header name.
 * @returns {string|null} Header value, if present.
 */
function getHeader(headers, name) {
  if (!headers) {
    return null;
  }

  if (typeof headers.get === "function") {
    return headers.get(name) || null;
  }

  return headers[name] || headers[name.toLowerCase()] || null;
}

/**
 * Extract the refreshed access token without trusting any other response field.
 *
 * @param {*} data - Refresh response payload.
 * @returns {string|null} New access token, if present.
 */
function getRefreshedAccessToken(data) {
  if (!data || typeof data !== "object") {
    return null;
  }

  const token = data.accessToken || data.access || data.token;
  return typeof token === "string" && token.length > 0 ? token : null;
}

/**
 * Attach security interceptors to an Axios instance.
 *
 * The refresh-token rotation pattern keeps the refresh token in an HttpOnly cookie.
 * When an access token expires, one failed request triggers a refresh; the backend
 * rotates the cookie and returns a new short-lived access token. The original request
 * is retried once, and failed refreshes clear the in-memory token and end the session.
 *
 * @param {import("axios").AxiosInstance} api - Configured Axios instance.
 * @param {{onUnauthorized?: function}} [options] - Unauthorized callback options.
 * @returns {{requestInterceptorId: number, responseInterceptorId: number}} Interceptor IDs.
 */
export function setupInterceptors(api, { onUnauthorized = () => {} } = {}) {
  if (!api || typeof api.interceptors?.request?.use !== "function") {
    throw new TypeError("A configured Axios instance is required.");
  }

  if (typeof onUnauthorized !== "function") {
    throw new TypeError("onUnauthorized must be a function.");
  }

  const requestInterceptorId = api.interceptors.request.use((config) => {
    const token = getAccessToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }

    const method = String(config.method || "GET").toUpperCase();
    if (!HTTP_METHODS_WITHOUT_BODY.has(method)) {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        config.headers = config.headers || {};
        config.headers["X-CSRF-TOKEN"] = csrfToken;
      }
    }

    return config;
  });

  const responseInterceptorId = api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const response = error?.response;
      const originalRequest = response?.config;
      const status = response?.status;

      if (status === 403) {
        console.warn("Request forbidden by the backend.");
        return Promise.reject(error);
      }

      if (status === 429) {
        const retryAfter = getHeader(response.headers, "retry-after");
        if (retryAfter !== null) {
          error.retryAfter = retryAfter;
        }
        return Promise.reject(error);
      }

      const isRefreshRequest = originalRequest?.url === REFRESH_ENDPOINT;
      if (status !== 401 || !originalRequest || originalRequest._retry || isRefreshRequest) {
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      try {
        const refreshResponse = await api.post(
          REFRESH_ENDPOINT,
          undefined,
          { _skipAuthRefresh: true, withCredentials: true },
        );
        const refreshedToken = getRefreshedAccessToken(refreshResponse.data);

        if (!refreshedToken) {
          throw new Error("Token refresh did not return an access token.");
        }

        setAccessToken(refreshedToken);
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${refreshedToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        clearAccessToken();
        onUnauthorized();
        return Promise.reject(refreshError);
      }
    },
  );

  return { requestInterceptorId, responseInterceptorId };
}

/**
 * Usage example:
 *
 * import { api } from "./axiosInstance";
 * import { setupInterceptors } from "./authInterceptor";
 *
 * setupInterceptors(api, {
 *   onUnauthorized: () => authLogout(),
 * });
 */
