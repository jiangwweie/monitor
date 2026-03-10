/**
 * Backtest Configuration Form
 * 回测参数配置表单 - Apple 风格极简设计
 */

import { useState } from "react";
import { ChevronDown, ChevronUp, Settings, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { toast } from "sonner";

import {
  getAvailableSymbols,
  getIntervals,
  formatDateForApi,
  type BacktestConfig,
} from "@/services/backtest_api";

interface BacktestConfigFormProps {
  onSubmit: (config: BacktestConfig) => void;
  isLoading: boolean;
}

interface FormData {
  symbol: string;
  interval: string;
  startDate: string;
  endDate: string;
  // FMZ 配置
  initialBalance: number;
  slipPoint: number;
  feeMaker: number;
  feeTaker: number;
  // 策略参数
  maxSlDist: number;
  bodyMaxRatio: number;
  shadowMinRatio: number;
  volatilityAtrMultiplier: number;
  dojiThreshold: number;
  dojiShadowBonus: number;
  mtfTrendFilterMode: string;
  dynamicSlEnabled: boolean;
  dynamicSlBase: number;
  dynamicSlAtrMultiplier: number;
  // 评分权重
  wShape: number;
  wTrend: number;
  wVol: number;
}

const defaultFormData: FormData = {
  symbol: "BTCUSDT",
  interval: "1h",
  startDate: "2024-01-01",
  endDate: "2024-06-30",
  initialBalance: 10000,
  slipPoint: 0,
  feeMaker: 75,
  feeTaker: 80,
  maxSlDist: 3.5,
  bodyMaxRatio: 0.25,
  shadowMinRatio: 2.5,
  volatilityAtrMultiplier: 1.2,
  dojiThreshold: 0.05,
  dojiShadowBonus: 0.6,
  mtfTrendFilterMode: "soft",
  dynamicSlEnabled: true,
  dynamicSlBase: 3.5,
  dynamicSlAtrMultiplier: 0.5,
  wShape: 50,
  wTrend: 30,
  wVol: 20,
};

export function BacktestConfigForm({ onSubmit, isLoading }: BacktestConfigFormProps) {
  const [formData, setFormData] = useState<FormData>(defaultFormData);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const symbols = getAvailableSymbols();
  const intervals = getIntervals();

  const handleChange = (field: keyof FormData, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // 验证
    if (!formData.symbol || !formData.interval) {
      toast.error("请选择交易对和周期");
      return;
    }
    if (!formData.startDate || !formData.endDate) {
      toast.error("请选择时间区间");
      return;
    }
    if (new Date(formData.startDate) >= new Date(formData.endDate)) {
      toast.error("结束日期必须晚于开始日期");
      return;
    }

    // 组装 Payload
    const config: BacktestConfig = {
      symbol: formData.symbol,
      interval: formData.interval,
      start_date: `${formData.startDate} 00:00:00`,
      end_date: `${formData.endDate} 23:59:59`,
      fmz_config: {
        initial_balance: formData.initialBalance,
        fee_maker: formData.feeMaker,
        fee_taker: formData.feeTaker,
        fee_denominator: 5,
        slip_point: formData.slipPoint,
      },
      strategy_config: {
        max_sl_dist: formData.maxSlDist / 100,
        pinbar_config: {
          body_max_ratio: formData.bodyMaxRatio,
          shadow_min_ratio: formData.shadowMinRatio,
          volatility_atr_multiplier: formData.volatilityAtrMultiplier,
          doji_threshold: formData.dojiThreshold,
          doji_shadow_bonus: formData.dojiShadowBonus,
          mtf_trend_filter_mode: formData.mtfTrendFilterMode,
          dynamic_sl_enabled: formData.dynamicSlEnabled,
          dynamic_sl_base: formData.dynamicSlBase / 100,
          dynamic_sl_atr_multiplier: formData.dynamicSlAtrMultiplier,
        },
        scoring_weights: {
          w_shape: formData.wShape / 100,
          w_trend: formData.wTrend / 100,
          w_vol: formData.wVol / 100,
        },
      },
    };

    onSubmit(config);
  };

  const resetForm = () => {
    setFormData(defaultFormData);
    toast.success("已重置为默认配置");
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* 基础配置 */}
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
        <CardContent className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 交易对 */}
            <div className="space-y-2">
              <Label htmlFor="symbol" className="text-zinc-700 dark:text-zinc-300 font-medium">
                交易对
              </Label>
              <Select
                value={formData.symbol}
                onValueChange={(value) => handleChange("symbol", value)}
              >
                <SelectTrigger className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-11">
                  <SelectValue placeholder="选择交易对" />
                </SelectTrigger>
                <SelectContent>
                  {symbols.map((sym) => (
                    <SelectItem key={sym} value={sym}>
                      {sym}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 周期 */}
            <div className="space-y-2">
              <Label htmlFor="interval" className="text-zinc-700 dark:text-zinc-300 font-medium">
                K 线周期
              </Label>
              <Select
                value={formData.interval}
                onValueChange={(value) => handleChange("interval", value)}
              >
                <SelectTrigger className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-11">
                  <SelectValue placeholder="选择周期" />
                </SelectTrigger>
                <SelectContent>
                  {intervals.map((i) => (
                    <SelectItem key={i.value} value={i.value}>
                      {i.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 开始日期 */}
            <div className="space-y-2">
              <Label htmlFor="startDate" className="text-zinc-700 dark:text-zinc-300 font-medium">
                开始日期
              </Label>
              <Input
                id="startDate"
                type="date"
                value={formData.startDate}
                onChange={(e) => handleChange("startDate", e.target.value)}
                className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-11"
              />
            </div>

            {/* 结束日期 */}
            <div className="space-y-2">
              <Label htmlFor="endDate" className="text-zinc-700 dark:text-zinc-300 font-medium">
                结束日期
              </Label>
              <Input
                id="endDate"
                type="date"
                value={formData.endDate}
                onChange={(e) => handleChange("endDate", e.target.value)}
                className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-11"
              />
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex items-center gap-3 pt-4">
            <Button
              type="submit"
              disabled={isLoading}
              className="bg-zinc-900 hover:bg-zinc-800 dark:bg-white dark:hover:bg-zinc-200 dark:text-zinc-900 rounded-xl px-6 h-11 font-medium transition-all"
            >
              <Zap className="w-4 h-4 mr-2" />
              {isLoading ? "启动中..." : "启动回测"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={resetForm}
              className="border-zinc-200 dark:border-white/10 rounded-xl h-11 px-6"
            >
              重置
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 高级设置折叠面板 */}
      <div className="space-y-4">
        <button
          type="button"
          onClick={() => setAdvancedOpen(!advancedOpen)}
          className="w-full flex items-center justify-between py-3 px-2 text-left hover:bg-white/30 dark:hover:bg-white/5 rounded-xl transition-colors"
        >
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-zinc-500" />
            <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              高级设置
            </span>
          </div>
          {advancedOpen ? (
            <ChevronUp className="w-4 h-4 text-zinc-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-500" />
          )}
        </button>

        {advancedOpen && (
          <div className="space-y-6 animate-in slide-in-from-top-2 duration-200">
            {/* FMZ 引擎配置 */}
            <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
              <CardContent className="p-6 space-y-6">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  回测引擎配置
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="space-y-2">
                    <Label className="text-xs text-zinc-500">初始资金 (USDT)</Label>
                    <Input
                      type="number"
                      value={formData.initialBalance}
                      onChange={(e) =>
                        handleChange("initialBalance", Number(e.target.value))
                      }
                      className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-zinc-500">Maker 手续费 (万分之)</Label>
                    <Input
                      type="number"
                      value={formData.feeMaker}
                      onChange={(e) =>
                        handleChange("feeMaker", Number(e.target.value))
                      }
                      className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-zinc-500">Taker 手续费 (万分之)</Label>
                    <Input
                      type="number"
                      value={formData.feeTaker}
                      onChange={(e) =>
                        handleChange("feeTaker", Number(e.target.value))
                      }
                      className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-zinc-500">滑点 (基点)</Label>
                    <Input
                      type="number"
                      value={formData.slipPoint}
                      onChange={(e) =>
                        handleChange("slipPoint", Number(e.target.value))
                      }
                      className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-10"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Pinbar 策略参数 */}
            <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
              <CardContent className="p-6 space-y-6">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Pinbar 策略参数
                </h3>

                {/* 滑块控件组 */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-zinc-500">实体最大占比</Label>
                      <span className="text-xs text-zinc-400">{formData.bodyMaxRatio.toFixed(2)}</span>
                    </div>
                    <Slider
                      value={[formData.bodyMaxRatio]}
                      onValueChange={([v]) => handleChange("bodyMaxRatio", v)}
                      min={0.1}
                      max={0.5}
                      step={0.01}
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-zinc-500">影线最小占比</Label>
                      <span className="text-xs text-zinc-400">{formData.shadowMinRatio.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[formData.shadowMinRatio]}
                      onValueChange={([v]) => handleChange("shadowMinRatio", v)}
                      min={1.5}
                      max={4}
                      step={0.1}
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-zinc-500">波动率 ATR 倍数</Label>
                      <span className="text-xs text-zinc-400">{formData.volatilityAtrMultiplier.toFixed(2)}</span>
                    </div>
                    <Slider
                      value={[formData.volatilityAtrMultiplier]}
                      onValueChange={([v]) => handleChange("volatilityAtrMultiplier", v)}
                      min={0.5}
                      max={3}
                      step={0.1}
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-zinc-500">Doji 阈值</Label>
                      <span className="text-xs text-zinc-400">{formData.dojiThreshold.toFixed(2)}</span>
                    </div>
                    <Slider
                      value={[formData.dojiThreshold]}
                      onValueChange={([v]) => handleChange("dojiThreshold", v)}
                      min={0.01}
                      max={0.15}
                      step={0.01}
                      className="w-full"
                    />
                  </div>
                </div>

                {/* 开关控件组 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-zinc-200 dark:border-white/5">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-xs text-zinc-500">动态止损</Label>
                      <p className="text-xs text-zinc-400">基于 ATR 自适应调整</p>
                    </div>
                    <Switch
                      checked={formData.dynamicSlEnabled}
                      onCheckedChange={(v) => handleChange("dynamicSlEnabled", v)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-xs text-zinc-500">MTF 趋势过滤</Label>
                      <p className="text-xs text-zinc-400">多周期协同过滤</p>
                    </div>
                    <Switch
                      checked={formData.mtfTrendFilterMode !== "off"}
                      onCheckedChange={(v) =>
                        handleChange("mtfTrendFilterMode", v ? "soft" : "off")
                      }
                    />
                  </div>
                </div>

                {/* 额外参数 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-zinc-200 dark:border-white/5">
                  <div className="space-y-2">
                    <Label className="text-xs text-zinc-500">Doji 影线奖励</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.dojiShadowBonus}
                      onChange={(e) =>
                        handleChange("dojiShadowBonus", Number(e.target.value))
                      }
                      className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-zinc-500">最大止损距离 (%)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.maxSlDist}
                      onChange={(e) =>
                        handleChange("maxSlDist", Number(e.target.value))
                      }
                      className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-white/10 rounded-xl h-10"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 评分权重 */}
            <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
              <CardContent className="p-6 space-y-6">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  信号评分权重
                </h3>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-zinc-500">形态分权重</Label>
                      <span className="text-xs text-zinc-400">{formData.wShape}%</span>
                    </div>
                    <Slider
                      value={[formData.wShape]}
                      onValueChange={([v]) => handleChange("wShape", v)}
                      min={0}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-zinc-500">趋势分权重</Label>
                      <span className="text-xs text-zinc-400">{formData.wTrend}%</span>
                    </div>
                    <Slider
                      value={[formData.wTrend]}
                      onValueChange={([v]) => handleChange("wTrend", v)}
                      min={0}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-zinc-500">量能分权重</Label>
                      <span className="text-xs text-zinc-400">{formData.wVol}%</span>
                    </div>
                    <Slider
                      value={[formData.wVol]}
                      onValueChange={([v]) => handleChange("wVol", v)}
                      min={0}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>
                </div>
                <p className="text-xs text-zinc-500 pt-2">
                  当前总和：{formData.wShape + formData.wTrend + formData.wVol}%
                  {formData.wShape + formData.wTrend + formData.wVol !== 100 && (
                    <span className="text-amber-500 ml-2">(建议调整为 100%)</span>
                  )}
                </p>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </form>
  );
}
