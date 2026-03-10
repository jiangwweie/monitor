/**
 * Backtest Candlestick Chart
 * 使用 Lightweight Charts 渲染行情 K 线图 + 交易点位标记
 */

import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";

import type { KlineBar } from "@/services/backtest_api";

// --- Helpers ---
function computeEMA(data: { time: number; close: number }[], period: number) {
  const emaData: { time: UTCTimestamp; value: number }[] = [];
  if (data.length === 0) return emaData;
  const multiplier = 2 / (period + 1);
  let ema = data[0].close;
  for (let i = 0; i < data.length; i++) {
    if (i === 0) {
      ema = data[i].close;
    } else {
      ema = (data[i].close - ema) * multiplier + ema;
    }
    if (i >= period - 1) {
      emaData.push({ time: data[i].time as UTCTimestamp, value: ema });
    }
  }
  return emaData;
}

const toBeijing = (ts: number) => {
  const d = new Date((ts + 8 * 3600) * 1000);
  const Y = d.getUTCFullYear();
  const M = String(d.getUTCMonth() + 1).padStart(2, "0");
  const D = String(d.getUTCDate()).padStart(2, "0");
  const h = String(d.getUTCHours()).padStart(2, "0");
  const m = String(d.getUTCMinutes()).padStart(2, "0");
  return `${Y}-${M}-${D} ${h}:${m}`;
};

interface TradeLog {
  action?: number;
  action_name?: string;
  timestamp: number;
  kline_index?: number;  // K 线索引，用于精确定位
  price?: number;
  direction?: string;
}

interface BacktestCandlestickChartProps {
  klineData: KlineBar[];
  tradeLogs?: TradeLog[];
}

export function BacktestCandlestickChart({
  klineData,
  tradeLogs = [],
}: BacktestCandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;
    if (!klineData || klineData.length === 0) return;

    // 创建图表 (极简深色风格)
    const chart = createChart(chartContainerRef.current, {
      localization: {
        timeFormatter: toBeijing,
      },
      layout: {
        background: { type: 'solid' as const, color: 'transparent' },
        textColor: '#71717a',
        fontSize: 11,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: 'rgba(255,255,255,0.04)' },
      },
      crosshair: {
        vertLine: { color: 'rgba(59,130,246,0.3)', labelBackgroundColor: '#3b82f6' },
        horzLine: { color: 'rgba(59,130,246,0.3)', labelBackgroundColor: '#3b82f6' },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.06)',
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: toBeijing,
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.06)',
      },
      handleScroll: true,
      handleScale: true,
    });

    chartRef.current = chart;

    // 创建 K 线系列 (苹果极简翠绿/大红风格)
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e80',
      wickDownColor: '#ef444480',
    });

    seriesRef.current = candlestickSeries;

    // 转换数据格式：timestamp 毫秒转秒
    const chartData = klineData.map((bar) => ({
      time: (bar.timestamp / 1000) as UTCTimestamp,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));

    candlestickSeries.setData(chartData);

    // EMA60 辅助线
    const ema60Data = computeEMA(chartData, 60);
    if (ema60Data.length > 0) {
      const emaSeries = chart.addSeries(LineSeries, {
        color: '#f59e0b',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      emaSeries.setData(ema60Data);
    }

    // 自适应容器大小
    const resizeObserver = new ResizeObserver((entries) => {
      const { width, height } = entries[0]?.contentRect || { width: 0, height: 0 };
      chart.applyOptions({
        width: Math.floor(width),
        height: Math.floor(height),
      });
    });

    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [klineData]);

  // 交易标记
  useEffect(() => {
    if (!chartRef.current || !seriesRef.current) return;
    if (!tradeLogs || tradeLogs.length === 0) return;
    if (!klineData || klineData.length === 0) return;

    // 构建标记数组
    const markers = tradeLogs
      .filter((trade) => {
        // 必须有 action_name 且有效
        if (!trade.action_name) return false;
        // 必须有有效的时间戳
        if (!trade.timestamp || trade.timestamp <= 0) return false;
        return true;
      })
      .map((trade) => {
        // 根据 action_name 判断类型（防御性检查：如果未定义则跳过）
        if (!trade.action_name) return null;

        const actionName = trade.action_name.toUpperCase();
        const isOpen = actionName.includes('OPEN');
        const isLong = actionName.includes('LONG');
        const isShort = actionName.includes('SHORT');

        // 确定箭头位置和颜色
        let position: 'aboveBar' | 'belowBar';
        let color: string;
        let shape: 'arrowUp' | 'arrowDown' | 'circle' | 'text';
        let text: string;

        if (isOpen && isLong) {
          // OPEN_LONG: 绿色向上箭头，belowBar
          position = 'belowBar';
          color = '#10b981';
          shape = 'arrowUp';
          text = '多';
        } else if (isOpen && isShort) {
          // OPEN_SHORT: 红色向下箭头，aboveBar
          position = 'aboveBar';
          color = '#f43f5e';
          shape = 'arrowDown';
          text = '空';
        } else if (actionName.includes('CLOSE_LONG')) {
          // CLOSE_LONG: 橙色圆点，aboveBar
          position = 'aboveBar';
          color = '#f97316';
          shape = 'circle';
          text = '平多';
        } else if (actionName.includes('CLOSE_SHORT')) {
          // CLOSE_SHORT: 橙色圆点，belowBar
          position = 'belowBar';
          color = '#f97316';
          shape = 'circle';
          text = '平空';
        } else {
          // 未知类型：使用中性标记
          position = 'aboveBar';
          color = '#71717a';
          shape = 'circle';
          text = '';
        }

        // 确定时间：优先使用 kline_index，如果无效则使用 timestamp
        let timeValue: any;
        if (trade.kline_index !== undefined && trade.kline_index >= 0 && trade.kline_index < klineData.length) {
          timeValue = (klineData[trade.kline_index].timestamp / 1000) as any;
        } else {
          timeValue = (trade.timestamp / 1000) as any;
        }

        return {
          time: timeValue,
          position,
          color,
          shape,
          text,
          size: 2,
        };
      })
      .filter(Boolean); // 过滤掉 null 值

    // 严格按 time 去重（保留同一时刻最后的操作）
    const uniqueMarkersMap = new Map();
    markers.forEach(m => {
      uniqueMarkersMap.set(m.time, m);
    });
    const uniqueMarkers: any[] = Array.from(uniqueMarkersMap.values());

    // 按 time 升序排序
    uniqueMarkers.sort((a, b) => {
      const timeA = typeof a.time === 'number' ? a.time : 0;
      const timeB = typeof b.time === 'number' ? b.time : 0;
      return timeA - timeB;
    });

    // 只有有效标记才设置
    if (uniqueMarkers.length > 0) {
      try {
        seriesRef.current?.setMarkers?.(uniqueMarkers);
      } catch (e) {
        console.warn('设置 K 线标记失败:', e);
      }
    }
  }, [tradeLogs, klineData]);

  return (
    <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden">
      <CardHeader className="pb-2 border-b border-zinc-200 dark:border-white/5">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-500" />
          <CardTitle className="text-zinc-900 dark:text-zinc-200">
            行情 K 线与交易点位
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div
          ref={chartContainerRef}
          className="w-full h-[400px]"
        />
      </CardContent>
    </Card>
  );
}
