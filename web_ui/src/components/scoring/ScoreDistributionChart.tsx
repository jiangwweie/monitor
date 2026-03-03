import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Loader2 } from "lucide-react";

interface ScoreDistributionChartProps {
  data: {
    total_bars?: number;
    signals_found?: number;
    score_distribution?: Record<string, number>;
    tier_distribution?: Record<string, number>;
  } | null;
  loading: boolean;
}

export function ScoreDistributionChart({
  data,
  loading,
}: ScoreDistributionChartProps) {
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
      <div className="flex flex-col items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-400 mb-2" />
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
              labelStyle={{ color: "#18181b" }}
              itemStyle={{ color: "#3f3f46" }}
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
