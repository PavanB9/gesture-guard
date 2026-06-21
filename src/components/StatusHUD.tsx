import type { GuardStatus } from "../lib/types";

interface StatusHUDProps {
  status: GuardStatus | null;
  connected: boolean;
}

export default function StatusHUD({ status, connected }: StatusHUDProps) {
  const active = !!status?.guard_active;
  const actionLabel =
    status?.action === "brb" ? "BE RIGHT BACK" : "BLURRING";

  return (
    <>
      {/* Top-left live indicator */}
      <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-full bg-black/55 px-3 py-1.5 backdrop-blur">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            !connected
              ? "bg-zinc-500"
              : active
                ? "animate-pulsedot bg-red-500"
                : "bg-emerald-400"
          }`}
        />
        <span className="text-xs font-medium tracking-wide text-zinc-200">
          {!connected ? "OFFLINE" : active ? "GUARDED" : "MONITORING"}
        </span>
        {connected && status && (
          <span className="font-mono text-[11px] text-zinc-400">
            {status.fps.toFixed(0)} fps
          </span>
        )}
        {status?.virtual_cam_active && (
          <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-emerald-300">
            VCAM
          </span>
        )}
      </div>

      {/* Flashing violation banner */}
      {active && (
        <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2">
          <div className="animate-guardflash rounded-lg border border-red-500/70 bg-red-950/80 px-5 py-2 text-center shadow-[0_0_22px_rgba(239,68,68,0.5)] backdrop-blur">
            <div className="text-sm font-bold tracking-[0.18em] text-red-300">
              PRIVACY GUARD ACTIVE: {actionLabel}
            </div>
            {status?.violation_labels?.length ? (
              <div className="mt-0.5 text-[11px] uppercase tracking-wide text-red-200/80">
                {status.violation_labels.join("  •  ")}
              </div>
            ) : null}
          </div>
        </div>
      )}

    </>
  );
}
