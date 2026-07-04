import { useEffect, useState, type RefObject } from "react";

import { wsBase } from "../lib/api";
import type { GuardStatus } from "../lib/types";

const SEND_INTERVAL_MS = 66; // ~15 fps cap
const JPEG_QUALITY = 0.7;
const CAP_W = 960;
const CAP_H = 540;
const INFLIGHT_TIMEOUT_MS = 2000;

/**
 * Owns the webcam in the app window (getUserMedia), streams JPEG frames to the
 * engine over /ws/process, and draws the returned safe frames onto `canvasRef`.
 * The browser handling getUserMedia means the OS grants the camera to the app
 * itself — no separate-process permission problem.
 */
export function useGuardProcessor(
  port: number | null,
  canvasRef: RefObject<HTMLCanvasElement | null>,
  deviceId: string | null,
) {
  const [status, setStatus] = useState<GuardStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    if (port == null) return;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let stream: MediaStream | null = null;
    let video: HTMLVideoElement | null = null;
    let timer: number | undefined;
    let retry: number | undefined;
    let inFlight = false;
    let inFlightSince = 0;

    const off = document.createElement("canvas");
    off.width = CAP_W;
    off.height = CAP_H;
    const offctx = off.getContext("2d");

    const sendLoop = () => {
      if (!ws || ws.readyState !== WebSocket.OPEN || !video || !offctx) return;
      if (inFlight && Date.now() - inFlightSince < INFLIGHT_TIMEOUT_MS) return;
      if (video.readyState < 2) return;
      // Claim the in-flight slot *before* the async encode so a later tick
      // can't slip past the gate while toBlob is still pending.
      inFlight = true;
      inFlightSince = Date.now();
      offctx.drawImage(video, 0, 0, off.width, off.height);
      off.toBlob(
        (blob) => {
          if (!blob || !ws || ws.readyState !== WebSocket.OPEN) {
            inFlight = false;
            return;
          }
          blob.arrayBuffer().then((buf) => {
            if (ws && ws.readyState === WebSocket.OPEN) ws.send(buf);
            else inFlight = false;
          });
        },
        "image/jpeg",
        JPEG_QUALITY,
      );
    };

    const connectWs = () => {
      // Keep a local handle: handlers must act on *this* socket, not whatever
      // `ws` points to by the time they fire (a late error/close event from an
      // abandoned socket must never tear down or double-reconnect a fresh one).
      const sock = new WebSocket(`${wsBase(port)}/ws/process`);
      ws = sock;
      sock.binaryType = "arraybuffer";
      sock.onopen = () => {
        if (cancelled || ws !== sock) return;
        setConnected(true);
        inFlight = false;
        if (timer) window.clearInterval(timer);
        timer = window.setInterval(sendLoop, SEND_INTERVAL_MS);
      };
      sock.onclose = () => {
        if (ws !== sock) return;
        setConnected(false);
        if (!cancelled) retry = window.setTimeout(connectWs, 1000);
      };
      sock.onerror = () => sock.close();
      sock.onmessage = async (ev) => {
        if (ws !== sock) return;
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
      // the app in System Settings -> Privacy -> Camera and shows the prompt, so
      // the subsequent getUserMedia call has permission. No-op elsewhere.
      try {
        if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
          const mod = await import("tauri-plugin-macos-permissions-api");
          if (mod?.requestCameraPermission) await mod.requestCameraPermission();
        }
      } catch {
        /* not macOS or plugin unavailable */
      }

      const secure = typeof window !== "undefined" ? window.isSecureContext : false;
      // In a non-secure context macOS WKWebView doesn't even expose mediaDevices.
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraError(
          `Camera API unavailable in this webview (secureContext=${secure}). ` +
            "The page is likely not a secure context.",
        );
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: deviceId
            ? { deviceId: { exact: deviceId }, width: 1280, height: 720 }
            : { width: 1280, height: 720 },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        video = document.createElement("video");
        video.muted = true;
        video.playsInline = true;
        video.autoplay = true;
        video.srcObject = stream;
        await video.play().catch(() => {});
        setCameraError(null);
        setStarted(true);
        connectWs();
      } catch (e) {
        if (cancelled) return;
        const name = (e as DOMException)?.name || "UnknownError";
        const base =
          name === "NotAllowedError" || name === "SecurityError"
            ? "Camera was blocked by the webview"
            : name === "NotFoundError" || name === "OverconstrainedError"
              ? "No usable camera found — try another from the dropdown"
              : "Camera error";
        setCameraError(`${base}. [${name}; secureContext=${secure}]`);
      }
    };

    startCamera();
    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
      if (retry) window.clearTimeout(retry);
      ws?.close();
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [port, canvasRef, deviceId]);

  return { status, connected, cameraError, started };
}
