import { useEffect, useState, type RefObject } from "react";

import { wsBase } from "../lib/api";
import type { GuardStatus } from "../lib/types";

const SEND_INTERVAL_MS = 66; // ~15 fps cap
const INFLIGHT_TIMEOUT_MS = 2000;

/**
 * Periodically polls the engine for safe frames over /ws/process, and draws
 * the returned safe frames onto `canvasRef`. The camera is managed by the
 * Python engine natively.
 */
export function useGuardProcessor(
  port: number | null,
  canvasRef: RefObject<HTMLCanvasElement | null>,
) {
  const [status, setStatus] = useState<GuardStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);

  useEffect(() => {
    if (port == null) return;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let retry: number | undefined;
    let inFlight = false;
    let inFlightSince = 0;

    const sendLoop = () => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      if (inFlight && Date.now() - inFlightSince < INFLIGHT_TIMEOUT_MS) return;
      
      inFlight = true;
      inFlightSince = Date.now();
      ws.send(new Uint8Array(0)); // trigger next frame from backend
    };

    const connectWs = () => {
      ws = new WebSocket(`${wsBase(port)}/ws/process`);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => {
        setConnected(true);
        inFlight = false;
        if (timer) window.clearInterval(timer);
        timer = window.setInterval(sendLoop, SEND_INTERVAL_MS);
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) retry = window.setTimeout(connectWs, 1000);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = async (ev) => {
        if (typeof ev.data === "string") {
          try {
            setStatus(JSON.parse(ev.data) as GuardStatus);
          } catch {
            /* ignore */
          }
          return;
        }
        inFlight = false;
        const canvas = canvasRef.current;
        if (!canvas) return;
        try {
          const bmp = await createImageBitmap(new Blob([ev.data]));
          if (canvas.width !== bmp.width || canvas.height !== bmp.height) {
            canvas.width = bmp.width;
            canvas.height = bmp.height;
          }
          canvas.getContext("2d")?.drawImage(bmp, 0, 0);
          bmp.close();
        } catch {
          /* dropped frame */
        }
      };
    };

    const startCamera = async () => {
      // macOS: ask the OS for camera permission natively first. This registers
      // the app in System Settings -> Privacy -> Camera and shows the prompt.
      // After this, the backend process will inherit the permission.
      try {
        if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
          const mod = await import("tauri-plugin-macos-permissions-api");
          if (mod?.requestCameraPermission) await mod.requestCameraPermission();
        }
      } catch {
        /* not macOS or plugin unavailable */
      }

      setCameraError(null);
      connectWs();
    };

    startCamera();
    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
      if (retry) window.clearTimeout(retry);
      ws?.close();
    };
  }, [port, canvasRef]);

  return { status, connected, cameraError };
}
