import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Load data and track loading/error state.
 * `refreshMs` re-fetches in the background (the existing data stays visible while it loads).
 */
export function useApi(fetcher, deps = [], { refreshMs } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const latest = useRef(0);

  const load = useCallback(async () => {
    const call = ++latest.current;
    setState((s) => ({ ...s, loading: true }));
    try {
      const data = await fetcher();
      if (call === latest.current) setState({ data, error: null, loading: false });
    } catch (error) {
      if (call === latest.current) setState((s) => ({ ...s, error, loading: false }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
    if (!refreshMs) return undefined;
    const timer = setInterval(load, refreshMs);
    return () => clearInterval(timer);
  }, [load, refreshMs]);

  return { ...state, reload: load };
}
