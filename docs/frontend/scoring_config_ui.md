# 打分配置中心 - 前端 UI 开发文档

**版本**: v1.0
**日期**: 2026-03-03
**状态**: 待开发

---

## 1. UI 布局设计

### 1.1 整体布局

```
┌─────────────────────────────────────────────────────────────────────────┐
│  打分配置中心                                               [保存] [重置] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 打分模式                                                           │ │
│  │  ○ 经典模式 (Classic)    ● 累进模式 (Progressive)    ○ 自定义模式  │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────┐ ┌─────────────────────────────────┐  │
│  │                             │ │                                 │  │
│  │   权重配置                   │ │   分数分布预览                  │  │
│  │                             │ │                                 │  │
│  │   形态评分 ━━━━━━●━━ 40%   │ │      ▲ 信号数量                  │  │
│  │   趋势评分 ━━━━●━━━━ 30%   │ │      │     ▓▓                    │  │
│  │   波动评分 ━━━━●━━━━ 30%   │ │      │    ▓▓▓▓   ▓▓▓             │  │
│  │                             │ │      │   ▓▓▓▓▓  ▓▓▓▓▓   ▓▓       │  │
│  │   ⚠️ 权重和必须等于 100%     │ │      │  ▓▓▓▓▓▓ ▓▓▓▓▓▓ ▓▓▓▓      │  │
│  │                             │ │      └────────────────────────   │  │
│  │                             │ │         0-20 40 60 80 100 分数   │  │
│  └─────────────────────────────┘ └─────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 经典模式参数配置                                                   │ │
│  ├───────────────────────────────────────────────────────────────────┤ │
│  │                                                                   │ │
│  │   影线比例最小值 (0 分)     ━━━━━━━━●━━━━━━━━━  0.60             │ │
│  │   影线比例最大值 (100 分)    ━━━━━━━━━━●━━━━━━  0.90             │ │
│  │   实体比例优秀阈值         ━━━━●━━━━━━━━━━━━━  0.10             │ │
│  │   实体比例差阈值           ━━━━━━━━━━━●━━━━━━  0.50             │ │
│  │   波动率最小值 (0 分)       ━━━━━━●━━━━━━━━━━  1.20x            │ │
│  │   波动率最大值 (100 分)     ━━━━━━━━━━━━●━━━━  3.00x            │ │
│  │   趋势距离最大值           ━━━━━━━━●━━━━━━━━━  0.03             │ │
│  │                                                                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 累进模式参数配置                                                   │ │
│  ├───────────────────────────────────────────────────────────────────┤ │
│  │                                                                   │ │
│  │   基础分上限              ━━━━━━━━━━●━━━━━━  30.0               │ │
│  │   影线奖励阈值            ━━━━━━━━●━━━━━━━━━  0.60             │ │
│  │   影线奖励倍率 (分/0.1)    ━━━━●━━━━━━━━━━━━━  2.0              │ │
│  │   实体奖励阈值            ━━━━●━━━━━━━━━━━━━  0.10             │ │
│  │   实体奖励倍率 (分/0.01)   ━━━━━━━━━━●━━━━━━  1.0               │ │
│  │   十字星固定奖励分        ━━━━━━●━━━━━━━━━━  5.0                │ │
│  │   波动率奖励起点          ━━━━━━━━━━━━●━━━━  2.0x              │ │
│  │   波动率奖励倍率 (分/0.1x) ━━━━━━━━●━━━━━━━━━  0.15             │ │
│  │                                                                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 响应式布局

| 屏幕宽度 | 布局 |
|----------|------|
| ≥ 1400px | 三列布局（权重 + 参数 + 预览） |
| ≥ 992px | 两列布局（权重 + 预览 在上，参数在下） |
| < 992px | 单列布局（垂直堆叠） |

---

## 2. 组件结构

### 2.1 组件树

```
ScoringConfigPanel (根组件)
├── ModeSelector (模式选择器)
├── WeightConfig (权重配置)
│   ├── WeightSlider (权重滑块) × 3
│   └── WeightWarning (权重和警告)
├── ScoreDistributionChart (分数分布图)
├── ClassicModePanel (经典模式参数)
│   ├── ParameterSlider × 7
│   └── ResetButton (重置默认)
├── ProgressiveModePanel (累进模式参数)
│   ├── ParameterSlider × 8
│   └── ResetButton (重置默认)
└── ActionButtons (操作按钮组)
    ├── SaveButton (保存)
    └── ResetButton (重置全部)
```

### 2.2 组件文件结构

```
web_ui/src/components/
├── scoring/
│   ├── index.tsx              # ScoringConfigPanel 入口
│   ├── ModeSelector.tsx       # 模式选择器
│   ├── WeightConfig.tsx       # 权重配置
│   ├── WeightSlider.tsx       # 权重滑块
│   ├── ScoreDistributionChart.tsx  # 分数分布图
│   ├── ClassicModePanel.tsx   # 经典模式参数面板
│   ├── ProgressiveModePanel.tsx # 累进模式参数面板
│   ├── ParameterSlider.tsx    # 参数滑块通用组件
│   ├── ActionButtons.tsx      # 操作按钮组
│   └── hooks/
│       ├── useScoringConfig.ts    # 配置管理 hook
│       └── useScorePreview.ts     # 分数预览 hook
└── ...
```

---

## 3. 核心组件实现

### 3.1 ScoringConfigPanel (根组件)

**文件**: `web_ui/src/components/scoring/index.tsx`

```tsx
import { useState, useEffect, useCallback } from "react";
import { ModeSelector } from "./ModeSelector";
import { WeightConfig } from "./WeightConfig";
import { ScoreDistributionChart } from "./ScoreDistributionChart";
import { ClassicModePanel } from "./ClassicModePanel";
import { ProgressiveModePanel } from "./ProgressiveModePanel";
import { ActionButtons } from "./ActionButtons";
import { useScoringConfig } from "./hooks/useScoringConfig";
import { useScorePreview } from "./hooks/useScorePreview";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ScoringConfigData {
  mode: "classic" | "progressive" | "custom";
  classic_shadow_min: number;
  classic_shadow_max: number;
  classic_body_good: number;
  classic_body_bad: number;
  classic_vol_min: number;
  classic_vol_max: number;
  classic_trend_max_dist: number;
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
  w_shape: number;
  w_trend: number;
  w_vol: number;
}

export function ScoringConfigPanel() {
  const {
    config,
    loading,
    error,
    fetchConfig,
    updateConfig,
    resetToDefaults,
  } = useScoringConfig();

  const { previewData, fetchPreview, submitting: previewSubmitting } =
    useScorePreview();

  const [modifiedConfig, setModifiedConfig] = useState<ScoringConfigData | null>(
    null
  );
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // 初始化加载配置
  useEffect(() => {
    fetchConfig();
  }, []);

  // 配置变更时更新预览
  useEffect(() => {
    if (modifiedConfig) {
      const debounce = setTimeout(() => {
        fetchPreview(modifiedConfig);
      }, 500);
      return () => clearTimeout(debounce);
    }
  }, [modifiedConfig]);

  const handleConfigChange = useCallback((updates: Partial<ScoringConfigData>) => {
    setModifiedConfig((prev) => {
      if (!prev) return prev;
      const updated = { ...prev, ...updates };
      return updated;
    });
    setHasUnsavedChanges(true);
  }, []);

  const handleSave = async () => {
    if (!modifiedConfig) return;

    try {
      await updateConfig(modifiedConfig);
      setHasUnsavedChanges(false);
      toast.success("配置已保存");
    } catch (err) {
      toast.error("保存失败", {
        description: err instanceof Error ? err.message : "请检查网络或后端服务",
      });
    }
  };

  const handleReset = () => {
    resetToDefaults();
    setModifiedConfig(null);
    setHasUnsavedChanges(false);
    toast.success("已重置为默认配置");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center text-rose-500 p-8">
        <p>加载配置失败：{error}</p>
      </div>
    );
  }

  const activeConfig = modifiedConfig || config;

  return (
    <ScrollArea className="h-[calc(100vh-100px)]">
      <div className="p-6 space-y-6">
        {/* 标题和操作按钮 */}
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            打分配置中心
          </h2>
          <ActionButtons
            onSave={handleSave}
            onReset={handleReset}
            hasUnsavedChanges={hasUnsavedChanges}
            disabled={previewSubmitting}
          />
        </div>

        {/* 模式选择器 */}
        <Card>
          <ModeSelector
            mode={activeConfig.mode}
            onModeChange={(mode) => handleConfigChange({ mode })}
          />
        </Card>

        {/* 权重配置 + 分数预览 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <WeightConfig
              w_shape={activeConfig.w_shape}
              w_trend={activeConfig.w_trend}
              w_vol={activeConfig.w_vol}
              onWeightsChange={(weights) =>
                handleConfigChange({
                  w_shape: weights.w_shape,
                  w_trend: weights.w_trend,
                  w_vol: weights.w_vol,
                })
              }
            />
          </Card>
          <Card>
            <ScoreDistributionChart data={previewData} loading={previewSubmitting} />
          </Card>
        </div>

        {/* 经典模式参数 */}
        {activeConfig.mode !== "progressive" && (
          <Card>
            <ClassicModePanel
              config={activeConfig}
              onChange={handleConfigChange}
            />
          </Card>
        )}

        {/* 累进模式参数 */}
        {activeConfig.mode !== "classic" && (
          <Card>
            <ProgressiveModePanel
              config={activeConfig}
              onChange={handleConfigChange}
            />
          </Card>
        )}
      </div>
    </ScrollArea>
  );
}
```

---

### 3.2 ModeSelector (模式选择器)

**文件**: `web_ui/src/components/scoring/ModeSelector.tsx`

```tsx
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { InfoTooltip } from "@/components/ui/info-tooltip";

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
                  <span className="text-xs px-2 py-0.5 bg-blue-500 text-white rounded-full">
                    {m.badge}
                  </span>
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
```

---

### 3.3 WeightConfig (权重配置)

**文件**: `web_ui/src/components/scoring/WeightConfig.tsx`

```tsx
import { useState, useEffect } from "react";
import { WeightSlider } from "./WeightSlider";
import { AlertCircle } from "lucide-react";

interface WeightConfigProps {
  w_shape: number;
  w_trend: number;
  w_vol: number;
  onWeightsChange: (weights: { w_shape: number; w_trend: number; w_vol: number }) => void;
}

export function WeightConfig({ w_shape, w_trend, w_vol, onWeightsChange }: WeightConfigProps) {
  const [localWeights, setLocalWeights] = useState({ w_shape, w_trend, w_vol });
  const [total, setTotal] = useState(1.0);

  useEffect(() => {
    setLocalWeights({ w_shape, w_trend, w_vol });
  }, [w_shape, w_trend, w_vol]);

  useEffect(() => {
    const sum = localWeights.w_shape + localWeights.w_trend + localWeights.w_vol;
    setTotal(Math.round(sum * 1000) / 1000);
  }, [localWeights]);

  const isValid = Math.abs(total - 1.0) < 0.001;

  const handleWeightChange = (key: string, value: number) => {
    const updated = { ...localWeights, [key]: value };
    setLocalWeights(updated);
    onWeightsChange(updated);
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">权重配置</h3>
      </div>

      <div className="space-y-4">
        <WeightSlider
          label="形态评分"
          description="影线比例、实体大小"
          value={localWeights.w_shape}
          onChange={(v) => handleWeightChange("w_shape", v)}
          color="blue"
        />
        <WeightSlider
          label="趋势评分"
          description="EMA60 距离、穿透"
          value={localWeights.w_trend}
          onChange={(v) => handleWeightChange("w_trend", v)}
          color="green"
        />
        <WeightSlider
          label="波动评分"
          description="ATR 倍数"
          value={localWeights.w_vol}
          onChange={(v) => handleWeightChange("w_vol", v)}
          color="orange"
        />
      </div>

      <div className={`flex items-center gap-2 p-3 rounded-lg ${
        isValid
          ? "bg-green-50 dark:bg-green-950/20 text-green-600"
          : "bg-amber-50 dark:bg-amber-950/20 text-amber-600"
      }`}>
        <AlertCircle className="w-4 h-4" />
        <span className="text-sm font-medium">
          {isValid
            ? `✓ 权重和为 ${(total * 100).toFixed(1)}%`
            : `⚠ 权重和为 ${(total * 100).toFixed(1)}%，必须等于 100%`}
        </span>
      </div>
    </div>
  );
}
```

---

### 3.4 ScoreDistributionChart (分数分布图)

**文件**: `web_ui/src/components/scoring/ScoreDistributionChart.tsx`

```tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface ScoreDistributionChartProps {
  data: {
    total_bars?: number;
    signals_found?: number;
    score_distribution?: Record<string, number>;
    tier_distribution?: Record<string, number>;
  } | null;
  loading: boolean;
}

export function ScoreDistributionChart({ data, loading }: ScoreDistributionChartProps) {
  const chartData = data?.score_distribution
    ? Object.entries(data.score_distribution).map(([range, count]) => ({
        range,
        count,
      }))
    : [];

  const getColor = (range: string) => {
    if (range === "80-100") return "#f59e0b"; // 琥珀色 - A 级
    if (range === "60-80") return "#3b82f6"; // 蓝色 - B 级
    if (range === "40-60") return "#6b7280"; // 灰色 - C 级
    return "#d1d5db"; // 浅灰 - 拒绝
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-zinc-500">计算中...</div>
      </div>
    );
  }

  if (!data || chartData.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-zinc-500">
        <p className="text-sm">暂无预览数据</p>
        <p className="text-xs mt-1">调整参数后自动计算</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold">分数分布预览</h3>
        <div className="text-xs text-zinc-500">
          基于最近 {data.total_bars || 0} 根 K 线 ({data.signals_found || 0} 个信号)
        </div>
      </div>

      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <XAxis
              dataKey="range"
              tick={{ fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(255,255,255,0.95)",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
              }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getColor(entry.range)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 图例 */}
      <div className="flex items-center justify-center gap-4 mt-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-amber-500" />
          <span>A 级 (精品)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-blue-500" />
          <span>B 级 (普通)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-zinc-500" />
          <span>C 级 (观察)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-zinc-300" />
          <span>拒绝</span>
        </div>
      </div>
    </div>
  );
}
```

---

### 3.5 ParameterSlider (通用参数滑块)

**文件**: `web_ui/src/components/scoring/ParameterSlider.tsx`

```tsx
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InfoTooltip } from "@/components/ui/info-tooltip";

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
}: ParameterSliderProps) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-4 items-center py-3">
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
          className="w-[100px] text-right"
          step={step}
          min={min}
          max={max}
        />
        <span className="text-sm text-zinc-500 w-12">{suffix}</span>
        {onReset && (
          <button
            onClick={onReset}
            className="text-xs text-zinc-400 hover:text-zinc-600"
          >
            重置
          </button>
        )}
      </div>
    </div>
  );
}
```

---

### 3.6 ClassicModePanel (经典模式参数面板)

**文件**: `web_ui/src/components/scoring/ClassicModePanel.tsx`

```tsx
import { ParameterSlider } from "./ParameterSlider";
import { Button } from "@/components/ui/button";

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
  config: any;
  onChange: (updates: Record<string, number>) => void;
}

export function ClassicModePanel({ config, onChange }: ClassicModePanelProps) {
  const handleReset = () => {
    onChange(DEFAULTS);
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold">经典模式参数配置</h3>
        <Button variant="ghost" size="sm" onClick={handleReset}>
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
        />
        <ParameterSlider
          label="影线比例最大值 (100 分)"
          description="高于此值形态分为 100"
          value={config.classic_shadow_max}
          min={0.7}
          max={1.0}
          step={0.01}
          onChange={(v) => onChange({ classic_shadow_max: v })}
        />
        <ParameterSlider
          label="实体比例优秀阈值"
          description="低于此值实体分满分"
          value={config.classic_body_good}
          min={0.01}
          max={0.3}
          step={0.01}
          onChange={(v) => onChange({ classic_body_good: v })}
        />
        <ParameterSlider
          label="实体比例差阈值"
          description="高于此值实体分 0 分"
          value={config.classic_body_bad}
          min={0.3}
          max={0.7}
          step={0.01}
          onChange={(v) => onChange({ classic_body_bad: v })}
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
        />
        <ParameterSlider
          label="趋势距离最大值"
          description="超过此值趋势分为 0"
          value={config.classic_trend_max_dist}
          min={0.01}
          max={0.1}
          step={0.005}
          onChange={(v) => onChange({ classic_trend_max_dist: v })}
        />
      </div>
    </div>
  );
}
```

---

### 3.7 ProgressiveModePanel (累进模式参数面板)

**文件**: `web_ui/src/components/scoring/ProgressiveModePanel.tsx`

```tsx
import { ParameterSlider } from "./ParameterSlider";
import { Button } from "@/components/ui/button";

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
  config: any;
  onChange: (updates: Record<string, number>) => void;
}

export function ProgressiveModePanel({ config, onChange }: ProgressiveModePanelProps) {
  const handleReset = () => {
    onChange(DEFAULTS);
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold">累进模式参数配置</h3>
        <Button variant="ghost" size="sm" onClick={handleReset}>
          重置为默认
        </Button>
      </div>

      {/* 基础分配置 */}
      <div className="space-y-1 border-b border-zinc-200 dark:border-zinc-800 pb-4 mb-4">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
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
        />
      </div>

      {/* 形态奖励配置 */}
      <div className="space-y-1 border-b border-zinc-200 dark:border-zinc-800 pb-4 mb-4">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
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
        />
        <ParameterSlider
          label="实体奖励阈值"
          description="低于此值开始奖励"
          value={config.progressive_body_bonus_threshold}
          min={0.05}
          max={0.2}
          step={0.01}
          onChange={(v) => onChange({ progressive_body_bonus_threshold: v })}
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
        />
        <ParameterSlider
          label="十字星固定奖励分"
          description="实体<5% 时的额外奖励"
          value={config.progressive_doji_bonus}
          min={0}
          max={20}
          step={1}
          suffix="分"
          onChange={(v) => onChange({ progressive_doji_bonus: v })}
        />
      </div>

      {/* 波动奖励配置 */}
      <div className="space-y-1 border-b border-zinc-200 dark:border-zinc-800 pb-4 mb-4">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
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
        />
      </div>

      {/* 趋势奖励配置 */}
      <div className="space-y-1">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
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
        />
      </div>
    </div>
  );
}
```

---

### 3.8 ActionButtons (操作按钮组)

**文件**: `web_ui/src/components/scoring/ActionButtons.tsx`

```tsx
import { Button } from "@/components/ui/button";
import { Save, RotateCcw } from "lucide-react";

interface ActionButtonsProps {
  onSave: () => void;
  onReset: () => void;
  hasUnsavedChanges: boolean;
  disabled?: boolean;
}

export function ActionButtons({
  onSave,
  onReset,
  hasUnsavedChanges,
  disabled,
}: ActionButtonsProps) {
  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={onReset}
        disabled={disabled}
        className="text-zinc-600 dark:text-zinc-400"
      >
        <RotateCcw className="w-4 h-4 mr-2" />
        重置
      </Button>
      <Button
        size="sm"
        onClick={onSave}
        disabled={disabled || !hasUnsavedChanges}
        className="bg-blue-600 hover:bg-blue-700 text-white"
      >
        <Save className="w-4 h-4 mr-2" />
        保存
        {hasUnsavedChanges && (
          <span className="ml-1 w-2 h-2 bg-white rounded-full animate-pulse" />
        )}
      </Button>
    </div>
  );
}
```

---

## 4. Hooks 实现

### 4.1 useScoringConfig

**文件**: `web_ui/src/components/scoring/hooks/useScoringConfig.ts`

```tsx
import { useState, useCallback } from "react";

const DEFAULT_CONFIG = {
  mode: "classic" as const,
  classic_shadow_min: 0.6,
  classic_shadow_max: 0.9,
  classic_body_good: 0.1,
  classic_body_bad: 0.5,
  classic_vol_min: 1.2,
  classic_vol_max: 3.0,
  classic_trend_max_dist: 0.03,
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
  w_shape: 0.4,
  w_trend: 0.3,
  w_vol: 0.3,
};

export function useScoringConfig() {
  const [config, setConfig] = useState<any>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://localhost:8000/api/config/scoring");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setConfig(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const updateConfig = useCallback(async (updates: any) => {
    const res = await fetch("http://localhost:8000/api/config/scoring", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "更新失败" }));
      throw new Error(error.detail || "更新失败");
    }
    const data = await res.json();
    setConfig(data.config || { ...config, ...updates });
  }, [config]);

  const resetToDefaults = useCallback(() => {
    setConfig(DEFAULT_CONFIG);
  }, []);

  return {
    config,
    loading,
    error,
    fetchConfig,
    updateConfig,
    resetToDefaults,
  };
}
```

---

### 4.2 useScorePreview

**文件**: `web_ui/src/components/scoring/hooks/useScorePreview.ts`

```tsx
import { useState, useCallback } from "react";

export function useScorePreview() {
  const [previewData, setPreviewData] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);

  const fetchPreview = useCallback(async (config: any) => {
    setSubmitting(true);
    try {
      const res = await fetch("http://localhost:8000/api/config/scoring/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config,
          symbol: "BTCUSDT",
          interval: "1h",
          limit: 500,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPreviewData(data.data);
    } catch (err) {
      console.error("预览失败:", err);
    } finally {
      setSubmitting(false);
    }
  }, []);

  return {
    previewData,
    fetchPreview,
    submitting,
  };
}
```

---

## 5. 与后端 API 交互

### 5.1 请求时序图

```
用户打开配置页面
    ↓
前端：useScoringConfig.fetchConfig()
    ↓
GET /api/config/scoring
    ↓
后端：返回当前配置
    ↓
前端：渲染配置表单
    ↓
────────── 用户调整参数 ──────────
    ↓
前端：参数变更 → modifiedConfig
    ↓
防抖 500ms → useScorePreview.fetchPreview()
    ↓
POST /api/config/scoring/preview
    ↓
后端：使用新配置回测最近 500 根 K 线
    ↓
后端：返回分数分布数据
    ↓
前端：更新 ScoreDistributionChart
    ↓
────────── 用户点击保存 ──────────
    ↓
PUT /api/config/scoring
    ↓
后端：验证 → 持久化 → 热加载
    ↓
前端：显示成功提示
```

### 5.2 表单验证规则

| 字段 | 验证规则 | 错误提示 |
|------|----------|----------|
| `w_shape + w_trend + w_vol` | 总和必须 = 1.0 | "权重和必须等于 100%" |
| `classic_shadow_min` | 0.3 ≤ value ≤ 0.8 | "范围：0.3 - 0.8" |
| `classic_shadow_max` | value > classic_shadow_min | "必须大于最小值" |
| 所有累进参数 | 在定义范围内 | "超出允许范围" |

---

## 6. 响应式设计

### 6.1 断点定义

```css
/* Tailwind CSS 默认断点 */
sm: 640px   /* 平板竖屏 */
md: 768px   /* 平板横屏 */
lg: 1024px  /* 小屏笔记本 */
xl: 1280px  /* 桌面 */
2xl: 1536px /* 大屏桌面 */
```

### 6.2 布局适配

| 断点 | 布局策略 |
|------|----------|
| < lg | 权重配置和预览图垂直堆叠 |
| ≥ lg | 权重配置和预览图并排显示 |
| < md | 参数面板全宽显示 |
| ≥ md | 参数面板两侧留白 |

---

## 7. 主题支持

### 7.1 深色模式

所有组件使用 Tailwind 的 `dark:` 前缀适配深色模式：

```tsx
<div className="bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800">
  <h3 className="text-zinc-900 dark:text-zinc-100">
    ...
  </h3>
</div>
```

### 7.2 颜色变量

```css
/* 建议使用 CSS 变量便于主题切换 */
:root {
  --color-shape: 59 130 246;    /* blue-500 */
  --color-trend: 34 197 94;     /* green-500 */
  --color-vol: 249 115 22;      /* orange-500 */
  --color-a-tier: 245 158 11;   /* amber-500 */
  --color-b-tier: 59 130 246;   /* blue-500 */
}
```

---

## 8. 性能优化

### 8.1 防抖优化

参数滑块拖动时，使用 500ms 防抖触发预览更新：

```tsx
useEffect(() => {
  const debounce = setTimeout(() => {
    fetchPreview(modifiedConfig);
  }, 500);
  return () => clearTimeout(debounce);
}, [modifiedConfig]);
```

### 8.2 缓存策略

- 使用 React Query 缓存配置数据
- 分数预览数据缓存 1 分钟

---

## 9. 附录

### 9.1 相关文件

- [产品需求文档](../scoring_config_prd.md)
- [技术设计文档](../scoring_config_technical_design.md)
- [API 接口文档](../api/scoring_config_api.md)

### 9.2 修订历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2026-03-03 | Claude | 初始版本 |
