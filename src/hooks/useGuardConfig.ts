import { useCallback, useEffect, useRef, useState } from "react";

import { fetchConfig, postConfig } from "../lib/api";
import type { GuardConfig } from "../lib/types";

/** Loads guard config from the sidecar and pushes updates back (with an
 *  optimistic local update so the UI feels instant). */
export function useGuardConfig(port: number | null) {
  const [config, setConfig] = useState<GuardConfig | null>(null);
  const timers = useRef<Record<string, number>>({});

  useEffect(() => {
    if (port == null) return;
    let cancelled = false;
    fetchConfig(port)
      .then((c) => !cancelled && setConfig(c))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [port]);

  const update = useCallback(
    (partial: Partial<GuardConfig>) => {
      setConfig((prev) => (prev ? { ...prev, ...partial } : prev));
      if (port == null) return;
      postConfig(port, partial)
        .then((c) => setConfig(c))
        .catch(() => {});
    },
    [port],
  );

  // Debounced push for high-frequency controls (the sensitivity slider).
  const updateDebounced = useCallback(
    (partial: Partial<GuardConfig>, key = "default", delay = 120) => {
      setConfig((prev) => (prev ? { ...prev, ...partial } : prev));
      if (port == null) return;
      window.clearTimeout(timers.current[key]);
      timers.current[key] = window.setTimeout(() => {
        postConfig(port, partial)
          .then((c) => setConfig(c))
          .catch(() => {});
      }, delay);
    },
    [port],
  );

  return { config, update, updateDebounced };
}
