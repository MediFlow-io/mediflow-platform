/**
 * Assumptions:
 * - Access tokens are JWT strings with a numeric exp claim in seconds since the Unix epoch.
 * - This module only performs client-side expiry inspection; the backend verifies signatures,
 *   issuer, audience, revocation, and all other security claims.
 * - A storage event in another tab invalidates this tab's in-memory token as a defense-in-depth
 *   response to cross-tab session changes.
 *
 * localStorage/sessionStorage are readable by any XSS payload. In-memory tokens are lost on
 * refresh but much safer. We refresh via HttpOnly cookie.
 */

let accessToken = null;

/**
 * Decode a JWT payload without treating it as trusted data.
 *
 * @param {string} token - JWT string to decode.
 * @returns {Record<string, unknown>|null} Decoded payload, or null when malformed.
 */
function decodePayload(token) {
  if (typeof token !== "string") {
    return null;
  }

  const parts = token.split(".");
  if (parts.length !== 3 || !parts[1]) {
    return null;
  }

  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const payload = JSON.parse(atob(padded));

    return payload && typeof payload === "object" && !Array.isArray(payload)
      ? payload
      : null;
  } catch {
    return null;
  }
}

/**
 * Determine whether a JWT is expired or cannot be safely inspected.
 *
 * This does not verify the JWT signature. The backend remains responsible for
 * authentication and authorization decisions.
 *
 * @param {string} token - JWT string to inspect.
 * @returns {boolean} True when the token is expired or invalid for client use.
 */
export function isTokenExpired(token) {
  const payload = decodePayload(token);
  if (!payload || typeof payload.exp !== "number" || !Number.isFinite(payload.exp)) {
    return true;
  }

  return payload.exp <= Math.floor(Date.now() / 1000);
}

/**
 * Store an access token in memory only.
 *
 * @param {string} token - Access token issued by the backend.
 * @returns {void}
 * @throws {TypeError} If token is not a string.
 */
export function setAccessToken(token) {
  if (typeof token !== "string" || token.length === 0) {
    throw new TypeError("Access token must be a non-empty string.");
  }

  accessToken = token;
}

/**
 * Return the current access token when it is still valid according to its exp claim.
 * Expired or malformed tokens are cleared before returning null.
 *
 * @returns {string|null} Current non-expired access token, or null.
 */
export function getAccessToken() {
  if (!accessToken || isTokenExpired(accessToken)) {
    clearAccessToken();
    return null;
  }

  return accessToken;
}

/**
 * Clear the in-memory access token.
 *
 * @returns {null} Always returns null for convenient auth-state cleanup.
 */
export function clearAccessToken() {
  accessToken = null;
  return null;
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", clearAccessToken);
}

/**
 * Usage example:
 *
 * import {
 *   clearAccessToken,
 *   getAccessToken,
 *   setAccessToken,
 * } from "./tokenManager";
 *
 * setAccessToken(accessTokenFromLoginResponse);
 * const token = getAccessToken();
 * clearAccessToken();
 */
