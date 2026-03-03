import { ParameterSlider } from "./ParameterSlider";
import { Button } from "@/components/ui/button";
import { RotateCcw } from "lucide-react";

const DEFAULTS = {
  progressive_base_cap: 30.0,
  progressive_shadow_threshold: 0.6,
  progressive_shadow_bonus_rate: 20.0,
  progressive_body_bonus_threshold: 0.1,
  progressive_body_bonus_rate: 100.0,
  progressive_doji_bonus: 5.0,
  progressive_vol_threshold: 2.0,
  progressive_vol_bonus_rate: 15.0,
  progressive_extreme_vol_threshold: 3.0,
  progressive_extreme_vol_bonus: 10.0,
  progressive_penetration_rate: 30.0,
};

interface ProgressiveModePanelProps {
  config: {
    progressive_base_cap: number;
    progressive_shadow_threshold: number;
    progressive_shadow_bonus_rate: number;
    progressive_body_bonus_threshold: number;
    progressive_body_bonus_rate: number;
    progressive_doji_bonus: number;
    progressive_vol_threshold: number;
    progressive_vol_bonus_rate: number;
    progressive_extreme_vol_threshold: number;
    progressive_extreme_vol_bonus: number;
    progressive_penetration_rate: number;
  };
  onChange: (updates: Record<string, number>) => void;
}

export function ProgressiveModePanel({ config, onChange }: ProgressiveModePanelProps) {
  const handleReset = () => {
    onChange(DEFAULTS);
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold">累进模式参数配置</h3>
          <p className="text-xs text-zinc-500 mt-1">
            基础分 + 奖励分模式，精品信号更突出
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

      {/* 基础分配置 */}
      <div className="space-y-1 border-b border-zinc-200 dark:border-zinc-800 pb-4 mb-4">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
          基础分配置
        </h4>
        <ParameterSlider
          label="基础分上限"
          description="每个维度的基础分上限"
          value={config.progressive_base_cap}
          min={20}
          max={50}
          step={1}
          suffix="分"
          onChange={(v) => onChange({ progressive_base_cap: v })}
          defaultValue={DEFAULTS.progressive_base_cap}
          onReset={handleReset}
        />
      </div>

      {/* 形态奖励配置 */}
      <div className="space-y-1 border-b border-zinc-200 dark:border-zinc-800 pb-4 mb-4">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
          形态奖励配置
        </h4>
        <ParameterSlider
          label="影线奖励阈值"
          description="超过此值开始奖励"
          value={config.progressive_shadow_threshold}
          min={0.4}
          max={0.8}
          step={0.01}
          onChange={(v) => onChange({ progressive_shadow_threshold: v })}
          defaultValue={DEFAULTS.progressive_shadow_threshold}
          onReset={handleReset}
        />
        <ParameterSlider
          label="影线奖励倍率"
          description="每超过 0.1 奖励的分数"
          value={config.progressive_shadow_bonus_rate}
          min={10}
          max={50}
          step={1}
          suffix="分/0.1"
          onChange={(v) => onChange({ progressive_shadow_bonus_rate: v })}
          defaultValue={DEFAULTS.progressive_shadow_bonus_rate}
          onReset={handleReset}
        />
        <ParameterSlider
          label="实体奖励阈值"
          description="低于此值开始奖励"
          value={config.progressive_body_bonus_threshold}
          min={0.05}
          max={0.2}
          step={0.01}
          onChange={(v) => onChange({ progressive_body_bonus_threshold: v })}
          defaultValue={DEFAULTS.progressive_body_bonus_threshold}
          onReset={handleReset}
        />
        <ParameterSlider
          label="实体奖励倍率"
          description="每低于 0.01 奖励的分数"
          value={config.progressive_body_bonus_rate}
          min={50}
          max={200}
          step={10}
          suffix="分/0.01"
          onChange={(v) => onChange({ progressive_body_bonus_rate: v })}
          defaultValue={DEFAULTS.progressive_body_bonus_rate}
          onReset={handleReset}
        />
        <ParameterSlider
          label="十字星固定奖励分"
          description="实体&lt;5% 时的额外奖励"
          value={config.progressive_doji_bonus}
          min={0}
          max={20}
          step={1}
          suffix="分"
          onChange={(v) => onChange({ progressive_doji_bonus: v })}
          defaultValue={DEFAULTS.progressive_doji_bonus}
          onReset={handleReset}
        />
      </div>

      {/* 波动奖励配置 */}
      <div className="space-y-1 border-b border-zinc-200 dark:border-zinc-800 pb-4 mb-4">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
          波动奖励配置
        </h4>
        <ParameterSlider
          label="波动率奖励起点"
          description="超过此值开始奖励"
          value={config.progressive_vol_threshold}
          min={1.2}
          max={3.0}
          step={0.1}
          suffix="x ATR"
          onChange={(v) => onChange({ progressive_vol_threshold: v })}
          defaultValue={DEFAULTS.progressive_vol_threshold}
          onReset={handleReset}
        />
        <ParameterSlider
          label="波动率奖励倍率"
          description="每超过 0.1x 奖励的分数"
          value={config.progressive_vol_bonus_rate}
          min={5}
          max={30}
          step={1}
          suffix="分/0.1x"
          onChange={(v) => onChange({ progressive_vol_bonus_rate: v })}
          defaultValue={DEFAULTS.progressive_vol_bonus_rate}
          onReset={handleReset}
        />
        <ParameterSlider
          label="极端波动阈值"
          description="超过此值额外奖励"
          value={config.progressive_extreme_vol_threshold}
          min={2.0}
          max={4.0}
          step={0.5}
          suffix="x ATR"
          onChange={(v) => onChange({ progressive_extreme_vol_threshold: v })}
          defaultValue={DEFAULTS.progressive_extreme_vol_threshold}
          onReset={handleReset}
        />
        <ParameterSlider
          label="极端波动奖励分"
          description="超过极端阈值的固定奖励"
          value={config.progressive_extreme_vol_bonus}
          min={5}
          max={20}
          step={1}
          suffix="分"
          onChange={(v) => onChange({ progressive_extreme_vol_bonus: v })}
          defaultValue={DEFAULTS.progressive_extreme_vol_bonus}
          onReset={handleReset}
        />
      </div>

      {/* 趋势奖励配置 */}
      <div className="space-y-1">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
          趋势奖励配置
        </h4>
        <ParameterSlider
          label="穿透奖励倍率"
          description="穿透 EMA60 时的奖励系数"
          value={config.progressive_penetration_rate}
          min={10}
          max={50}
          step={1}
          suffix="分"
          onChange={(v) => onChange({ progressive_penetration_rate: v })}
          defaultValue={DEFAULTS.progressive_penetration_rate}
          onReset={handleReset}
        />
      </div>
    </div>
  );
}
