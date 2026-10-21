// Free hosting puts idle services to sleep, and the first request after that waits about a minute.
// Opening the page pings every backend (Nginx routes in nginx.conf), so they are awake by the time
// someone signs in. Fire-and-forget: failures are ignored, and it runs once per page load.
const TARGETS = ["/api/health", "/wake/gateway", "/wake/flow", "/wake/notify"];
let started = false;

export function wakeServers() {
  if (started) return;
  started = true;
  for (const url of TARGETS) {
    (async () => {
      for (let attempt = 0; attempt < 8; attempt += 1) {
        try {
          if ((await fetch(url, { cache: "no-store" })).ok) return;
        } catch {
          // offline or still starting: try again shortly
        }
        await new Promise((resolve) => setTimeout(resolve, 8000));
      }
    })();
  }
}
