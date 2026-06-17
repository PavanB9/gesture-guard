import type { GuardAction, GuardConfig } from "../lib/types";
import FeatureToggle from "./FeatureToggle";
import SensitivitySlider from "./SensitivitySlider";

interface ControlPanelProps {
  config: GuardConfig | null;
  update: (partial: Partial<GuardConfig>) => void;
  updateDebounced: (
    partial: Partial<GuardConfig>,
    key?: string,
    delay?: number,
  ) => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function ControlPanel({
  config,
  update,
  updateDebounced,
}: ControlPanelProps) {
  if (!config) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-zinc-500">
        Loading settings…
      </div>
    );
  }

  const armed = config.guard_enabled;

  return (
    <div className="flex flex-col gap-6">
      {/* Master switch */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        <FeatureToggle
          label="Privacy Guard"
          description={armed ? "Armed — watching the feed" : "Disabled — feed passes through"}
          checked={armed}
          accent="emerald"
          onChange={(v) => update({ guard_enabled: v })}
        />
      </div>

      <Section title="Detectors">
        <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <FeatureToggle
            label="Yawn Guard"
            description="Blurs on a sustained wide-open mouth"
            checked={config.yawn_guard}
            disabled={!armed}
            onChange={(v) => update({ yawn_guard: v })}
          />
          <FeatureToggle
            label="Anti Face-Touch"
            description="Hands near nose / eyes (grooming, nose-picking)"
            checked={config.face_touch_guard}
            disabled={!armed}
            onChange={(v) => update({ face_touch_guard: v })}
          />
          <FeatureToggle
            label="Background Intrusion"
            description="A second person appears behind you"
            checked={config.intrusion_guard}
            disabled={!armed}
            accent="amber"
            onChange={(v) => update({ intrusion_guard: v })}
          />
        </div>
      </Section>

      <Section title="Guard Action">
        <div className="grid grid-cols-2 gap-2">
          {(["blur", "brb"] as GuardAction[]).map((action) => {
            const selected = config.guard_action === action;
            return (
              <button
                key={action}
                type="button"
                onClick={() => update({ guard_action: action })}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  selected
                    ? "border-cyan-400/70 bg-cyan-400/10 text-cyan-200"
                    : "border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700"
                }`}
              >
                {action === "blur" ? "Blur feed" : "Be Right Back"}
              </button>
            );
          })}
        </div>
      </Section>

      <Section title="Tuning">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <SensitivitySlider
            value={config.sensitivity}
            disabled={!armed}
            onChange={(v) => updateDebounced({ sensitivity: v }, "sensitivity")}
          />
        </div>
      </Section>

      <Section title="Camera">
        <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-zinc-100">Device</span>
            <select
              value={config.camera_index}
              onChange={(e) => update({ camera_index: Number(e.target.value) })}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-200 outline-none focus:border-cyan-500"
            >
              {[0, 1, 2, 3].map((i) => (
                <option key={i} value={i}>
                  Camera {i}
                </option>
              ))}
            </select>
          </div>
          <FeatureToggle
            label="Mirror preview"
            checked={config.mirror}
            onChange={(v) => update({ mirror: v })}
          />
          <FeatureToggle
            label="Show landmarks (debug)"
            checked={config.show_overlay}
            onChange={(v) => update({ show_overlay: v })}
          />
        </div>
      </Section>
    </div>
  );
}
