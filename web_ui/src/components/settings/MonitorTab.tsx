import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Clock, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface MonitorTabProps {
  initialConfig: any;
  onConfigChange: (field: string, value: any) => void;
}

export function MonitorTab({ initialConfig, onConfigChange }: MonitorTabProps) {
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    monitor_intervals: ["15m", "1h", "4h", "1d"] as string[] | Record<string, any>,
    symbols: "BTCUSDT,ETHUSDT",
  });

  useEffect(() => {
    setFormData({
      monitor_intervals: initialConfig.monitor_intervals || ["15m", "1h", "4h", "1d"],
      symbols: initialConfig.symbols || "BTCUSDT,ETHUSDT",
    });
  }, [initialConfig]);

  const handleSave = async () => {
    setLoading(true);
    try {
      // 将数组格式转换为后端期望的对象格式 { "15m": { use_trend_filter: false }, ... }
      const monitorIntervalsPayload: Record<string, any> = {};
      const intervals = formData.monitor_intervals;

      if (Array.isArray(intervals)) {
        for (const interval of intervals) {
          monitorIntervalsPayload[interval] = { use_trend_filter: false };
        }
      } else {
        Object.assign(monitorIntervalsPayload, intervals);
      }

      const payload: any = {
        monitor_intervals: monitorIntervalsPayload,
      };

      if (formData.symbols) {
        payload.active_symbols = formData.symbols
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
      }

      const res = await fetch("http://localhost:8000/api/config/monitor", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        toast.success("监控配置已保存", {
          description: "监控级别和趋势过滤设置已更新。",
          className: "bg-zinc-900 border border-white/10 text-zinc-100",
        });
        onConfigChange("monitor_intervals", formData.monitor_intervals);
        onConfigChange("symbols", formData.symbols);
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

  const toggleInterval = (interval: string) => {
    setFormData((prev) => {
      const current = prev.monitor_intervals;

      if (Array.isArray(current)) {
        if (current.includes(interval) && current.length === 1) {
          toast.error("至少保留一个监控级别");
          return prev;
        }
        const newIntervals = current.includes(interval)
          ? current.filter((i) => i !== interval)
          : [...current, interval];
        return { ...prev, monitor_intervals: newIntervals };
      } else {
        const keys = Object.keys(current);
        if (keys.includes(interval) && keys.length === 1) {
          toast.error("至少保留一个监控级别");
          return prev;
        }
        const newIntervals: Record<string, any> = { ...current };
        if (keys.includes(interval)) {
          delete newIntervals[interval];
        } else {
          newIntervals[interval] = { use_trend_filter: true };
        }
        return { ...prev, monitor_intervals: newIntervals };
      }
    });
  };

  const toggleTrendFilter = (interval: string, enabled: boolean) => {
    setFormData((prev) => {
      if (!Array.isArray(prev.monitor_intervals)) {
        const newIntervals = {
          ...prev.monitor_intervals,
          [interval]: {
            ...prev.monitor_intervals[interval],
            use_trend_filter: enabled,
          },
        };
        return { ...prev, monitor_intervals: newIntervals };
      }
      return prev;
    });
  };

  const isIntervalSelected = (interval: string) => {
    const current = formData.monitor_intervals;
    if (Array.isArray(current)) {
      return current.includes(interval);
    }
    return Object.keys(current).includes(interval);
  };

  const addSymbol = (symbol: string) => {
    if (symbol && !formData.symbols.split(",").map((s) => s.trim()).includes(symbol)) {
      const newSymbols = formData.symbols
        ? formData.symbols + "," + symbol
        : symbol;
      setFormData((prev) => ({ ...prev, symbols: newSymbols }));
    }
  };

  const removeSymbol = (symbolToRemove: string) => {
    const symbols = formData.symbols
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s !== symbolToRemove);
    setFormData((prev) => ({ ...prev, symbols: symbols.join(",") }));
  };

  return (
    <div className="space-y-6">
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
            <Clock className="w-5 h-5" /> 监控配置
          </CardTitle>
          <CardDescription>配置多周期监控级别、趋势过滤和监控币种</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <Label className="text-zinc-700 dark:text-zinc-300">
              监控币种
            </Label>
            <div className="flex flex-wrap gap-2 items-center">
              {formData.symbols
                .split(",")
                .filter(Boolean)
                .map((sym) => (
                  <Badge
                    key={sym}
                    onClick={() => removeSymbol(sym)}
                    className="cursor-pointer px-3 py-1.5 text-sm font-medium transition-all bg-blue-500 text-white hover:bg-blue-600 border-transparent shadow-md"
                    variant="outline"
                  >
                    {sym} ✕
                  </Badge>
                ))}
              <div className="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-800/50 rounded-full pr-1">
                <Input
                  placeholder="新币种 (如 SOLUSDT)"
                  className="w-32 h-8 text-xs border-none bg-transparent focus-visible:ring-0 px-3 shadow-none"
                  onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addSymbol(e.currentTarget.value.trim().toUpperCase());
                      e.currentTarget.value = "";
                    }
                  }}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-3 text-xs rounded-full bg-white dark:bg-zinc-700 shadow-sm hover:text-blue-500"
                  onClick={(e) => {
                    e.preventDefault();
                    const input = e.currentTarget.parentElement?.querySelector("input");
                    if (input?.value) {
                      addSymbol(input.value.trim().toUpperCase());
                      input.value = "";
                    }
                  }}
                >
                  + 添加
                </Button>
              </div>
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t border-zinc-200 dark:border-white/10">
            <Label className="text-zinc-700 dark:text-zinc-300">
              监控级别 (多周期 MTF)
            </Label>
            <div className="flex flex-wrap gap-2 items-center">
              {["15m", "1h", "4h", "1d"].map((interval) => {
                const isSelected = isIntervalSelected(interval);
                return (
                  <Badge
                    key={interval}
                    onClick={() => toggleInterval(interval)}
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

            {!Array.isArray(formData.monitor_intervals) &&
              Object.keys(formData.monitor_intervals).length > 0 && (
                <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl border border-zinc-200 dark:border-white/5">
                  <p className="text-xs font-medium text-zinc-500 mb-2 uppercase">
                    趋势过滤设置
                  </p>
                  {Object.entries(formData.monitor_intervals).map(
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
                          onCheckedChange={(checked) =>
                            toggleTrendFilter(interval, checked)
                          }
                        />
                      </div>
                    )
                  )}
                </div>
              )}

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
              "保存监控配置"
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
