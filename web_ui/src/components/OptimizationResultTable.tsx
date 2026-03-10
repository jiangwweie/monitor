/**
 * Optimization Result Table
 * 参数优化结果对比表格
 */

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trophy, TrendingUp } from "lucide-react";

export interface OptimizationResultRow {
  rank: number;
  params: Record<string, any>;
  totalReturnPct: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
}

interface OptimizationResultTableProps {
  results: OptimizationResultRow[];
  objective: string;  // 当前优化目标，用于高亮对应列
}

// 格式化参数组合为短字符串
function formatParams(params: Record<string, any>): string {
  return Object.entries(params)
    .map(([key, value]) => {
      // 缩写参数名
      const abbreviations: Record<string, string> = {
        ema_period: "ema",
        leverage: "lev",
        risk_pct: "risk",
        atr_period: "atr",
        max_sl_dist: "sl",
      };
      const shortKey = abbreviations[key] || key;
      return `${shortKey}=${value}`;
    })
    .join(", ");
}

// 格式化数值显示
function formatNumber(value: number, decimals: number = 2): string {
  if (value === undefined || value === null || isNaN(value)) {
    return "-";
  }
  return value.toFixed(decimals);
}

// 获取列配置
function getColumnConfig(objective: string) {
  const columns = [
    { key: "totalReturnPct", label: "总收益率%", highlight: objective === "total_return_pct" },
    { key: "maxDrawdownPct", label: "最大回撤%", highlight: objective === "max_drawdown_pct" },
    { key: "sharpeRatio", label: "夏普比率", highlight: objective === "sharpe_ratio" },
    { key: "winRate", label: "胜率%", highlight: objective === "win_rate" },
    { key: "profitFactor", label: "盈亏比", highlight: objective === "profit_factor" },
  ];
  return columns;
}

export function OptimizationResultTable({
  results,
  objective,
}: OptimizationResultTableProps) {
  const columns = getColumnConfig(objective);

  if (!results || results.length === 0) {
    return null;
  }

  return (
    <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden">
      <CardHeader className="pb-4 border-b border-zinc-200 dark:border-white/5">
        <div className="flex items-center gap-2">
          <Trophy className="w-5 h-5 text-yellow-500" />
          <CardTitle className="text-zinc-900 dark:text-zinc-200">
            优化结果排名
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-200 dark:border-white/10">
              <TableHead className="w-16 text-center">排名</TableHead>
              <TableHead>参数组合</TableHead>
              {columns.map((col) => (
                <TableHead
                  key={col.key}
                  className={`text-right ${
                    col.highlight
                      ? "text-blue-500 font-semibold"
                      : "text-zinc-500"
                  }`}
                >
                  {col.label}
                </TableHead>
              ))}
              <TableHead className="text-right text-zinc-500">交易次数</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.map((row, index) => {
              const isGold = row.rank === 1;
              const isNegativeReturn = row.totalReturnPct < 0;

              return (
                <TableRow
                  key={index}
                  className={`
                    border-zinc-200 dark:border-white/10
                    ${isGold ? "bg-yellow-500/10" : ""}
                    hover:bg-muted/50
                  `}
                >
                  <TableCell className="text-center">
                    {row.rank === 1 ? (
                      <span className="text-lg">🥇</span>
                    ) : row.rank === 2 ? (
                      <span className="text-lg">🥈</span>
                    ) : row.rank === 3 ? (
                      <span className="text-lg">🥉</span>
                    ) : (
                      <span className="text-zinc-500 font-mono">{row.rank}</span>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {formatParams(row.params)}
                  </TableCell>
                  {/* 总收益率 */}
                  <TableCell
                    className={`text-right font-mono ${
                      columns[0].highlight ? "text-blue-500 font-semibold" : ""
                    } ${isNegativeReturn ? "text-red-500" : "text-emerald-500"}`}
                  >
                    {row.totalReturnPct >= 0 ? "+" : ""}
                    {formatNumber(row.totalReturnPct)}
                  </TableCell>
                  {/* 最大回撤 */}
                  <TableCell
                    className={`text-right font-mono ${
                      columns[1].highlight ? "text-blue-500 font-semibold" : "text-zinc-500"
                    }`}
                  >
                    {formatNumber(row.maxDrawdownPct)}
                  </TableCell>
                  {/* 夏普比率 */}
                  <TableCell
                    className={`text-right font-mono ${
                      columns[2].highlight ? "text-blue-500 font-semibold" : "text-zinc-500"
                    }`}
                  >
                    {formatNumber(row.sharpeRatio)}
                  </TableCell>
                  {/* 胜率 */}
                  <TableCell
                    className={`text-right font-mono ${
                      columns[3].highlight ? "text-blue-500 font-semibold" : "text-zinc-500"
                    }`}
                  >
                    {formatNumber(row.winRate)}
                  </TableCell>
                  {/* 盈亏比 */}
                  <TableCell
                    className={`text-right font-mono ${
                      columns[4].highlight ? "text-blue-500 font-semibold" : "text-zinc-500"
                    }`}
                  >
                    {formatNumber(row.profitFactor)}
                  </TableCell>
                  {/* 交易次数 */}
                  <TableCell className="text-right font-mono text-zinc-500">
                    {row.totalTrades}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
