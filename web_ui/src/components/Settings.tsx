import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Zap, Database, ShieldCheck, Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface SettingsProps {
  config: any;
  onConfigChange: (field: string, value: any) => void;
  onSymbolToggle: (symbol: string) => void;
  onWeightAutoBalance: (field: string, value: number[]) => void;
  onSave: (e: React.FormEvent) => void;
}

export function Settings({
  config,
  onConfigChange,
  onSymbolToggle,
  onWeightAutoBalance,
  onSave,
}: SettingsProps) {
  const [saving, setSaving] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [showWecomSecret, setShowWecomSecret] = useState(false);
  const [newSymbolInput, setNewSymbolInput] = useState("");

  const handleSave = async (e: React.FormEvent) => {
    setSaving(true);
    await onSave(e);
    setTimeout(() => setSaving(false), 400);
  };

  return (
    <form onSubmit={handleSave} className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Column 1 */}
      <div className="space-y-6">
        {/* Exchange Integration */}
        <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
              <Database className="w-5 h-5" /> 交易所配置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-3">
              <Label className="text-zinc-700 dark:text-zinc-300">
                监控币种 (可多选)
              </Label>
              <div className="flex flex-wrap gap-2 items-center">
                {config.symbols
                  .split(",")
                  .filter(Boolean)
                  .map((sym: string) => (
                    <Badge
                      key={sym}
                      onClick={() => onSymbolToggle(sym)}
                      className="cursor-pointer px-3 py-1.5 text-sm font-medium transition-all bg-blue-500 text-white hover:bg-blue-600 border-transparent shadow-md"
                      variant="outline"
                    >
                      {sym} ✕
                    </Badge>
                  ))}
                <div className="flex items-center gap-1 ml-2 bg-zinc-100 dark:bg-zinc-800/50 rounded-full pr-1">
                  <Input
                    value={newSymbolInput}
                    onChange={(e) => setNewSymbolInput(e.target.value.toUpperCase())}
                    placeholder="新币种 (如 SOLUSDT)"
                    className="w-32 h-8 text-xs border-none bg-transparent focus-visible:ring-0 px-3 shadow-none"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && newSymbolInput.trim()) {
                        e.preventDefault();
                        if (!config.symbols.includes(newSymbolInput.trim())) {
                          onConfigChange(
                            "symbols",
                            config.symbols +
                              (config.symbols ? "," : "") +
                              newSymbolInput.trim()
                          );
                        }
                        setNewSymbolInput("");
                      }
                    }}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-3 text-xs rounded-full bg-white dark:bg-zinc-700 shadow-sm hover:text-blue-500"
                    onClick={(e) => {
                      e.preventDefault();
                      if (
                        newSymbolInput.trim() &&
                        !config.symbols.includes(newSymbolInput.trim())
                      ) {
                        onConfigChange(
                          "symbols",
                          config.symbols +
                            (config.symbols ? "," : "") +
                            newSymbolInput.trim()
                        );
                      }
                      setNewSymbolInput("");
                    }}
                  >
                    + 添加
                  </Button>
                </div>
              </div>
            </div>

            <div className="space-y-3 pt-4 border-t border-zinc-200 dark:border-white/10">
              <Label className="text-zinc-700 dark:text-zinc-300">
                监控级别 (多周期 MTF)
              </Label>
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap gap-2 items-center">
                  {["15m", "1h", "4h", "1d"].map((interval) => {
                    const isSelected = Array.isArray(config.monitor_intervals)
                      ? config.monitor_intervals.includes(interval)
                      : Object.keys(config.monitor_intervals).includes(interval);
                    return (
                      <Badge
                        key={interval}
                        onClick={() => {
                          let newIntervals;
                          if (Array.isArray(config.monitor_intervals)) {
                            if (isSelected && config.monitor_intervals.length === 1) {
                              toast.error("至少保留一个监控级别");
                              return;
                            }
                            newIntervals = isSelected
                              ? config.monitor_intervals.filter((i: string) => i !== interval)
                              : [...config.monitor_intervals, interval];
                          } else {
                            const keys = Object.keys(config.monitor_intervals);
                            if (isSelected && keys.length === 1) {
                              toast.error("至少保留一个监控级别");
                              return;
                            }
                            newIntervals = { ...(config.monitor_intervals as any) };
                            if (isSelected) {
                              delete newIntervals[interval];
                            } else {
                              newIntervals[interval] = { use_trend_filter: true };
                            }
                          }
                          onConfigChange("monitor_intervals", newIntervals);
                        }}
                        className={`cursor-pointer px-4 py-1.5 text-sm font-medium transition-all shadow-sm ${
                          isSelected
                            ? "bg-blue-500 text-white hover:bg-blue-600 border-transparent shadow-md"
                            : "bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-700"
                        }`}
                        variant={isSelected ? "default" : "outline"}
                      >
                        {interval} {isSelected && "✓"}
                      </Badge>
                    );
                  })}
                </div>

                {!Array.isArray(config.monitor_intervals) &&
                  Object.keys(config.monitor_intervals).length > 0 && (
                    <div className="mt-3 space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl border border-zinc-200 dark:border-white/5">
                      <p className="text-xs font-medium text-zinc-500 mb-2 uppercase">
                        趋势过滤设置
                      </p>
                      {Object.entries(config.monitor_intervals).map(
                        ([interval, intervalCfg]: [string, any]) => (
                          <div
                            key={interval}
                            className="flex justify-between items-center"
                          >
                            <div className="flex items-center gap-2">
                              <Badge
                                variant="outline"
                                className="w-12 justify-center text-xs"
                              >
                                {interval}
                              </Badge>
                              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                                参考大级别趋势
                              </span>
                            </div>
                            <Switch
                              checked={intervalCfg.use_trend_filter}
                              onCheckedChange={(checked) => {
                                const newIntervals = {
                                  ...config.monitor_intervals,
                                  [interval]: {
                                    ...intervalCfg,
                                    use_trend_filter: checked,
                                  },
                                };
                                onConfigChange("monitor_intervals", newIntervals);
                                fetch("http://localhost:8000/api/config", {
                                  method: "PUT",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({
                                    monitor_intervals: newIntervals,
                                  }),
                                })
                                  .then((res) => {
                                    if (res.ok)
                                      toast.success(
                                        `${interval} 趋势过滤状态已保存`
                                      );
                                  })
                                  .catch(() => toast.error("配置保存失败"));
                              }}
                            />
                          </div>
                        )
                      )}
                    </div>
                  )}
              </div>
              <p className="text-xs text-zinc-500 mt-2 bg-blue-500/5 p-3 rounded-xl border border-blue-500/10 dark:border-blue-500/20">
                <strong className="text-blue-600 dark:text-blue-400">
                  MTF 趋势过滤说明:
                </strong>
                <br />
                • 15m 信号必须符合 1h 级别的大趋势方向。
                <br />
                • 1h 信号必须符合 4h 级别的大趋势方向。
                <br />• 4h 及 1d 信号独立判断，无上级约束。
              </p>
            </div>

            <div className="space-y-4 pt-4 border-t border-zinc-200 dark:border-white/10">
              <Label className="text-zinc-700 dark:text-zinc-300">
                币安 API Key (仅供读取)
              </Label>
              <Input
                value={config.binance_api_key}
                onChange={(e) =>
                  onConfigChange("binance_api_key", e.target.value)
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white placeholder:text-zinc-400 font-mono"
                placeholder={
                  config.has_binance_key
                    ? "******** (目前密钥已配置成功)"
                    : "输入币安 API Key"
                }
              />

              <Label className="text-zinc-700 dark:text-zinc-300">
                币安 API Secret
              </Label>
              <Input
                type="password"
                value={config.binance_api_secret}
                onChange={(e) =>
                  onConfigChange("binance_api_secret", e.target.value)
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white placeholder:text-zinc-400 font-mono"
                placeholder={
                  config.has_binance_key
                    ? "******** (加密隐藏)"
                    : "输入币安 API Secret"
                }
              />
              <p className="text-xs text-zinc-500 mt-2">
                安全提示：密钥将在后台强制加密存储，请确保该秘钥仅开启只读权限，严禁开启交易与提现权限。
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Pinbar Strategy Settings */}
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
                  {(Number(config.body_max_ratio) * 100).toFixed(0)}%
                </span>
              </div>
              <Slider
                value={[Number(config.body_max_ratio) * 100]}
                max={100}
                step={1}
                onValueChange={(val) =>
                  onConfigChange("body_max_ratio", val[0] / 100)
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
                  {Number(config.shadow_min_ratio).toFixed(1)}x
                </span>
              </div>
              <Slider
                value={[Number(config.shadow_min_ratio) * 10]}
                max={50}
                step={1}
                onValueChange={(val) =>
                  onConfigChange("shadow_min_ratio", val[0] / 10)
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
                  {Number(config.volatility_atr_multiplier).toFixed(1)}x
                </span>
              </div>
              <Slider
                value={[Number(config.volatility_atr_multiplier) * 10]}
                max={50}
                step={1}
                onValueChange={(val) =>
                  onConfigChange("volatility_atr_multiplier", val[0] / 10)
                }
                className="py-4"
              />
              <p className="text-xs text-zinc-500">
                K 线总长度与平均 ATR 的比值。用于过滤极小波动。
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Risk Limits */}
        <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
              <ShieldCheck className="w-5 h-5" /> 风控参数
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-zinc-700 dark:text-zinc-300">
                  单笔风险度 (%)
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  value={config.risk_pct}
                  onChange={(e) => onConfigChange("risk_pct", e.target.value)}
                  onBlur={(e) =>
                    onConfigChange(
                      "risk_pct",
                      Number(
                        parseFloat(e.target.value || "0").toFixed(2)
                      )
                    )
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
                  value={config.max_sl_dist}
                  onChange={(e) =>
                    onConfigChange("max_sl_dist", e.target.value)
                  }
                  onBlur={(e) =>
                    onConfigChange(
                      "max_sl_dist",
                      Number(
                        parseFloat(e.target.value || "0").toFixed(2)
                      )
                    )
                  }
                  className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white font-mono"
                />
              </div>
              <div className="space-y-2 col-span-2">
                <Label className="text-zinc-700 dark:text-zinc-300">
                  最大杠杆倍数 (x)
                </Label>
                <Input
                  type="number"
                  value={config.max_leverage}
                  onChange={(e) =>
                    onConfigChange("max_leverage", Number(e.target.value))
                  }
                  className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white"
                />
              </div>
            </div>
            <div className="flex items-center justify-between pt-4 border-t border-zinc-200 dark:border-white/10 mt-4">
              <div>
                <Label className="text-base text-zinc-900 dark:text-zinc-200 flex items-center gap-2">
                  全局推送开关
                  <Badge
                    variant="outline"
                    className="text-[10px] h-5 px-1.5 bg-blue-500/10 text-blue-500 border-blue-500/20"
                  >
                    生效中
                  </Badge>
                </Label>
                <p className="text-xs text-zinc-500 mt-1">
                  控制所有告警通道 (飞书/企微) 的总闸
                </p>
              </div>
              <Switch
                checked={config.global_push_enabled}
                onCheckedChange={(c) => onConfigChange("global_push_enabled", c)}
              />
            </div>
            <div className="flex items-center justify-between pt-4">
              <div>
                <Label className="text-base text-zinc-400 dark:text-zinc-500 flex items-center gap-2">
                  自动下单交易
                  <Badge
                    variant="outline"
                    className="text-[10px] h-5 px-1.5 bg-zinc-500/10 text-zinc-500 border-zinc-500/20"
                  >
                    仅监测模式
                  </Badge>
                </Label>
                <p className="text-xs text-zinc-500 mt-1">
                  当前系统仅作为信号监测工具，自动交易已禁用
                </p>
              </div>
              <Switch checked={false} disabled />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Column 2 */}
      <div className="space-y-6">
        {/* Scoring Engine Weights */}
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
                  {config.w_shape}%
                </span>
              </div>
              <Slider
                value={[config.w_shape]}
                onValueChange={(v) => onWeightAutoBalance("w_shape", v)}
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
                  {config.w_trend}%
                </span>
              </div>
              <Slider
                value={[config.w_trend]}
                onValueChange={(v) => onWeightAutoBalance("w_trend", v)}
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
                  {config.w_vol}%
                </span>
              </div>
              <Slider
                value={[config.w_vol]}
                onValueChange={(v) => onWeightAutoBalance("w_vol", v)}
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

        {/* Notifications */}
        <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
          <CardHeader>
            <CardTitle className="text-lg text-zinc-900 dark:text-white">
              告警与通知
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-zinc-900 dark:text-zinc-300">
                  飞书机器人推送
                </Label>
                <Switch
                  checked={config.feishu_enabled}
                  onCheckedChange={(c) => onConfigChange("feishu_enabled", c)}
                />
              </div>
              <div className="relative pb-4 border-b border-zinc-200 dark:border-white/5">
                <Input
                  type={showSecret ? "text" : "password"}
                  value={config.feishu_secret}
                  onChange={(e) =>
                    onConfigChange("feishu_secret", e.target.value)
                  }
                  className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 pr-10 text-zinc-900 dark:text-white"
                  placeholder={
                    config.has_secret
                      ? "•••••••••••••••• (已保存)"
                      : "输入飞书 Webhook 密钥..."
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                >
                  {showSecret ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>

              <div className="flex items-center justify-between pt-2">
                <Label className="text-zinc-900 dark:text-zinc-300">
                  企业微信推送
                </Label>
                <Switch
                  checked={config.wecom_enabled}
                  onCheckedChange={(c) => onConfigChange("wecom_enabled", c)}
                />
              </div>
              <div className="relative pb-2">
                <Input
                  type={showWecomSecret ? "text" : "password"}
                  value={config.wecom_secret}
                  onChange={(e) => onConfigChange("wecom_secret", e.target.value)}
                  className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 pr-10 text-zinc-900 dark:text-white"
                  placeholder={
                    config.has_wecom_secret
                      ? "•••••••••••••••• (已保存)"
                      : "输入企微 Webhook 密钥..."
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowWecomSecret(!showWecomSecret)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 mb-1"
                >
                  {showWecomSecret ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Submit Button */}
        <Button
          type="submit"
          disabled={saving}
          className="w-full h-14 rounded-2xl bg-zinc-900 text-white dark:bg-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all text-base font-semibold shadow-xl shadow-black/5 dark:shadow-white/5"
        >
          {saving ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> 配置正在后台部署...
            </>
          ) : (
            "保存并生效配置"
          )}
        </Button>
      </div>
    </form>
  );
}
