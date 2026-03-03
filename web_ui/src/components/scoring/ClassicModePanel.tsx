import { ParameterSlider } from "./ParameterSlider";
import { Button } from "@/components/ui/button";
import { RotateCcw } from "lucide-react";

const DEFAULTS = {
  classic_shadow_min: 0.6,
  classic_shadow_max: 0.9,
  classic_body_good: 0.1,
  classic_body_bad: 0.5,
  classic_vol_min: 1.2,
  classic_vol_max: 3.0,
  classic_trend_max_dist: 0.03,
};

interface ClassicModePanelProps {
  config: {
    classic_shadow_min: number;
    classic_shadow_max: number;
    classic_body_good: number;
    classic_body_bad: number;
    classic_vol_min: number;
    classic_vol_max: number;
    classic_trend_max_dist: number;
  };
  onChange: (updates: Record<string, number>) => void;
}

export function ClassicModePanel({ config, onChange }: ClassicModePanelProps) {
  const handleReset = () => {
    onChange(DEFAULTS);
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold">经典模式参数配置</h3>
          <p className="text-xs text-zinc-500 mt-1">
            线性评分模式：影线 0.6→0 分，0.9→100 分
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleReset}
          className="text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          <RotateCcw className="w-3.5 h-3.5 mr-2" />
          重置为默认
        </Button>
      </div>

      <div className="space-y-1">
        <ParameterSlider
          label="影线比例最小值 (0 分)"
          description="低于此值形态分为 0"
          value={config.classic_shadow_min}
          min={0.3}
          max={0.8}
          step={0.01}
          onChange={(v) => onChange({ classic_shadow_min: v })}
          defaultValue={DEFAULTS.classic_shadow_min}
          onReset={handleReset}
        />
        <ParameterSlider
          label="影线比例最大值 (100 分)"
          description="高于此值形态分为 100"
          value={config.classic_shadow_max}
          min={0.7}
          max={1.0}
          step={0.01}
          onChange={(v) => onChange({ classic_shadow_max: v })}
          defaultValue={DEFAULTS.classic_shadow_max}
          onReset={handleReset}
        />
        <ParameterSlider
          label="实体比例优秀阈值"
          description="低于此值实体分满分"
          value={config.classic_body_good}
          min={0.01}
          max={0.3}
          step={0.01}
          onChange={(v) => onChange({ classic_body_good: v })}
          defaultValue={DEFAULTS.classic_body_good}
          onReset={handleReset}
        />
        <ParameterSlider
          label="实体比例差阈值"
          description="高于此值实体分 0 分"
          value={config.classic_body_bad}
          min={0.3}
          max={0.7}
          step={0.01}
          onChange={(v) => onChange({ classic_body_bad: v })}
          defaultValue={DEFAULTS.classic_body_bad}
          onReset={handleReset}
        />
        <ParameterSlider
          label="波动率最小值 (0 分)"
          description="低于此值波动分为 0"
          value={config.classic_vol_min}
          min={0.8}
          max={2.0}
          step={0.1}
          suffix="x ATR"
          onChange={(v) => onChange({ classic_vol_min: v })}
          defaultValue={DEFAULTS.classic_vol_min}
          onReset={handleReset}
        />
        <ParameterSlider
          label="波动率最大值 (100 分)"
          description="高于此值波动分为 100"
          value={config.classic_vol_max}
          min={2.0}
          max={5.0}
          step={0.1}
          suffix="x ATR"
          onChange={(v) => onChange({ classic_vol_max: v })}
          defaultValue={DEFAULTS.classic_vol_max}
          onReset={handleReset}
        />
        <ParameterSlider
          label="趋势距离最大值"
          description="超过此值趋势分为 0"
          value={config.classic_trend_max_dist}
          min={0.01}
          max={0.1}
          step={0.005}
          onChange={(v) => onChange({ classic_trend_max_dist: v })}
          defaultValue={DEFAULTS.classic_trend_max_dist}
          onReset={handleReset}
        />
      </div>
    </div>
  );
}
