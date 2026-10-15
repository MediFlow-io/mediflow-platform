import { useEffect, useRef, useState } from "react";
import { streamEvents } from "../api/client";

/**
 * Subscribe to live visit changes from the Go patient-flow service (/api/queue/events).
 * Calls onChange (debounced) whenever a visit is checked in, moved or edited.
 * Reconnects with backoff; returns `live` so the UI can fall back to slower polling while offline.
 */
export function useQueueEvents(onChange, { debounceMs = 300 } = {}) {
  const [live, setLive] = useState(false);
  const latest = useRef(onChange);
  latest.current = onChange;

  useEffect(() => {
    const controller = new AbortController();
    let timer = null;
    let retry = null;
    let backoff = 1000;
    const changed = () => {
      clearTimeout(timer);
      timer = setTimeout(() => latest.current?.(), debounceMs);
    };

    const connect = () => {
      streamEvents("/api/queue/events", {
        signal: controller.signal,
        onOpen: () => {
          setLive(true);
          backoff = 1000;
          changed(); // catch up on anything missed while disconnected
        },
        onEvent: (name) => {
          if (name === "visit") changed();
        },
      })
        .catch(() => {})
        .finally(() => {
          if (controller.signal.aborted) return;
          setLive(false);
          retry = setTimeout(connect, backoff);
          backoff = Math.min(backoff * 2, 30000);
        });
    };
    connect();

    return () => {
      controller.abort();
      clearTimeout(timer);
      clearTimeout(retry);
    };
  }, [debounceMs]);

  return live;
}
