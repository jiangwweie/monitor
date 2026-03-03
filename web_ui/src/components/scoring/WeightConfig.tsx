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

  const handleWeightChange = (key: "w_shape" | "w_trend" | "w_vol", value: number) => {
    const otherKeys: Array<"w_shape" | "w_trend" | "w_vol"> = key === "w_shape" ? ["w_trend", "w_vol"]
      : key === "w_trend" ? ["w_shape", "w_vol"]
      : ["w_shape", "w_trend"];

    const otherWeightsSum = localWeights[otherKeys[0]] + localWeights[otherKeys[1]];
    const remainingWeight = 1 - value;

    let updated: { w_shape: number; w_trend: number; w_vol: number };

    if (otherWeightsSum === 0) {
      // 如果其他两个权重都为 0，平均分配剩余权重
      updated = {
        ...localWeights,
        [key]: value,
        [otherKeys[0]]: remainingWeight / 2,
        [otherKeys[1]]: remainingWeight / 2,
      };
    } else {
      // 按比例调整其他两个权重
      const ratio0 = localWeights[otherKeys[0]] / otherWeightsSum;
      const ratio1 = localWeights[otherKeys[1]] / otherWeightsSum;
      updated = {
        ...localWeights,
        [key]: value,
        [otherKeys[0]]: remainingWeight * ratio0,
        [otherKeys[1]]: remainingWeight * ratio1,
      };
    }

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
          ? "bg-green-50 dark:bg-green-950/20 text-green-600 dark:text-green-400"
          : "bg-amber-50 dark:bg-amber-950/20 text-amber-600 dark:text-amber-400"
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
