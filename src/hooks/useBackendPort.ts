import { useEffect, useState } from "react";

// When running as a plain Vite dev server (no Tauri), connect to a sidecar
// started manually on this port (see README "Frontend dev" instructions).
const DEV_FALLBACK_PORT = 8000;

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/** Resolve the localhost port the Python sidecar is listening on. */
export function useBackendPort() {
  const [port, setPort] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (isTauri()) {
        try {
          const { invoke } = await import("@tauri-apps/api/core");
          const p = await invoke<number>("get_backend_port");
          if (!cancelled) setPort(p);
          return;
        } catch (e) {
          if (!cancelled) setError(String(e));
        }
      }
      if (!cancelled) setPort(DEV_FALLBACK_PORT);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { port, error };
}
