import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";

interface WeightSliderProps {
  label: string;
  description?: string;
  value: number;
  onChange: (value: number) => void;
  color?: "blue" | "green" | "orange";
}

export function WeightSlider({
  label,
  description,
  value,
  onChange,
  color = "blue",
}: WeightSliderProps) {
  const colorClasses = {
    blue: "accent-blue-500",
    green: "accent-green-500",
    orange: "accent-orange-500",
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm font-medium">{label}</Label>
          {description && (
            <p className="text-xs text-zinc-500">{description}</p>
          )}
        </div>
        <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
          {(value * 100).toFixed(0)}%
        </span>
      </div>
      <Slider
        value={[value]}
        min={0}
        max={1}
        step={0.01}
        onValueChange={([v]) => onChange(v)}
        className={`w-full ${colorClasses[color]}`}
      />
    </div>
  );
}
