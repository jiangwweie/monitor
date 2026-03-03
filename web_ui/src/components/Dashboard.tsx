import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Wallet, Wifi } from "lucide-react";

interface DashboardProps {
  systemStatus: {
    is_connected: boolean;
    api_latency_ms: number;
    api_weight_usage: number;
    uptime: string;
  };
  dashboardData: {
    total_wallet_balance: number;
    available_balance: number;
    total_balance?: number;
    available_margin?: number;
    total_unrealized_pnl: number;
    current_positions_count: number;
    positions: any[];
  } | null;
  realtimePrices: Record<string, number>;
  activeSymbols: string[];
  resetCountdown?: number;
  onOpenPositionDetail: (symbol: string) => void;
}

export function Dashboard({
  systemStatus,
  dashboardData,
  realtimePrices,
  activeSymbols,
  resetCountdown,
  onOpenPositionDetail,
}: DashboardProps) {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* System Health Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* API Weight Progress Card */}
        <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-zinc-200">
              <Wifi className="w-5 h-5 text-blue-400" />
              API 权重消耗
            </CardTitle>
            <CardDescription>币安接口频率与限流实时监控</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex justify-between items-end text-sm mb-2 text-zinc-500 dark:text-zinc-400">
              <span>当前用量</span>
              <div className="text-right">
                <span className="text-xs mr-2 opacity-60">重置倒计时：{resetCountdown}s</span>
                <span
                  className={
                    systemStatus.api_weight_usage > 80
                      ? "text-red-500 font-bold"
                      : "text-emerald-500 font-bold"
                  }
                >
                  {systemStatus.api_weight_usage}%
                </span>
              </div>
            </div>
            <div className="relative h-3 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`absolute top-0 left-0 h-full ${systemStatus.api_weight_usage > 80 ? "bg-red-500" : "bg-emerald-500"} transition-all duration-300`}
                style={{ width: `${systemStatus.api_weight_usage}%` }}
              />
            </div>
            <p className="text-xs text-zinc-500 mt-4 leading-relaxed">
              （每分钟重置）限制保持在 80% 以内可确保高频执行的可靠性与 IP 安全。
            </p>
          </CardContent>
        </Card>

        {/* Server Stats */}
        <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
          <CardHeader>
            <CardTitle className="text-zinc-900 dark:text-zinc-200">系统健康度</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <p className="text-sm text-zinc-500 mb-1">API 延迟</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                {systemStatus.api_latency_ms}{" "}
                <span className="text-sm font-normal text-zinc-500">ms</span>
              </p>
            </div>
            <div>
              <p className="text-sm text-zinc-500 mb-1">连接状态</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                {systemStatus.is_connected ? (
                  <>
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]" />{" "}
                    在线
                  </>
                ) : (
                  <>
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]" />{" "}
                    离线
                  </>
                )}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Real-time Ticker */}
      <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-hide mt-6">
        {activeSymbols.map((sym) => (
          <div
            key={sym}
            className="flex-none bg-white/50 dark:bg-zinc-900/50 backdrop-blur-md border border-zinc-200 dark:border-white/10 rounded-2xl px-5 py-3 shadow-sm min-w-[140px]"
          >
            <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1">{sym}</p>
            <p className="text-lg font-bold text-zinc-900 dark:text-zinc-100 font-mono">
              {realtimePrices[sym] ? `$${realtimePrices[sym].toFixed(realtimePrices[sym] < 10 ? 4 : 2)}` : "---"}
            </p>
          </div>
        ))}
      </div>

      {/* Account Dashboard Card (Full Width) */}
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden mt-4">
        <CardHeader className="pb-4 border-b border-zinc-200 dark:border-white/5 bg-black/5 dark:bg-black/20">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-zinc-200">
              <Wallet className="w-5 h-5 text-blue-400" />
              账户与持仓
            </CardTitle>
            {dashboardData && (
              <Badge
                variant="outline"
                className="bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700"
              >
                {dashboardData.current_positions_count} 个活跃持仓
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {dashboardData ? (
            <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-zinc-200 dark:divide-white/5">
              {/* Balance Info */}
              <div className="p-6 md:col-span-1 space-y-6">
                <div>
                  <p className="text-sm text-zinc-500 mb-1">账户总资产</p>
                  <p className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
                    ${Number(dashboardData.total_wallet_balance).toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-zinc-500 mb-1">可用保证金</p>
                  <p className="text-xl font-semibold text-zinc-700 dark:text-zinc-300">
                    ${Number(dashboardData.available_balance).toFixed(2)}
                  </p>
                </div>
                <div className="pt-4 border-t border-zinc-200 dark:border-white/10">
                  <p className="text-sm text-zinc-500 mb-1">总计未实现盈亏</p>
                  <p
                    className={`text-xl font-bold tracking-tight ${
                      dashboardData.total_unrealized_pnl >= 0
                        ? "text-emerald-500 dark:text-emerald-400"
                        : "text-rose-500 dark:text-rose-400"
                    }`}
                  >
                    {dashboardData.total_unrealized_pnl > 0 ? "+" : ""}
                    {Number(dashboardData.total_unrealized_pnl).toFixed(2)}
                  </p>
                </div>
              </div>

              {/* Positions List */}
              <div className="p-0 md:col-span-2">
                {dashboardData.positions.length === 0 ? (
                  <div className="h-full flex items-center justify-center p-8 text-zinc-500 text-sm">
                    暂无持仓数据
                  </div>
                ) : (
                  <div className="divide-y divide-zinc-200 dark:divide-white/5">
                    {dashboardData.positions.map((pos, idx) => (
                      <div
                        key={idx}
                        className="p-6 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
                      >
                        <div className="flex items-center gap-4">
                          <div
                            className={`w-12 h-12 rounded-2xl flex items-center justify-center font-bold text-lg ${
                              pos.positionAmt > 0
                                ? "bg-emerald-500/10 text-emerald-500 dark:text-emerald-400"
                                : "bg-rose-500/10 text-rose-500 dark:text-rose-400"
                            }`}
                          >
                            {pos.positionAmt > 0 ? "多" : "空"}
                          </div>
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <h4 className="font-semibold text-zinc-900 dark:text-zinc-100">
                                {pos.symbol}
                              </h4>
                              <Badge
                                variant="outline"
                                className="bg-transparent border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400"
                              >
                                {pos.leverage}x
                              </Badge>
                            </div>
                            <p className="text-xs text-zinc-500">
                              仓位：{Math.abs(pos.positionAmt)} @ {Number(pos.entryPrice).toFixed(4)}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p
                            className={`text-lg font-semibold tracking-tight ${
                              pos.unrealized_pnl >= 0
                                ? "text-emerald-500 dark:text-emerald-400"
                                : "text-rose-500 dark:text-rose-400"
                            }`}
                          >
                            {pos.unrealized_pnl > 0 ? "+" : ""}
                            {Number(pos.unrealized_pnl).toFixed(2)}
                          </p>
                          <p className="text-xs text-zinc-500">未实现盈亏</p>
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-2 h-7 text-xs border-zinc-200 dark:border-white/10 hover:bg-zinc-100 dark:hover:bg-white/5"
                            onClick={() => onOpenPositionDetail(pos.symbol)}
                          >
                            详情
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center text-zinc-500">
              <Wallet className="w-8 h-8 mx-auto mb-3 opacity-20" />
              <p>账户资产数据暂时不可用。</p>
              <p className="text-xs opacity-60 mt-1">
                请在"系统设置"中确认币安 API Keys 配置并确保网络畅通。
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
