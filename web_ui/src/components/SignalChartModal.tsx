import { useRef, useEffect, useState, useCallback } from "react";
import { createChart, createSeriesMarkers, CandlestickSeries, LineSeries, type IChartApi, type UTCTimestamp } from "lightweight-charts";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Loader2, Radar, TrendingUp } from "lucide-react";

/**
 * 计算 EMA (指数移动平均线)
 * 从 klines 的 close 序列中计算 EMA60
 */
function computeEMA(klines: { time: number; close: number }[], period: number) {
    const emaData: { time: UTCTimestamp; value: number }[] = [];
    if (klines.length === 0) return emaData;

    const multiplier = 2 / (period + 1);
    let ema = klines[0].close;

    for (let i = 0; i < klines.length; i++) {
        if (i === 0) {
            ema = klines[i].close;
        } else {
            ema = (klines[i].close - ema) * multiplier + ema;
        }
        // 只在有足够数据后才输出 (避免初始噪音)
        if (i >= period - 1) {
            emaData.push({ time: klines[i].time as UTCTimestamp, value: ema });
        }
    }
    return emaData;
}

interface SignalChartModalProps {
    signal: any;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function SignalChartModal({ signal, open, onOpenChange }: SignalChartModalProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const [chartLoading, setChartLoading] = useState(false);
    const [chartError, setChartError] = useState<string | null>(null);

    const initChart = useCallback(async () => {
        if (!signal || !chartContainerRef.current) return;

        setChartLoading(true);
        setChartError(null);

        try {
            const interval = signal.interval || "1h";
            const symbol = signal.symbol || "BTCUSDT";

            const res = await fetch(
                `http://localhost:8000/api/chart/data/${symbol}?interval=${interval}&limit=500`
            );

            if (!res.ok) {
                throw new Error(`API 响应异常: ${res.status}`);
            }

            const data = await res.json();
            const klines = data.klines || [];
            const markers = data.markers || [];

            if (klines.length === 0) {
                setChartError("无可用 K 线数据");
                setChartLoading(false);
                return;
            }

            // 清理旧图表
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }

            // 创建图表 (极简深色风格)
            const toBeijing = (ts: number) => {
                const d = new Date((ts + 8 * 3600) * 1000);
                const Y = d.getUTCFullYear();
                const M = String(d.getUTCMonth() + 1).padStart(2, "0");
                const D = String(d.getUTCDate()).padStart(2, "0");
                const h = String(d.getUTCHours()).padStart(2, "0");
                const m = String(d.getUTCMinutes()).padStart(2, "0");
                return `${Y}-${M}-${D} ${h}:${m}`;
            };

            const chart = createChart(chartContainerRef.current, {
                width: chartContainerRef.current.clientWidth,
                height: 360,
                localization: {
                    timeFormatter: toBeijing,
                },
                layout: {
                    background: { color: "transparent" },
                    textColor: "#71717a",
                    fontSize: 11,
                },
                grid: {
                    vertLines: { visible: false },
                    horzLines: { color: "rgba(255,255,255,0.04)" },
                },
                crosshair: {
                    vertLine: { color: "rgba(59,130,246,0.3)", labelBackgroundColor: "#3b82f6" },
                    horzLine: { color: "rgba(59,130,246,0.3)", labelBackgroundColor: "#3b82f6" },
                },
                timeScale: {
                    borderColor: "rgba(255,255,255,0.06)",
                    timeVisible: true,
                    secondsVisible: false,
                    tickMarkFormatter: toBeijing,
                },
                rightPriceScale: {
                    borderColor: "rgba(255,255,255,0.06)",
                },
            });

            chartRef.current = chart;

            // 蜡烛图系列
            const candleSeries = chart.addSeries(CandlestickSeries, {
                upColor: "#22c55e",
                downColor: "#ef4444",
                borderUpColor: "#22c55e",
                borderDownColor: "#ef4444",
                wickUpColor: "#22c55e80",
                wickDownColor: "#ef444480",
            });

            const typedKlines = klines.map((k: any) => ({
                time: k.time as UTCTimestamp,
                open: k.open,
                high: k.high,
                low: k.low,
                close: k.close,
            }));
            candleSeries.setData(typedKlines);

            // 信号标记
            if (markers.length > 0) {
                const tvMarkers = markers.map((m: any) => ({
                    time: m.time as UTCTimestamp,
                    position: m.position,
                    color: m.color,
                    shape: m.shape,
                    text: m.text,
                }));
                createSeriesMarkers(candleSeries, tvMarkers);
            }

            // EMA60 趋势线
            const ema60Data = computeEMA(klines, 60);
            if (ema60Data.length > 0) {
                const emaSeries = chart.addSeries(LineSeries, {
                    color: "#f59e0b",
                    lineWidth: 2,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });
                emaSeries.setData(ema60Data);
            }

            // 自适应缩放 — 聚焦到信号所在的时间区域
            const signalTimeSec = Math.floor(signal.timestamp / 1000);
            const intervalMs: Record<string, number> = {
                "1m": 60000, "5m": 300000, "15m": 900000, "30m": 1800000,
                "1h": 3600000, "4h": 14400000, "1d": 86400000,
            };
            const ivlMs = intervalMs[interval] || 3600000;
            const barsToShow = 80;
            const rangeFrom = signalTimeSec - (barsToShow * ivlMs) / 1000;
            const rangeTo = signalTimeSec + (20 * ivlMs) / 1000;

            chart.timeScale().setVisibleRange({
                from: rangeFrom as any,
                to: rangeTo as any,
            });

            // 响应式
            const handleResize = () => {
                if (chartContainerRef.current && chartRef.current) {
                    chartRef.current.applyOptions({
                        width: chartContainerRef.current.clientWidth,
                    });
                }
            };
            const ro = new ResizeObserver(handleResize);
            ro.observe(chartContainerRef.current);

            // 存储 observer 以便清理
            (chartContainerRef.current as any)._resizeObserver = ro;

        } catch (err: any) {
            setChartError(err.message || "图表加载失败");
        } finally {
            setChartLoading(false);
        }
    }, [signal]);

    // 弹窗打开时初始化图表
    useEffect(() => {
        if (open && signal) {
            // 延迟一帧等 DOM 就绪
            const timer = setTimeout(initChart, 50);
            return () => clearTimeout(timer);
        }
        return () => {
            // 清理
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
            if (chartContainerRef.current) {
                const ro = (chartContainerRef.current as any)?._resizeObserver;
                if (ro) ro.disconnect();
            }
        };
    }, [open, signal, initChart]);

    if (!signal) return null;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl bg-white/95 dark:bg-zinc-900/95 backdrop-blur-2xl border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-zinc-100 rounded-3xl p-6 shadow-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Radar className="w-5 h-5 text-blue-500" />
                        指标详情 ({signal.symbol})
                        {signal.interval && <Badge variant="secondary" className="text-xs ml-1">{signal.interval}</Badge>}
                        {signal.source === "history_scan" && (
                            <Badge variant="outline" className="text-xs bg-violet-500/10 text-violet-500 border-violet-500/20">历史</Badge>
                        )}
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-2 max-h-[80vh] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-zinc-300 dark:scrollbar-thumb-zinc-700">
                    {/* ===== K 线图表区域 ===== */}
                    <div className="rounded-2xl overflow-hidden bg-zinc-50 dark:bg-black/30 border border-zinc-200/50 dark:border-white/5">
                        {/* 图表标题栏 */}
                        <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-200/50 dark:border-white/5">
                            <div className="flex items-center gap-2 text-xs text-zinc-500">
                                <TrendingUp className="w-3.5 h-3.5" />
                                <span>{signal.symbol} · {signal.interval || "1h"} · K线图表</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-2 h-0.5 bg-amber-500 rounded-full inline-block" />
                                <span className="text-[10px] text-zinc-500">EMA60</span>
                            </div>
                        </div>

                        {/* 图表容器 */}
                        <div className="relative" style={{ height: 360 }}>
                            {chartLoading && (
                                <div className="absolute inset-0 flex items-center justify-center z-10 bg-zinc-50/80 dark:bg-black/40 backdrop-blur-sm">
                                    <div className="flex flex-col items-center gap-3">
                                        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                                        <span className="text-xs text-zinc-500">正在加载 K 线数据...</span>
                                    </div>
                                </div>
                            )}
                            {chartError && (
                                <div className="absolute inset-0 flex items-center justify-center z-10">
                                    <span className="text-sm text-zinc-500">{chartError}</span>
                                </div>
                            )}
                            <div ref={chartContainerRef} className="w-full h-full" />
                        </div>
                    </div>

                    {/* ===== 评分 + 方向卡片 ===== */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-zinc-50 dark:bg-black/20 p-3 rounded-2xl">
                            <p className="text-xs text-zinc-500 mb-1">综合评分 (Score)</p>
                            <p className="font-mono text-xl font-bold">{signal.score}</p>
                        </div>
                        <div className="bg-zinc-50 dark:bg-black/20 p-3 rounded-2xl">
                            <p className="text-xs text-zinc-500 mb-1">操作方向 (Direction)</p>
                            <p className={`font-medium ${signal.direction === "LONG" ? "text-emerald-500" : "text-rose-500"}`}>
                                {signal.direction === "LONG" ? "做多 (LONG)" : "做空 (SHORT)"}
                            </p>
                        </div>
                    </div>

                    {/* ===== 价格与风控参数 ===== */}
                    <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl">
                        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-2">价格与风险控制参数</p>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">建议入场价 (Entry)</span>
                            <span className="font-mono text-zinc-900 dark:text-zinc-100">${Number(signal.entry_price || signal.price || 0).toFixed(4)}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">止损价 (Stop Loss)</span>
                            <span className="font-mono text-rose-500">${Number(signal.stop_loss || 0).toFixed(4)}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">第一止盈价 (TP1)</span>
                            <span className="font-mono text-emerald-500">${Number(signal.take_profit_1 || 0).toFixed(4)}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">止损距离比例 (SL Dist)</span>
                            <span className="font-mono text-zinc-900 dark:text-zinc-100">{(Number(signal.sl_distance_pct || 0) * 100).toFixed(2)}%</span>
                        </div>
                    </div>

                    {/* ===== 策略指标详情 ===== */}
                    <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl">
                        <div className="flex justify-between items-center text-sm pt-2">
                            <span className="text-zinc-500 font-semibold text-amber-600 dark:text-amber-500">MTF 趋势校验</span>
                            <span className="font-medium text-amber-600 dark:text-amber-500">已通过上级周期方向校验</span>
                        </div>
                        <div className="w-full h-px bg-zinc-200 dark:bg-zinc-800 my-2" />
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">信号触发原因 (Reason)</span>
                            <span className="font-medium text-blue-500">{signal.reason || "Pinbar+EMA60"}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">形态完美度 (Shape)</span>
                            <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(signal.score_details?.shape ?? 0).toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">趋势顺应度 (Trend)</span>
                            <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(signal.score_details?.trend ?? 0).toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">波动率健康度 (Vol)</span>
                            <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(signal.score_details?.vol ?? 0).toFixed(1)}</span>
                        </div>
                        <div className="w-full h-px bg-zinc-200 dark:bg-zinc-800 my-2" />
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">引线比例 (Shadow Ratio)</span>
                            <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(signal.shadow_ratio || 0).toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">EMA 距离 (EMA Dist)</span>
                            <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(signal.ema_distance || 0).toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-zinc-500">真实波动幅度 (ATR)</span>
                            <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(signal.volatility_atr || 0).toFixed(2)}</span>
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
