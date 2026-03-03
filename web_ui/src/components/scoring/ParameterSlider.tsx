import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { RotateCcw } from "lucide-react";

interface ParameterSliderProps {
  label: string;
  description?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  onChange: (value: number) => void;
  onReset?: () => void;
  defaultValue?: number;
}

export function ParameterSlider({
  label,
  description,
  value,
  min,
  max,
  step,
  suffix = "",
  onChange,
  onReset,
  defaultValue,
}: ParameterSliderProps) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-4 items-center py-3 border-b border-zinc-100 dark:border-zinc-800 last:border-0">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Label className="text-sm font-medium">{label}</Label>
          {description && <InfoTooltip content={description} />}
        </div>
        <Slider
          value={[value]}
          min={min}
          max={max}
          step={step}
          onValueChange={([v]) => onChange(v)}
          className="w-[280px]"
        />
      </div>
      <div className="flex items-center gap-2">
        <Input
          type="number"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className="w-[100px] text-right h-8"
          step={step}
          min={min}
          max={max}
        />
        {suffix && <span className="text-sm text-zinc-500 w-12">{suffix}</span>}
        {onReset && defaultValue !== undefined && (
          <button
            onClick={onReset}
            className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
            title="重置为默认值"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
