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

// On free hosting, idle services sleep and take up to a minute to start. Until then the host answers with
// its own 502/503 page (never JSON, unlike our APIs): nothing reached the service, so it's safe to repeat.
const isHostErrorPage = (res) =>
  (res.status === 502 || res.status === 503) && !(res.headers.get("Content-Type") ?? "").includes("json");

async function fetchAwake(url, options) {
  const deadline = Date.now() + 100_000;
  for (let delay = 2000; ; delay = Math.min(delay * 2, 6000)) {
    const res = await fetch(url, options);
    if (!isHostErrorPage(res) || Date.now() + delay > deadline) return res;
    if (delay === 2000) wakeDirect(); // found a service asleep: wake it from the browser
    await new Promise((resolve) => setTimeout(resolve, delay));
  }
}

// Free hosting puts idle services to sleep. On Render a sleeping service only wakes for traffic from the
// internet, not from our own Nginx (another Render service), so the browser also calls each backend's public
// health check directly (addresses from /wake-urls; none in Docker). Fire-and-forget.
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function ping(url, options) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const res = await fetch(url, { cache: "no-store", ...options }).catch(() => null);
    if (res && (res.ok || res.type === "opaque")) return;
    await pause(8000);
  }
}
let directUrls = null;
async function wakeDirect() {
  directUrls ??= fetch("/wake-urls", { cache: "no-store" })
    .then((res) => (res.ok ? res.text() : ""))
    .then((text) => (text.trim().startsWith("<") ? [] : text.split(/\s+/).filter((u) => u.startsWith("https://"))))
    .catch(() => []);
  for (const url of await directUrls) ping(url, { mode: "no-cors" });
}
let woken = false;
/** Pings every backend once when the page opens, so sleeping services are up by the time someone signs in. */
export function wakeServers() {
  if (woken) return;
  woken = true;
  wakeDirect();
  for (const url of ["/api/health", "/wake/gateway", "/wake/flow", "/wake/notify"]) ping(url);
}

let refreshing = null;
function refreshTokens() {
  if (!store.refresh) return Promise.resolve(false);
  refreshing ??= fetchAwake("/api/auth/token/refresh", {
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
    res = await fetchAwake(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError("Can't reach the health centre server. Check your connection and try again.", 0);
  }
  if (res.status === 401 && auth && !retried && (await refreshTokens())) {
    return request(path, { method, body, auth, retried: true });
  }
  if (isHostErrorPage(res)) throw new ApiError("The health centre server is still starting up. Please try again in a minute.", res.status);
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // Field errors look like {"time": ["The clinic takes appointments Mon-Fri..."]}: show the messages.
    const fieldMessages = data && typeof data === "object" && !data.detail ? Object.values(data).flat().join(" ") : "";
    throw new ApiError(data?.detail || fieldMessages || `Something went wrong (${res.status}).`, res.status);
  }
  return data;
}

export const isSignedIn = () => Boolean(store.access);

// portal "student": the server refuses staff accounts here (they use the staff portal).
export async function signIn(uniqueId, password) {
  const data = await request("/api/auth/login", { method: "POST", body: { unique_id: uniqueId, password, portal: "student" }, auth: false });
  store.set(data);
  return data;
}

/** Creates a student account, then signs in with it. */
export async function register({ uniqueId, name, email, password }) {
  await request("/api/auth/register/student", { method: "POST", body: { unique_id: uniqueId, name, email, password }, auth: false });
  return signIn(uniqueId, password);
}

export async function signOut() {
  const refresh = store.refresh;
  store.clear();
  if (refresh) await request("/api/auth/logout", { method: "POST", body: { refresh }, auth: false }).catch(() => {});
}

export const getMe = () => request("/api/me");
export const getMyHealth = () => request("/api/me/health");
export const getMyAppointments = () => request("/api/appointments/mine");
// Queue position and a rough wait estimate, from the Go patient-flow service.
export const getMyQueue = () => request("/api/queue/me");
export const getMyMedications = () => request("/api/me/medications");
export const getDepartments = () => request("/api/departments");
export const requestAppointment = (body) => request("/api/appointments", { method: "POST", body });
export const cancelAppointment = (id) => request(`/api/appointments/${id}/cancel`, { method: "POST" });

// Notifications come from the Flask notification service.
export const getNotifications = () => request("/api/notifications?limit=50");
export const markNotificationRead = (id) => request(`/api/notifications/${id}/read`, { method: "POST" });
export const markAllNotificationsRead = () => request("/api/notifications/read-all", { method: "POST" });
export const getNotificationPreferences = () => request("/api/notifications/preferences");
export const setNotificationPreferences = (body) => request("/api/notifications/preferences", { method: "PUT", body });
