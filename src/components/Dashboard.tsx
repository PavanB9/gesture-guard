import { type RefObject } from "react";

import type { GuardConfig, GuardStatus } from "../lib/types";
import ControlPanel from "./ControlPanel";
import VideoPreview from "./VideoPreview";

interface DashboardProps {
  connected: boolean;
  portError: string | null;
  status: GuardStatus | null;
  config: GuardConfig | null;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  update: (partial: Partial<GuardConfig>) => void;
  updateDebounced: (
    partial: Partial<GuardConfig>,
    key?: string,
    delay?: number,
  ) => void;
}

export default function Dashboard({
  connected,
  portError,
  status,
  config,
  canvasRef,
  update,
  updateDebounced,
}: DashboardProps) {
  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-5">
      {/* Header */}
      <header className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-emerald-500 text-black shadow-[0_0_18px_rgba(34,211,238,0.5)]">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3l7 3v5c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6l7-3z" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-semibold leading-tight text-zinc-50">
              Gesture Guard
            </h1>
            <p className="text-xs text-zinc-500">Local real-time privacy guard</p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-1.5">
          <span
            className={`h-2 w-2 rounded-full ${
              connected ? "bg-emerald-400" : "bg-amber-400 animate-pulsedot"
            }`}
          />
          <span className="text-xs text-zinc-400">
            {connected ? "Engine connected" : "Connecting…"}
          </span>
        </div>
      </header>

      {portError && (
        <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-950/40 px-4 py-2 text-sm text-amber-300">
          Could not reach the sidecar port ({portError}). In a browser dev session,
          start the engine manually on port 8000.
        </div>
      )}

      {/* Main */}
      <div className="grid flex-1 grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
        <div className="flex flex-col gap-4">
          <VideoPreview canvasRef={canvasRef} status={status} connected={connected} />
          <p className="text-center text-xs text-zinc-600">
            The feed never leaves this machine — capture, detection and blurring all
            run in the local Python sidecar.
          </p>
        </div>
        <aside className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-5">
          <ControlPanel
            config={config}
            status={status}
            update={update}
            updateDebounced={updateDebounced}
          />
        </aside>
      </div>
    </div>
  );
}
