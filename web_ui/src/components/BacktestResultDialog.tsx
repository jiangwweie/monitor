/**
 * Backtest Result Dialog
 * 回测结果详情对话框
 */

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { X, FileText, Loader2 } from "lucide-react";

import { BacktestResultChart } from "./BacktestResultChart";
import { BacktestCandlestickChart } from "./BacktestCandlestickChart";
import { BacktestStatsPanel } from "./BacktestStatsPanel";
import { getBacktestResult, type BacktestResult } from "@/services/backtest_api";

interface BacktestResultDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  taskId: string | null;
}

export function BacktestResultDialog({
  open,
  onOpenChange,
  taskId,
}: BacktestResultDialogProps) {
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && taskId) {
      loadResult();
    }
  }, [open, taskId]);

  const loadResult = async () => {
    if (!taskId) return;
    setLoading(true);
    try {
      const data = await getBacktestResult(taskId);
      // 检查是否有错误信息
      if (data.errorMessage) {
        console.error('Backend error:', data.errorMessage);
      }
      setResult(data);
    } catch (error) {
      console.error('Failed to load result:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDateTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto bg-zinc-50 dark:bg-zinc-950 border-zinc-200 dark:border-white/10">
        <DialogHeader className="pb-4 border-b border-zinc-200 dark:border-white/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-emerald-500/10">
                <FileText className="w-5 h-5 text-emerald-500" />
              </div>
              <div>
                <DialogTitle className="text-zinc-900 dark:text-zinc-100">
                  回测结果详情
                </DialogTitle>
                <p className="text-sm text-zinc-500 mt-0.5">
                  {taskId && `Task ID: ${taskId}`}
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="h-9 w-9 p-0"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </DialogHeader>

        {loading ? (
          <div className="py-16 text-center">
            <Loader2 className="w-8 h-8 mx-auto mb-4 animate-spin text-zinc-400" />
            <p className="text-zinc-500">加载回测结果中...</p>
          </div>
        ) : result ? (
          <div className="space-y-6 py-4">
            {/* 状态和基本信息 */}
            <div className="flex items-center gap-4">
              <Badge
                variant="outline"
                className={`
                  ${result.status === 'completed'
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                    : 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20'}
                `}
              >
                {result.status === 'completed' ? '已完成' : result.status}
              </Badge>
              {result.equityCurve && result.equityCurve.length > 0 && (
                <span className="text-sm text-zinc-500">
                  数据点数：{result.equityCurve.length}
                </span>
              )}
            </div>

            {/* 统计指标面板 */}
            <BacktestStatsPanel stats={result.stats} />

            {/* 资金曲线图表 */}
            <BacktestResultChart
              equityCurve={result.equityCurve || []}
              tradeLogs={result.tradeLogs || []}
              initialBalance={result.stats.initialBalance}
            />

            {/* 行情 K 线与交易点位 */}
            {result.klineData && result.klineData.length > 0 && (
              <BacktestCandlestickChart
                klineData={result.klineData}
                tradeLogs={result.tradeLogs || []}
              />
            )}

            {/* 运行日志 */}
            {result.runtimeLogs && result.runtimeLogs.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  运行日志
                </h3>
                <ScrollArea className="h-40 rounded-xl border border-zinc-200 dark:border-white/10 bg-white/50 dark:bg-zinc-900/50 p-4">
                  <div className="space-y-1 font-mono text-xs text-zinc-600 dark:text-zinc-400">
                    {result.runtimeLogs.map((log, idx) => (
                      <div key={idx} className="leading-relaxed">
                        {log}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}
          </div>
        ) : (
          <div className="py-16 text-center text-zinc-500">
            <p>暂无回测结果数据</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
