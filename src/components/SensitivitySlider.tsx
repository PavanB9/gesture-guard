interface SensitivitySliderProps {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}

export default function SensitivitySlider({
  value,
  onChange,
  disabled = false,
}: SensitivitySliderProps) {
  return (
    <div className={disabled ? "opacity-40" : ""}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-zinc-100">Sensitivity</span>
        <span className="font-mono text-xs text-cyan-300">
          {Math.round(value * 100)}%
        </span>
      </div>
      <input
        type="range"
        className="gg-slider"
        min={0}
        max={1}
        step={0.01}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <div className="mt-1 flex justify-between text-[10px] uppercase tracking-wide text-zinc-600">
        <span>Relaxed</span>
        <span>Strict</span>
      </div>
    </div>
  );
}
