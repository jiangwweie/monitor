/**
 * Backtest Stats Panel
 * 回测统计指标仪表板
 */

import { TrendingUp, TrendingDown, Award, Target, Zap, Wallet } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface BacktestStats {
  initialBalance: number;
  finalBalance: number;
  totalReturnPct: number;
  totalPnl?: number;
  maxDrawdownPct: number;
  winRate: number;
  totalTrades: number;
  winCount?: number;
  lossCount?: number;
  profitFactor?: number;
  buyCount?: number;
  sellCount?: number;
  errorCount?: number;
  avgWin?: number;
  avgLoss?: number;
  consecutiveWins?: number;
  consecutiveLosses?: number;
}

interface BacktestStatsPanelProps {
  stats: BacktestStats;
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  subValue?: string;
  positive?: boolean;
  neutral?: boolean;
}

function StatCard({ icon, label, value, subValue, positive, neutral }: StatCardProps) {
  const bgColor = positive
    ? 'bg-emerald-500/10'
    : neutral
    ? 'bg-zinc-500/10'
    : 'bg-rose-500/10';

  const textColor = positive
    ? 'text-emerald-500'
    : neutral
    ? 'text-zinc-500'
    : 'text-rose-500';

  return (
    <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-2xl overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{label}</p>
            <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{value}</p>
            {subValue && (
              <p className={`text-xs ${textColor}`}>{subValue}</p>
            )}
          </div>
          <div className={`p-2.5 rounded-xl ${bgColor}`}>{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}

export function BacktestStatsPanel({ stats }: BacktestStatsPanelProps) {
  const formatCurrency = (value: number) => {
    const safeValue = (value === undefined || value === null || !isFinite(value)) ? 0 : value;
    return `$${safeValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatPercent = (value: number | undefined | null, decimals = 1) => {
    if (value === undefined || value === null || !isFinite(value) || isNaN(value)) {
      return '—'; // 优雅降级显示横线
    }
    const safeValue = Math.abs(value) < 0.0001 ? 0 : value; // 极小值视为 0
    const formatted = safeValue.toFixed(decimals);
    return safeValue >= 0 ? `+${formatted}%` : `${formatted}%`;
  };

  // 安全计算胜率 - 避免除 0
  const safeWinRate = stats.totalTrades > 0
    ? ((stats.winCount || 0) / stats.totalTrades * 100)
    : 0;

  // 安全计算最终权益 - 避免 NaN
  const safeFinalBalance = isFinite(stats.finalBalance) ? stats.finalBalance : stats.initialBalance;
  const safeTotalPnl = (stats.totalPnl !== undefined && isFinite(stats.totalPnl))
    ? stats.totalPnl
    : (safeFinalBalance - (stats.initialBalance || 0));

  // 检查是否有进阶数据
  const hasAdvancedData = (stats.profitFactor && stats.profitFactor > 0 && isFinite(stats.profitFactor)) ||
                          (stats.buyCount && stats.buyCount > 0) ||
                          (stats.sellCount && stats.sellCount > 0);

  return (
    <div className="space-y-4">
      {/* 核心指标 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-emerald-500" />}
          label="总收益率"
          value={formatPercent(stats.totalReturnPct)}
          subValue={`初始：${formatCurrency(stats.initialBalance || 0)}`}
          positive={(stats.totalReturnPct || 0) > 0}
        />
        <StatCard
          icon={<Wallet className="w-5 h-5 text-blue-500" />}
          label="总盈亏"
          value={formatCurrency(safeTotalPnl)}
          subValue={formatPercent(stats.totalReturnPct)}
          positive={safeTotalPnl > 0}
        />
        <StatCard
          icon={<TrendingDown className="w-5 h-5 text-rose-500" />}
          label="最大回撤"
          value={formatPercent(Math.abs(stats.maxDrawdownPct || 0))}
          subValue="风险指标"
          positive={(stats.maxDrawdownPct || 100) < 15}
        />
        <StatCard
          icon={<Award className="w-5 h-5 text-amber-500" />}
          label="胜率"
          value={`${safeWinRate.toFixed(1)}%`}
          subValue={stats.totalTrades > 0 ? `共 ${stats.totalTrades} 笔交易` : '暂无交易'}
          positive={safeWinRate > 50}
        />
      </div>

      {/* 进阶指标 - 有数据时显示 */}
      {hasAdvancedData && (
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          {stats.profitFactor !== undefined && stats.profitFactor > 0 && isFinite(stats.profitFactor) && (
            <StatCard
              icon={<Target className="w-5 h-5 text-purple-500" />}
              label="盈亏比"
              value={isFinite(stats.profitFactor) ? stats.profitFactor.toFixed(2) : '—'}
              subValue={stats.profitFactor > 1.5 ? '优秀' : stats.profitFactor > 1 ? '良好' : '待改进'}
              positive={stats.profitFactor > 1.5}
            />
          )}
          {stats.buyCount !== undefined && stats.buyCount >= 0 && (
            <StatCard
              icon={<TrendingUp className="w-5 h-5 text-emerald-500" />}
              label="做多次数"
              value={`${stats.buyCount}`}
              neutral
            />
          )}
          {stats.sellCount !== undefined && stats.sellCount >= 0 && (
            <StatCard
              icon={<TrendingDown className="w-5 h-5 text-rose-500" />}
              label="做空次数"
              value={`${stats.sellCount}`}
              neutral
            />
          )}
          {stats.winCount !== undefined && stats.winCount >= 0 && (
            <StatCard
              icon={<Award className="w-5 h-5 text-emerald-500" />}
              label="盈利次数"
              value={`${stats.winCount}`}
              neutral
            />
          )}
          {stats.lossCount !== undefined && stats.lossCount >= 0 && (
            <StatCard
              icon={<Award className="w-5 h-5 text-rose-500" />}
              label="亏损次数"
              value={`${stats.lossCount}`}
              neutral
            />
          )}
        </div>
      )}
    </div>
  );
}
