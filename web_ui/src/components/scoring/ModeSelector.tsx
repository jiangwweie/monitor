import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Badge } from "@/components/ui/badge";

interface ModeSelectorProps {
  mode: "classic" | "progressive" | "custom";
  onModeChange: (mode: "classic" | "progressive" | "custom") => void;
}

export function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
  const modes = [
    {
      value: "classic",
      label: "经典模式",
      description: "线性评分，0.6→0 分，0.9→100 分",
    },
    {
      value: "progressive",
      label: "累进模式",
      description: "基础分 + 奖励分，精品信号更突出",
      badge: "推荐",
    },
    {
      value: "custom",
      label: "自定义模式",
      description: "自定义公式系数（开发中）",
      disabled: true,
    },
  ];

  return (
    <div className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Label className="text-sm font-semibold">打分模式</Label>
        <InfoTooltip content="选择不同的打分算法模式" />
      </div>

      <RadioGroup
        value={mode}
        onValueChange={(v) => onModeChange(v as typeof mode)}
        className="flex flex-wrap gap-4"
      >
        {modes.map((m) => (
          <div
            key={m.value}
            className={`flex items-center space-x-2 p-4 border rounded-lg cursor-pointer transition-all
              ${m.disabled ? "opacity-50 cursor-not-allowed" : "hover:bg-zinc-50 dark:hover:bg-zinc-900"}
              ${mode === m.value ? "border-blue-500 bg-blue-50 dark:bg-blue-950/20" : "border-zinc-200 dark:border-zinc-800"}
            `}
            onClick={() => !m.disabled && onModeChange(m.value as typeof mode)}
          >
            <RadioGroupItem
              value={m.value}
              id={m.value}
              disabled={m.disabled}
            />
            <Label
              htmlFor={m.value}
              className="flex flex-col cursor-pointer"
            >
              <span className="flex items-center gap-2 font-medium">
                {m.label}
                {m.badge && (
                  <Badge variant="default" className="text-xs px-2 py-0.5 bg-blue-500 text-white rounded-full">
                    {m.badge}
                  </Badge>
                )}
              </span>
              <span className="text-xs text-zinc-500 mt-1">
                {m.description}
              </span>
            </Label>
          </div>
        ))}
      </RadioGroup>
    </div>
  );
}
