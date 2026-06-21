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
      offctx.drawImage(video, 0, 0, off.width, off.height);
      off.toBlob(
        (blob) => {
          if (!blob || !ws || ws.readyState !== WebSocket.OPEN) return;
          inFlight = true;
          inFlightSince = Date.now();
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
