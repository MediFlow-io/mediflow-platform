/**
 * Assumptions:
 * - Values are JSON-serializable and are stored under the current application origin.
 * - This module runs in a browser, but may also be imported during SSR or testing.
 * - clearAll() is intended to clear both localStorage and sessionStorage for this origin.
 *
 * Never store secrets here. Access tokens live in memory (see tokenManager.js).
 * Refresh tokens live in HttpOnly cookies.
 */

const FORBIDDEN_KEYS = new Set([
  "accessToken",
  "refreshToken",
  "jwt",
  "password",
  "ssn",
  "mfaSecret",
]);

/**
 * Return a browser storage area when it is available.
 *
 * @param {boolean} persistent - Whether to use localStorage instead of sessionStorage.
 * @returns {Storage|null} The selected storage area, or null outside a browser.
 */
function getStorage(persistent = false) {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return persistent ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

/**
 * Reject keys that could be used to store credentials or sensitive identifiers.
 *
 * @param {string} key - Storage key to validate.
 * @returns {void}
 * @throws {TypeError} If the key is not a string.
 * @throws {Error} If the key is forbidden.
 */
function assertAllowedKey(key) {
  if (typeof key !== "string") {
    throw new TypeError("Storage keys must be strings.");
  }

  if (FORBIDDEN_KEYS.has(key)) {
    throw new Error(`Refusing to store forbidden key: ${key}`);
  }
}

/**
 * Store a non-sensitive JSON-serializable value in browser storage.
 *
 * @param {string} key - Storage key.
 * @param {*} value - JSON-serializable preference value.
 * @param {{persistent?: boolean}} [options] - Storage persistence options.
 * @returns {boolean} Whether the value was stored successfully.
 * @throws {TypeError|Error} If the key is invalid or forbidden.
 */
export function setItem(key, value, { persistent = false } = {}) {
  assertAllowedKey(key);

  const storage = getStorage(persistent);
  if (!storage) {
    return false;
  }

  try {
    storage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

/**
 * Read and parse a stored JSON value.
 *
 * Malformed JSON, unavailable storage, and missing keys return the fallback.
 *
 * @param {string} key - Storage key.
 * @param {*} [fallback=null] - Value returned when the item cannot be read.
 * @returns {*} The parsed value or fallback.
 * @throws {TypeError|Error} If the key is invalid or forbidden.
 */
export function getItem(key, fallback = null) {
  assertAllowedKey(key);

  for (const storage of [getStorage(false), getStorage(true)]) {
    if (!storage) {
      continue;
    }

    try {
      const storedValue = storage.getItem(key);
      if (storedValue !== null) {
        return JSON.parse(storedValue);
      }
    } catch {
      return fallback;
    }
  }

  return fallback;
}

/**
 * Remove a value from both browser storage areas.
 *
 * @param {string} key - Storage key.
 * @returns {boolean} Whether removal completed without storage errors.
 * @throws {TypeError|Error} If the key is invalid or forbidden.
 */
export function removeItem(key) {
  assertAllowedKey(key);

  let succeeded = true;
  for (const storage of [getStorage(false), getStorage(true)]) {
    if (!storage) {
      continue;
    }

    try {
      storage.removeItem(key);
    } catch {
      succeeded = false;
    }
  }

  return succeeded;
}

/**
 * Clear all entries from both browser storage areas.
 *
 * @returns {boolean} Whether both available storage areas were cleared successfully.
 */
export function clearAll() {
  let succeeded = true;
  for (const storage of [getStorage(false), getStorage(true)]) {
    if (!storage) {
      continue;
    }

    try {
      storage.clear();
    } catch {
      succeeded = false;
    }
  }

  return succeeded;
}

/**
 * Usage example:
 *
 * import { clearAll, getItem, removeItem, setItem } from "./secureStorage";
 *
 * setItem("theme", "dark");
 * setItem("language", "en", { persistent: true });
 * const theme = getItem("theme", "light");
 * removeItem("theme");
 * clearAll();
 */
