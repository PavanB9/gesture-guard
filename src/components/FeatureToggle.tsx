interface FeatureToggleProps {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  accent?: "cyan" | "emerald" | "amber";
}

const ACCENT: Record<string, string> = {
  cyan: "bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.7)]",
  emerald: "bg-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.7)]",
  amber: "bg-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.7)]",
};

export default function FeatureToggle({
  label,
  description,
  checked,
  onChange,
  disabled = false,
  accent = "cyan",
}: FeatureToggleProps) {
  return (
    <div
      className={`flex items-center justify-between gap-3 ${disabled ? "opacity-40" : ""}`}
    >
      <div className="min-w-0">
        <div className="text-sm font-medium text-zinc-100">{label}</div>
        {description && <div className="text-xs text-zinc-500">{description}</div>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
          checked ? ACCENT[accent] : "bg-zinc-700"
        } ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
            checked ? "translate-x-[22px]" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}
