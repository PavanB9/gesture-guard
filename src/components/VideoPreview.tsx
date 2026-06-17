import { type RefObject } from "react";

import type { GuardStatus } from "../lib/types";
import StatusHUD from "./StatusHUD";

interface VideoPreviewProps {
  canvasRef: RefObject<HTMLCanvasElement | null>;
  status: GuardStatus | null;
  connected: boolean;
}

export default function VideoPreview({
  canvasRef,
  status,
  connected,
}: VideoPreviewProps) {
  const active = !!status?.guard_active;

  return (
    <div
      className={`relative aspect-video w-full overflow-hidden rounded-2xl border bg-black shadow-2xl transition-colors ${
        active ? "border-red-500/70" : "border-zinc-800"
      }`}
    >
      <canvas
        ref={canvasRef}
        className="h-full w-full object-contain"
      />

      {!connected && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-zinc-950/80">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-cyan-400" />
          <div className="text-sm text-zinc-400">
            Connecting to privacy engine…
          </div>
        </div>
      )}

      <StatusHUD status={status} connected={connected} />
    </div>
  );
}
