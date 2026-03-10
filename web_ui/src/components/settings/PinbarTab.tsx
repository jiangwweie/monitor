import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Zap, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface PinbarTabProps {
  initialConfig: any;
  onConfigChange: (field: string, value: any) => void;
}

export function PinbarTab({ initialConfig, onConfigChange }: PinbarTabProps) {
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    body_max_ratio: 0.25,
    shadow_min_ratio: 2.5,
    volatility_atr_multiplier: 1.2,
    doji_threshold: 0.05,
    doji_shadow_bonus: 0.6,
    mtf_trend_filter_mode: "soft" as "soft" | "hard" | "off",
    dynamic_sl_enabled: true,
    dynamic_sl_base: 0.035,
    dynamic_sl_atr_multiplier: 0.5,
  });

  useEffect(() => {
    setFormData({
      body_max_ratio: initialConfig.body_max_ratio ?? 0.25,
      shadow_min_ratio: initialConfig.shadow_min_ratio ?? 2.5,
      volatility_atr_multiplier: initialConfig.volatility_atr_multiplier ?? 1.2,
      doji_threshold: initialConfig.doji_threshold ?? 0.05,
      doji_shadow_bonus: initialConfig.doji_shadow_bonus ?? 0.6,
      mtf_trend_filter_mode: initialConfig.mtf_trend_filter_mode ?? "soft",
      dynamic_sl_enabled: initialConfig.dynamic_sl_enabled ?? true,
      dynamic_sl_base: initialConfig.dynamic_sl_base ?? 0.035,
      dynamic_sl_atr_multiplier: initialConfig.dynamic_sl_atr_multiplier ?? 0.5,
    });
  }, [initialConfig]);

  const handleSave = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/config/pinbar", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (res.ok) {
        toast.success("Pinbar 策略配置已保存", {
          description: "K 线形态识别参数已更新。",
          className: "bg-zinc-900 border border-white/10 text-zinc-100",
        });
        Object.entries(formData).forEach(([key, value]) => {
          onConfigChange(key, value);
        });
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

  return (
    <div className="space-y-6">
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
            <Zap className="w-5 h-5 text-amber-500" /> Pinbar 策略参数
          </CardTitle>
          <CardDescription>调整 K 线形态识别的核心比例与阈值</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <Label className="text-zinc-700 dark:text-zinc-300">
                实体最大比例 (Body Ratio)
              </Label>
              <span className="font-mono text-sm font-bold text-blue-500">
                {(Number(formData.body_max_ratio) * 100).toFixed(0)}%
              </span>
            </div>
            <Slider
              value={[Number(formData.body_max_ratio) * 100]}
              max={100}
              step={1}
              onValueChange={(val) =>
                setFormData((prev) => ({ ...prev, body_max_ratio: val[0] / 100 }))
              }
              className="py-4"
            />
            <p className="text-xs text-zinc-500">
              实体部分占整根 K 线长度的最大比例。越小越苛刻。
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <Label className="text-zinc-700 dark:text-zinc-300">
                影线最小比例 (Shadow Ratio)
              </Label>
              <span className="font-mono text-sm font-bold text-blue-500">
                {Number(formData.shadow_min_ratio).toFixed(1)}x
              </span>
            </div>
            <Slider
              value={[Number(formData.shadow_min_ratio) * 10]}
              max={50}
              step={1}
              onValueChange={(val) =>
                setFormData((prev) => ({ ...prev, shadow_min_ratio: val[0] / 10 }))
              }
              className="py-4"
            />
            <p className="text-xs text-zinc-500">
              单边影线长度与实体的最小倍数关系。越大影线越长。
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <Label className="text-zinc-700 dark:text-zinc-300">
                波幅 ATR 乘数 (Volatility)
              </Label>
              <span className="font-mono text-sm font-bold text-blue-500">
                {Number(formData.volatility_atr_multiplier).toFixed(1)}x
              </span>
            </div>
            <Slider
              value={[Number(formData.volatility_atr_multiplier) * 10]}
              max={50}
              step={1}
              onValueChange={(val) =>
                setFormData((prev) => ({ ...prev, volatility_atr_multiplier: val[0] / 10 }))
              }
              className="py-4"
            />
            <p className="text-xs text-zinc-500">
              K 线总长度与平均 ATR 的比值。用于过滤极小波动。
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-zinc-200 dark:border-white/10">
            <div className="flex justify-between items-center">
              <Label className="text-zinc-700 dark:text-zinc-300">
                Doji 十字星阈值
              </Label>
              <span className="font-mono text-sm font-bold text-blue-500">
                {(Number(formData.doji_threshold) * 100).toFixed(1)}%
              </span>
            </div>
            <Slider
              value={[Number(formData.doji_threshold) * 1000]}
              max={200}
              step={5}
              onValueChange={(val) =>
                setFormData((prev) => ({ ...prev, doji_threshold: val[0] / 1000 }))
              }
              className="py-4"
            />
            <p className="text-xs text-zinc-500">
              实体占比低于此值视为十字星 Doji。
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <Label className="text-zinc-700 dark:text-zinc-300">
                Doji 影线加分系数
              </Label>
              <span className="font-mono text-sm font-bold text-blue-500">
                {Number(formData.doji_shadow_bonus).toFixed(2)}
              </span>
            </div>
            <Slider
              value={[Number(formData.doji_shadow_bonus) * 100]}
              max={100}
              step={5}
              onValueChange={(val) =>
                setFormData((prev) => ({ ...prev, doji_shadow_bonus: val[0] / 100 }))
              }
              className="py-4"
            />
            <p className="text-xs text-zinc-500">
              Doji 形态的额外加分系数，影线越长加分越多。
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-zinc-200 dark:border-white/10">
            <div className="flex justify-between items-center">
              <Label className="text-zinc-700 dark:text-zinc-300">
                MTF 趋势过滤模式
              </Label>
              <Select
                value={formData.mtf_trend_filter_mode}
                onValueChange={(val: "soft" | "hard" | "off") =>
                  setFormData((prev) => ({ ...prev, mtf_trend_filter_mode: val }))
                }
              >
                <SelectTrigger className="w-[180px] bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="soft">Soft (软过滤)</SelectItem>
                  <SelectItem value="hard">Hard (硬过滤)</SelectItem>
                  <SelectItem value="off">Off (关闭)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-xs text-zinc-500">
              Soft: 趋势不符时扣分；Hard: 趋势不符直接过滤；Off: 不进行趋势过滤。
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-zinc-200 dark:border-white/10">
            <div className="flex items-center justify-between">
              <Label className="text-zinc-700 dark:text-zinc-300">
                动态止损 (Dynamic SL)
              </Label>
              <Button
                variant={formData.dynamic_sl_enabled ? "default" : "outline"}
                size="sm"
                onClick={() =>
                  setFormData((prev) => ({ ...prev, dynamic_sl_enabled: !prev.dynamic_sl_enabled }))
                }
                className={formData.dynamic_sl_enabled ? "bg-blue-500" : ""}
              >
                {formData.dynamic_sl_enabled ? "已启用" : "已禁用"}
              </Button>
            </div>
            {formData.dynamic_sl_enabled && (
              <>
                <div className="flex justify-between items-center">
                  <Label className="text-zinc-700 dark:text-zinc-300">
                    动态止损基础值
                  </Label>
                  <span className="font-mono text-sm font-bold text-blue-500">
                    {(Number(formData.dynamic_sl_base) * 100).toFixed(1)}%
                  </span>
                </div>
                <Slider
                  value={[Number(formData.dynamic_sl_base) * 100]}
                  max={10}
                  step={0.5}
                  onValueChange={(val) =>
                    setFormData((prev) => ({ ...prev, dynamic_sl_base: val[0] / 100 }))
                  }
                  className="py-4"
                />
                <div className="flex justify-between items-center">
                  <Label className="text-zinc-700 dark:text-zinc-300">
                    动态止损 ATR 乘数
                  </Label>
                  <span className="font-mono text-sm font-bold text-blue-500">
                    {Number(formData.dynamic_sl_atr_multiplier).toFixed(2)}x
                  </span>
                </div>
                <Slider
                  value={[Number(formData.dynamic_sl_atr_multiplier) * 10]}
                  max={50}
                  step={1}
                  onValueChange={(val) =>
                    setFormData((prev) => ({ ...prev, dynamic_sl_atr_multiplier: val[0] / 10 }))
                  }
                  className="py-4"
                />
              </>
            )}
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
              "保存 Pinbar 策略配置"
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
