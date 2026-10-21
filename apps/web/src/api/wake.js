// Free hosting puts idle services to sleep, and the first request after that waits about a minute.
// On Render a sleeping service only wakes for traffic from the internet: calls from our own Nginx (another
// Render service) just get a 502. So the browser calls each backend's public health check itself
// (addresses from /wake-urls, set per deployment; none in Docker) as well as through Nginx.
// Fire-and-forget: failures are ignored.
const PROXIED = ["/api/health", "/wake/gateway", "/wake/flow", "/wake/notify"];
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function ping(url, options) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      const res = await fetch(url, { cache: "no-store", ...options });
      if (res.ok || res.type === "opaque") return; // opaque: a direct call answered (its body is unreadable)
    } catch {
      // offline, or the service is still starting
    }
    await pause(8000);
  }
}

let directUrls = null;
async function direct() {
  directUrls ??= fetch("/wake-urls", { cache: "no-store" })
    .then((res) => (res.ok ? res.text() : ""))
    .then((text) => (text.trim().startsWith("<") ? [] : text.split(/\s+/).filter((u) => u.startsWith("https://"))))
    .catch(() => []);
  // no-cors: the browser sends a plain GET and doesn't need the service to allow this origin.
  for (const url of await directUrls) ping(url, { mode: "no-cors" });
}

let started = false;
/** Wakes every backend; runs once per page load unless `again` is set (e.g. a request found one asleep). */
export function wakeServers({ again = false } = {}) {
  if (started && !again) return;
  started = true;
  direct();
  if (!again) for (const url of PROXIED) ping(url);
}
