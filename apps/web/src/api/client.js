// Auth requests go through the Go gateway (/api/auth/*); everything else goes to the Django API.
// Both default to the same origin: in Docker, Nginx routes them; in `npm run dev`, Vite proxies them
// (see vite.config.js). Override with VITE_GATEWAY_URL / VITE_API_URL only for unusual setups.
const GATEWAY_BASE_URL = import.meta.env.VITE_GATEWAY_URL ?? "";
const API_BASE_URL = import.meta.env.VITE_API_URL ?? "";

const TOKEN_KEY = "mediflow_access_token";
const REFRESH_KEY = "mediflow_refresh_token";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens({ access, refresh }) {
  if (access) localStorage.setItem(TOKEN_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// DRF errors look like {"detail": "..."} or {"fullName": ["This field is required."]}.
export function errorMessage(data, status) {
  if (!data || typeof data !== "object") return `Request failed (${status}).`;
  if (typeof data.detail === "string") return data.detail;
  const parts = Object.entries(data).map(([field, value]) => {
    const text = [value].flat(Infinity).map((v) => (typeof v === "object" ? errorMessage(v, status) : v)).join(" ");
    return field === "non_field_errors" ? text : `${field}: ${text}`;
  });
  return parts.join(" ") || `Request failed (${status}).`;
}

// Refresh tokens are single-use (rotated server-side), so concurrent 401s share one refresh call.
let refreshInFlight = null;

function refreshAccessToken() {
  const refresh = getRefreshToken();
  if (!refresh) return Promise.resolve(false);
  refreshInFlight ??= fetch(`${GATEWAY_BASE_URL}/api/auth/token/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  })
    .then(async (res) => {
      if (!res.ok) {
        clearTokens();
        return false;
      }
      setTokens(await res.json());
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

const listeners = new Set();
/** Called when the session can't be recovered (refresh failed), so the UI can sign out. */
export function onSessionExpired(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function request(path, { method = "GET", body, auth = true, retried = false } = {}) {
  const base = path.startsWith("/api/auth/") ? GATEWAY_BASE_URL : API_BASE_URL;
  const headers = { "Content-Type": "application/json" };
  const token = auth ? getAccessToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${base}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError("Can't reach the MediFlow server. Check your connection and try again.", 0, null);
  }

  if (res.status === 401 && token && !retried) {
    if (await refreshAccessToken()) return request(path, { method, body, auth, retried: true });
    listeners.forEach((listener) => listener());
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // Some endpoints (e.g. logout) return no body.
  }
  if (!res.ok) throw new ApiError(errorMessage(data, res.status), res.status, data);
  return data;
}

export const authApi = {
  loginStudent: (unique_id, password) =>
    request("/api/auth/login", { method: "POST", body: { unique_id, password }, auth: false }),

  registerStudent: (payload) =>
    request("/api/auth/register/student", { method: "POST", body: payload, auth: false }),

  registerStaff: (payload) => request("/api/auth/register/staff", { method: "POST", body: payload }),

  logout: (refresh) => request("/api/auth/logout", { method: "POST", body: { refresh } }),

  me: () => request("/api/me"),

  // The server revokes all refresh tokens on a password change and returns a new pair.
  changePassword: async (payload) => {
    const data = await request("/api/auth/change-password", { method: "POST", body: payload });
    setTokens(data);
    return data;
  },
};

const qs = (params) => {
  const entries = Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? `?${new URLSearchParams(entries)}` : "";
};

export const mediflowApi = {
  dashboard: () => request("/api/dashboard"),
  departments: () => request("/api/departments"),
  queue: (department) => request(`/api/queue${qs({ department })}`),
  visits: (params) => request(`/api/visits${qs(params)}`),
  checkIn: (payload) => request("/api/visits", { method: "POST", body: payload }),
  visitAction: (id, action) => request(`/api/visits/${id}/${action}`, { method: "POST" }),
  patients: (search) => request(`/api/patients${qs({ search })}`),
  patient: (id) => request(`/api/patients/${id}`),
  createPatient: (payload) => request("/api/patients", { method: "POST", body: payload }),
  updatePatient: (id, payload) => request(`/api/patients/${id}`, { method: "PATCH", body: payload }),
  users: (params) => request(`/api/users${qs(params)}`),
  updateUser: (id, payload) => request(`/api/users/${id}`, { method: "PATCH", body: payload }),
  triageSuggestion: (payload) => request("/api/ai/triage", { method: "POST", body: payload }),
};
