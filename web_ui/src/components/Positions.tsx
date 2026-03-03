import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Wallet } from "lucide-react";

interface PositionsProps {
  dashboardData: {
    current_positions_count: number;
    positions: any[];
  } | null;
  onOpenPositionDetail: (symbol: string) => void;
}

export function Positions({ dashboardData, onOpenPositionDetail }: PositionsProps) {
  if (!dashboardData) {
    return (
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden shadow-lg">
        <CardContent className="p-12 text-center text-zinc-500">
          <Wallet className="w-16 h-16 mx-auto mb-4 opacity-20" />
          <p className="text-lg">持仓数据暂时不可用</p>
          <p className="text-xs opacity-60 mt-2">
            请在"系统设置"中确认币安 API Keys 配置并确保网络畅通。
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden shadow-lg">
      <CardHeader className="pb-4 border-b border-zinc-200 dark:border-white/5 bg-black/5 dark:bg-black/20">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-zinc-200">
            <Wallet className="w-5 h-5 text-blue-400" /> 活跃持仓列表
          </CardTitle>
          <Badge
            variant="outline"
            className="bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700"
          >
            共 {dashboardData.current_positions_count} 个
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        {dashboardData.positions.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-zinc-500 text-sm">
            <Wallet className="w-10 h-10 mb-4 opacity-20" />
            当前无活跃持仓
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dashboardData.positions.map((pos, idx) => (
              <div
                key={idx}
                className="bg-white/50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-white/10 rounded-2xl p-5 hover:bg-white dark:hover:bg-zinc-800 transition-colors shadow-sm"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${
                        pos.positionAmt > 0
                          ? "bg-emerald-500/10 text-emerald-500 dark:text-emerald-400"
                          : "bg-rose-500/10 text-rose-500 dark:text-rose-400"
                      }`}
                    >
                      {pos.positionAmt > 0 ? "多" : "空"}
                    </div>
                    <div>
                      <h4 className="font-bold text-zinc-900 dark:text-zinc-100 text-lg flex items-center gap-2">
                        {pos.symbol}{" "}
                        <Badge
                          variant="secondary"
                          className="text-[10px] h-4 px-1"
                        >
                          {pos.leverage}x
                        </Badge>
                      </h4>
                      <p className="text-xs text-zinc-500">
                        仓位数量：{Math.abs(pos.positionAmt)}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs border-zinc-200 dark:border-white/10"
                    onClick={() => onOpenPositionDetail(pos.symbol)}
                  >
                    详情
                  </Button>
                </div>
                <div className="space-y-2 pt-4 border-t border-zinc-200 dark:border-white/10">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-zinc-500">入场价</span>
                    <span className="text-sm font-mono text-zinc-900 dark:text-zinc-100">
                      ${Number(pos.entryPrice).toFixed(4)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-zinc-500">未实现盈亏</span>
                    <span
                      className={`text-sm font-mono font-bold ${
                        pos.unrealized_pnl >= 0
                          ? "text-emerald-500"
                          : "text-rose-500"
                      }`}
                    >
                      {pos.unrealized_pnl > 0 ? "+" : ""}
                      {Number(pos.unrealized_pnl).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
