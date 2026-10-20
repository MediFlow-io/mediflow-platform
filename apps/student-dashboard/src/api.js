// Talks to the MediFlow core API on the same origin. `npm run dev` proxies /api/auth to the Go gateway
// and /api to Django (vite.config.js). Students only ever read their own record (/api/me/health).
const TOKEN_KEY = "mediflow_student_access";
const REFRESH_KEY = "mediflow_student_refresh";

const store = {
  get access() { return localStorage.getItem(TOKEN_KEY); },
  get refresh() { return localStorage.getItem(REFRESH_KEY); },
  set({ access, refresh }) {
    if (access) localStorage.setItem(TOKEN_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

let refreshing = null;
function refreshTokens() {
  if (!store.refresh) return Promise.resolve(false);
  refreshing ??= fetch("/api/auth/token/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: store.refresh }),
  })
    .then(async (res) => (res.ok ? (store.set(await res.json()), true) : (store.clear(), false)))
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

async function request(path, { method = "GET", body, auth = true, retried = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && store.access) headers.Authorization = `Bearer ${store.access}`;
  let res;
  try {
    res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError("Can't reach the health centre server. Check your connection and try again.", 0);
  }
  if (res.status === 401 && auth && !retried && (await refreshTokens())) {
    return request(path, { method, body, auth, retried: true });
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // Field errors look like {"time": ["The clinic takes appointments Mon-Fri..."]}: show the messages.
    const fieldMessages = data && typeof data === "object" && !data.detail ? Object.values(data).flat().join(" ") : "";
    throw new ApiError(data?.detail || fieldMessages || `Something went wrong (${res.status}).`, res.status);
  }
  return data;
}

export const isSignedIn = () => Boolean(store.access);

export async function signIn(uniqueId, password) {
  const data = await request("/api/auth/login", { method: "POST", body: { unique_id: uniqueId, password }, auth: false });
  store.set(data);
  return data;
}

export async function signOut() {
  const refresh = store.refresh;
  store.clear();
  if (refresh) await request("/api/auth/logout", { method: "POST", body: { refresh }, auth: false }).catch(() => {});
}

export const getMe = () => request("/api/me");
export const getMyHealth = () => request("/api/me/health");
export const getMyAppointments = () => request("/api/appointments/mine");
export const getDepartments = () => request("/api/departments");
export const requestAppointment = (body) => request("/api/appointments", { method: "POST", body });
export const cancelAppointment = (id) => request(`/api/appointments/${id}/cancel`, { method: "POST" });

// Notifications come from the Flask notification service.
export const getNotifications = () => request("/api/notifications?limit=50");
export const markNotificationRead = (id) => request(`/api/notifications/${id}/read`, { method: "POST" });
export const markAllNotificationsRead = () => request("/api/notifications/read-all", { method: "POST" });
