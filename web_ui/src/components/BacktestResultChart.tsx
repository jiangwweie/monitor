/**
 * Backtest Result Chart
 * 使用 Lightweight Charts 渲染资金权益曲线
 */

import { useEffect, useRef, useState } from "react";
import { createChart, AreaSeries } from "lightweight-charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity } from "lucide-react";

interface EquityPoint {
  timestamp: number;
  balance: number;
  equity?: number;
  pnl?: number;
  utilization?: number;
}

interface TradeLog {
  action?: number;
  action_name?: string;
  timestamp: number;
  datetime?: string;
  price: number;
  amount: number;
  symbol?: string;
  profit?: number;
  runBalance?: number;
}

interface BacktestResultChartProps {
  equityCurve: EquityPoint[];
  tradeLogs?: TradeLog[];
  initialBalance: number;
}

export function BacktestResultChart({
  equityCurve,
  tradeLogs = [],
  initialBalance,
}: BacktestResultChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const [hoveredData, setHoveredData] = useState<{
    date: string;
    balance: number;
    profit: number;
  } | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;
    if (!equityCurve || equityCurve.length === 0) return;

    // 创建图表
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: 'solid' as const, color: 'transparent' },
        textColor: '#a1a1aa',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.05)' },
        horzLines: { color: 'rgba(255,255,255,0.05)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.1)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.1)',
        timeVisible: true,
        secondsVisible: false,
        fontSize: 12,
      },
      crosshair: {
        vertLine: {
          color: 'rgba(59, 130, 246, 0.5)',
          style: 3,
          labelBackgroundColor: '#18181b',
        },
        horzLine: {
          color: 'rgba(59, 130, 246, 0.5)',
          style: 3,
          labelBackgroundColor: '#18181b',
        },
      },
      handleScroll: true,
      handleScale: true,
    });

    chartRef.current = chart;

    // ==========================================
    // 防御性数据处理：Y 轴防沉底机制
    // ==========================================
    // 1. 计算初始余额（如果传入为 0 或无效，则使用 equityCurve 的第一个有效 pnl 值）
    const safeInitialBalance = (initialBalance > 0 && isFinite(initialBalance))
      ? initialBalance
      : 0;

    // 3. 检查数据是否为"绝对平"的 0 线（所有值相同）
    const chartData = equityCurve.map((point) => {
      // 优先级：pnl > balance > 0
      let value: number;
      if (point.pnl !== undefined && point.pnl !== null && isFinite(point.pnl)) {
        value = point.pnl;
      } else if (point.balance !== undefined && point.balance !== null && isFinite(point.balance)) {
        // Fallback: 如果 balance 有效，使用 initialBalance + balance
        value = (safeInitialBalance > 0 ? safeInitialBalance : 0) + point.balance;
      } else {
        value = 0;
      }
      return {
        time: (point.timestamp / 1000) as any,
        value: value,
      };
    });

    // 4. 等间距过滤/去重：lightweight-charts 严格要求 time 升序且无重复
    const uniqueTimeMap = new Map();
    chartData.forEach(d => {
      uniqueTimeMap.set(d.time, d);
    });

    // 生成最终的升序无重复数据，并检测全平情况
    const finalChartData = Array.from(uniqueTimeMap.values()).sort((a, b) => (a.time as number) - (b.time as number));

    const allValuesSame = finalChartData.length > 0 && finalChartData.every(d => d.value === finalChartData[0]?.value);
    if (allValuesSame && finalChartData.length > 0) {
      // 给最后一个点添加微小增量，让图表能正常渲染
      finalChartData[finalChartData.length - 1].value += 0.01;
    }

    // 创建面积图系列 (v5 API)
    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: '#10b981',
      topColor: 'rgba(16, 185, 129, 0.3)',
      bottomColor: 'rgba(16, 185, 129, 0.05)',
      lineWidth: 2,
      lineStyle: 0 /* LineStyle.Solid */,
      areaBaseValue: { type: 'price', price: 0 }, // 以 0 为基准，显示实际盈亏
    });

    seriesRef.current = areaSeries;
    areaSeries.setData(finalChartData);

    // 自适应容器大小
    const resizeObserver = new ResizeObserver((entries) => {
      const { width, height } = entries[0]?.contentRect || { width: 0, height: 0 };
      chart.applyOptions({
        width: Math.floor(width),
        height: Math.floor(height),
      });
    });

    resizeObserver.observe(chartContainerRef.current);

    // 监听十字交叉线移动
    chart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const data = chartData.find((d) => d.time === param.time);
        if (data && data.value !== undefined && data.value !== null && isFinite(data.value)) {
          const date = new Date((data.time as number) * 1000);
          const safeValue = data.value;
          setHoveredData({
            date: date.toLocaleString('zh-CN', {
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
            }),
            balance: safeValue,
            profit: safeValue,
          });
        }
      } else {
        setHoveredData(null);
      }
    });

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [equityCurve, initialBalance]);

  // ==========================================
  // 交易标记：统一的节点标注逻辑
  // ==========================================
  useEffect(() => {
    if (!chartRef.current || !seriesRef.current) return;
    if (!tradeLogs || tradeLogs.length === 0) return;

    // 统一使用 action_name 复合字段：OPEN_LONG, OPEN_SHORT, CLOSE_LONG, CLOSE_SHORT
    const markers = tradeLogs
      .filter((trade) => {
        // 严格检查：必须有 action_name
        if (!trade.action_name) return false;
        // 额外验证：必须有有效的时间戳和价格
        if (!trade.timestamp || trade.timestamp <= 0) return false;
        if (!trade.price || trade.price <= 0) return false;
        return true;
      })
      .map((trade) => {
        // 防御性检查：如果 action_name 未定义则跳过
        if (!trade.action_name) return null;

        const actionName = trade.action_name.toUpperCase();
        const isOpen = actionName.includes('OPEN');
        const isLong = actionName.includes('LONG');
        const isShort = actionName.includes('SHORT');

        // 确定箭头位置、颜色和文字
        let position: 'belowBar' | 'aboveBar';
        let color: string;
        let shape: 'arrowUp' | 'arrowDown';
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
          // CLOSE_LONG: 橙色向上箭头，belowBar（平多获利）
          position = 'belowBar';
          color = '#f97316';
          shape = 'arrowUp';
          text = '平多';
        } else if (actionName.includes('CLOSE_SHORT')) {
          // CLOSE_SHORT: 橙色向下箭头，aboveBar（平空获利）
          position = 'aboveBar';
          color = '#f97316';
          shape = 'arrowDown';
          text = '平空';
        } else {
          // 未知类型：使用默认标记
          position = 'aboveBar';
          color = '#71717a';
          shape = 'arrowDown';
          text = '';
        }

        return {
          time: (trade.timestamp / 1000) as any,
          position,
          color,
          shape,
          text,
          size: 2,
        };
      })
      .filter(Boolean); // 过滤掉 null 值

    // 只有有效标记才设置
    if (markers.length > 0) {
      // 必须通过 time 去重，否则 lightweight-charts 会报错
      const uniqueMarkersMap = new Map();
      markers.forEach(m => {
        uniqueMarkersMap.set(m.time, m);
      });
      const uniqueMarkers: any[] = Array.from(uniqueMarkersMap.values());

      uniqueMarkers.sort((a, b) => {
        const timeA = typeof a.time === 'number' ? a.time : 0;
        const timeB = typeof b.time === 'number' ? b.time : 0;
        return timeA - timeB;
      });

      try {
        seriesRef.current?.setMarkers?.(uniqueMarkers);
      } catch (e) {
        console.warn('设置交易标记失败:', e);
      }
    }
  }, [tradeLogs]);

  return (
    <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden">
      <CardHeader className="pb-2 border-b border-zinc-200 dark:border-white/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-500" />
            <CardTitle className="text-zinc-900 dark:text-zinc-200">
              资金权益曲线
            </CardTitle>
          </div>
          {hoveredData && (
            <div className="flex items-center gap-4 text-sm">
              <span className="text-zinc-500">{hoveredData.date}</span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                ${(hoveredData.balance !== undefined && isFinite(hoveredData.balance))
                  ? hoveredData.balance.toFixed(2)
                  : '0.00'}
              </span>
              <span
                className={`font-mono ${(hoveredData.profit !== undefined && hoveredData.profit >= 0)
                  ? 'text-emerald-500'
                  : 'text-rose-500'
                  }`}
              >
                {(hoveredData.profit !== undefined && isFinite(hoveredData.profit))
                  ? (hoveredData.profit >= 0 ? '+' : '') + hoveredData.profit.toFixed(2)
                  : '0.00'}
              </span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div
          ref={chartContainerRef}
          className="w-full h-[320px]"
        />
      </CardContent>
    </Card>
  );
}
