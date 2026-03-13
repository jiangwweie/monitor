import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { ShieldCheck, Zap, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface RiskTabProps {
  initialConfig: any;
  onConfigChange: (field: string, value: any) => void;
}

export function RiskTab({ initialConfig, onConfigChange }: RiskTabProps) {
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    risk_pct: 2.0,
    max_sl_dist: 3.5,
    max_leverage: 20,
    max_position_value_ratio: 20,
    w_shape: 50,
    w_trend: 30,
    w_vol: 20,
  });

  useEffect(() => {
    setFormData({
      risk_pct: initialConfig.risk_pct ?? 2.0,
      max_sl_dist: initialConfig.max_sl_dist ?? 3.5,
      max_leverage: initialConfig.max_leverage ?? 20,
      max_position_value_ratio: initialConfig.max_position_value_ratio ?? 20,
      w_shape: initialConfig.w_shape ?? 50,
      w_trend: initialConfig.w_trend ?? 30,
      w_vol: initialConfig.w_vol ?? 20,
    });
  }, [initialConfig]);

  const handleSave = async () => {
    setLoading(true);
    try {
      // 保存风控配置
      const riskRes = await fetch("http://localhost:8000/api/config/risk", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          risk_pct: Math.round(Number(formData.risk_pct) * 100) / 10000.0,
          max_sl_dist: Math.round(Number(formData.max_sl_dist) * 100) / 10000.0,
          max_leverage: Number(formData.max_leverage),
          max_position_value_ratio: Number(formData.max_position_value_ratio),
        }),
      });

      // 保存评分权重
      const scoringRes = await fetch("http://localhost:8000/api/config/scoring", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          w_shape: Number(formData.w_shape) / 100.0,
          w_trend: Number(formData.w_trend) / 100.0,
          w_vol: Number(formData.w_vol) / 100.0,
        }),
      });

      if (riskRes.ok && scoringRes.ok) {
        toast.success("风控与评分配置已保存", {
          description: "风险参数和 AI 评分权重已更新。",
          className: "bg-zinc-900 border border-white/10 text-zinc-100",
        });
        onConfigChange("risk_pct", formData.risk_pct);
        onConfigChange("max_sl_dist", formData.max_sl_dist);
        onConfigChange("max_leverage", formData.max_leverage);
        onConfigChange("max_position_value_ratio", formData.max_position_value_ratio);
        onConfigChange("w_shape", formData.w_shape);
        onConfigChange("w_trend", formData.w_trend);
        onConfigChange("w_vol", formData.w_vol);
      } else {
        throw new Error("Save failed");
      }
    } catch (error) {
      toast.error("保存失败", {
        description: "后端服务离线或网络异常。",
        className: "bg-red-950 border border-red-900",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleWeightChange = (field: string, value: number) => {
    setFormData((prev) => {
      const otherFields = ["w_shape", "w_trend", "w_vol"].filter((f) => f !== field) as Array<
        "w_shape" | "w_trend" | "w_vol"
      >;
      const oldValue = prev[field as keyof typeof prev] as number;
      const diff = value - oldValue;
      const sumOthers = otherFields.reduce(
        (acc, f) => acc + (prev[f] as number),
        0
      );

      let nextState = { ...prev, [field]: value };

      if (sumOthers === 0) {
        const remainder = 100 - value;
        nextState[otherFields[0]] = remainder / 2;
        nextState[otherFields[1]] = remainder / 2;
      } else {
        otherFields.forEach((f) => {
          const current = prev[f] as number;
          const ratio = current / sumOthers;
          nextState[f] = Math.max(0, Math.round(current - diff * ratio));
        });
      }

      const intShape = Math.round(nextState.w_shape);
      const intTrend = Math.round(nextState.w_trend);
      const intVol = 100 - intShape - intTrend;

      return {
        ...nextState,
        w_shape: intShape,
        w_trend: intTrend,
        w_vol: intVol,
      };
    });
  };

  return (
    <div className="space-y-6">
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
            <ShieldCheck className="w-5 h-5" /> 风控参数
          </CardTitle>
          <CardDescription>配置单笔风险、止损距离、最大杠杆和仓位价值比例</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-zinc-700 dark:text-zinc-300">
                单笔风险度 (%)
              </Label>
              <Input
                type="number"
                step="0.01"
                value={formData.risk_pct}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, risk_pct: Number(e.target.value) }))
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-zinc-700 dark:text-zinc-300">
                最大止损距离 (%)
              </Label>
              <Input
                type="number"
                step="0.01"
                value={formData.max_sl_dist}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, max_sl_dist: Number(e.target.value) }))
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-zinc-700 dark:text-zinc-300">
                最大杠杆倍数 (x)
              </Label>
              <Input
                type="number"
                value={formData.max_leverage}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, max_leverage: Number(e.target.value) }))
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-zinc-700 dark:text-zinc-300">
                仓位价值比例上限 (倍)
              </Label>
              <Input
                type="number"
                value={formData.max_position_value_ratio}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, max_position_value_ratio: Number(e.target.value) }))
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white"
              />
            </div>
          </div>

          <Button
            onClick={handleSave}
            disabled={loading}
            className="w-full h-12 rounded-2xl bg-zinc-900 text-white dark:bg-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all text-base font-semibold shadow-xl shadow-black/5 dark:shadow-white/5"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> 保存中...
              </>
            ) : (
              "保存风控配置"
            )}
          </Button>
        </CardContent>
      </Card>

      <Card className="backdrop-blur-xl bg-gradient-to-br from-white to-zinc-50 dark:from-zinc-900 dark:to-zinc-950 border border-zinc-200 dark:border-white/10 rounded-3xl shadow-lg ring-1 ring-black/5 dark:ring-white/5 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-full h-1 bg-gradient-to-r from-blue-500 via-purple-500 to-amber-500 opacity-50" />
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
            <Zap className="w-5 h-5 text-amber-500" /> AI 评分权重
          </CardTitle>
          <CardDescription>
            调整各维度打分的考量基准（互嵌联动以维持 100%）。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 pt-4">
          <div className="space-y-3">
            <div className="flex justify-between items-end">
              <Label className="text-zinc-700 dark:text-zinc-300">
                形态完美度 (影线占比)
              </Label>
              <span className="text-xs font-mono text-zinc-500">
                {formData.w_shape}%
              </span>
            </div>
            <Slider
              value={[formData.w_shape]}
              onValueChange={(v) => handleWeightChange("w_shape", v[0])}
              max={100}
              step={1}
              className="py-2"
            />
          </div>

          <div className="space-y-3">
            <div className="flex justify-between items-end">
              <Label className="text-zinc-700 dark:text-zinc-300">
                趋势顺应度 (EMA 距离)
              </Label>
              <span className="text-xs font-mono text-zinc-500">
                {formData.w_trend}%
              </span>
            </div>
            <Slider
              value={[formData.w_trend]}
              onValueChange={(v) => handleWeightChange("w_trend", v[0])}
              max={100}
              step={1}
              className="py-2"
            />
          </div>

          <div className="space-y-3">
            <div className="flex justify-between items-end">
              <Label className="text-zinc-700 dark:text-zinc-300">
                波动率健康度 (ATR)
              </Label>
              <span className="text-xs font-mono text-zinc-500">
                {formData.w_vol}%
              </span>
            </div>
            <Slider
              value={[formData.w_vol]}
              onValueChange={(v) => handleWeightChange("w_vol", v[0])}
              max={100}
              step={1}
              className="py-2"
            />
          </div>
        </CardContent>
        <CardFooter className="bg-white/[0.02] border-t border-zinc-200 dark:border-white/5 py-3">
          <p className="text-xs text-zinc-500 w-full text-center">
            总评分 = (权重 1 × 形态) + (权重 2 × 趋势) + (权重 3 × 波动)
          </p>
        </CardFooter>
      </Card>

      <Button
        onClick={handleSave}
        disabled={loading}
        className="w-full h-12 rounded-2xl bg-zinc-900 text-white dark:bg-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all text-base font-semibold shadow-xl shadow-black/5 dark:shadow-white/5"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin mr-2" /> 保存中...
          </>
        ) : (
          "保存评分权重配置"
        )}
      </Button>
    </div>
  );
}
