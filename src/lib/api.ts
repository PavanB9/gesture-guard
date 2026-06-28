import type { GuardConfig } from "./types";

export const httpBase = (port: number) => `http://127.0.0.1:${port}`;
export const wsBase = (port: number) => `ws://127.0.0.1:${port}`;

export async function fetchConfig(port: number): Promise<GuardConfig> {
  const res = await fetch(`${httpBase(port)}/api/config`);
  if (!res.ok) throw new Error(`config ${res.status}`);
  return res.json();
}

export async function postConfig(
  port: number,
  partial: Partial<GuardConfig>,
): Promise<GuardConfig> {
  const res = await fetch(`${httpBase(port)}/api/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(partial),
  });
  if (!res.ok) throw new Error(`config ${res.status}`);
  return res.json();
}

export async function fetchCameras(
  port: number,
): Promise<{ cameras: number[]; active: number }> {
  const res = await fetch(`${httpBase(port)}/api/cameras`);
  if (!res.ok) throw new Error(`cameras ${res.status}`);
  return res.json();
}

export async function ping(port: number): Promise<boolean> {
  try {
    const res = await fetch(`${httpBase(port)}/healthz`);
    return res.ok;
  } catch {
    return false;
  }
}

/** Open a URL in the user's default browser (Tauri opener; window.open fallback). */
export async function openExternal(url: string): Promise<void> {
  try {
    if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
      const { openUrl } = await import("@tauri-apps/plugin-opener");
      await openUrl(url);
      return;
    }
  } catch {
    /* fall through to window.open */
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
