import { type RefObject } from "react";

import type { GuardStatus } from "../lib/types";
import StatusHUD from "./StatusHUD";

interface VideoPreviewProps {
  canvasRef: RefObject<HTMLCanvasElement | null>;
  status: GuardStatus | null;
  connected: boolean;
  cameraError: string | null;
}

export default function VideoPreview({
  canvasRef,
  status,
  connected,
  cameraError,
}: VideoPreviewProps) {
  const active = !!status?.guard_active;

  return (
    <div
      className={`relative aspect-video w-full overflow-hidden rounded-2xl border bg-black shadow-2xl transition-colors ${
        active ? "border-red-500/70" : "border-zinc-800"
      }`}
    >
      <canvas ref={canvasRef} className="h-full w-full object-contain" />

      {cameraError ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-zinc-950/85 px-8 text-center">
          <div className="text-3xl">📷</div>
          <div className="max-w-md text-sm font-medium text-red-300">{cameraError}</div>
          <div className="max-w-md text-xs text-zinc-500">
            On macOS: System Settings → Privacy &amp; Security → Camera → enable
            Gesture Guard, then reopen the app.
          </div>
        </div>
      ) : !connected ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-zinc-950/80">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-cyan-400" />
          <div className="text-sm text-zinc-400">Connecting to privacy engine…</div>
        </div>
      ) : null}

      <StatusHUD status={status} connected={connected} />
    </div>
  );
}
