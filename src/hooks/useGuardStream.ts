import { useEffect, useState, type RefObject } from "react";

import { wsBase } from "../lib/api";
import type { GuardStatus } from "../lib/types";

/** Connects to the sidecar's frame stream: draws binary JPEG frames onto the
 *  given canvas and surfaces the interleaved JSON status. Auto-reconnects. */
export function useGuardStream(
  port: number | null,
  canvasRef: RefObject<HTMLCanvasElement | null>,
) {
  const [status, setStatus] = useState<GuardStatus | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (port == null) return;
    let ws: WebSocket | null = null;
    let retry: number | undefined;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(`${wsBase(port)}/ws/stream`);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = window.setTimeout(connect, 1000);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = async (ev) => {
        if (typeof ev.data === "string") {
          try {
            setStatus(JSON.parse(ev.data) as GuardStatus);
          } catch {
            /* ignore malformed status */
          }
          return;
        }
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

    connect();
    return () => {
      closed = true;
      if (retry) window.clearTimeout(retry);
      ws?.close();
    };
  }, [port, canvasRef]);

  return { status, connected };
}
