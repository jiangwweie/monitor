/**
 * Backtest Task List
 * 回测任务队列 - 现代化数据表格
 */

import { useState, useEffect } from "react";
import { RefreshCw, ExternalLink, Clock, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";

import {
  type BacktestTask,
  getBacktestTasks,
  formatStatus,
} from "@/services/backtest_api";

interface BacktestTaskListProps {
  onRefresh?: () => void;
  onViewDetail?: (taskId: string) => void;
}

export function BacktestTaskList({ onRefresh, onViewDetail }: BacktestTaskListProps) {
  const [tasks, setTasks] = useState<BacktestTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const data = await getBacktestTasks();
      setTasks(data);
    } catch {
      toast.error("获取任务列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, [refreshTrigger]);

  const handleRefresh = () => {
    setRefreshTrigger((prev) => prev + 1);
    onRefresh?.();
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
      case "pending_in_queue":
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case "running":
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case "completed":
        return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const formatReturn = (pct?: number) => {
    if (pct === undefined) return "-";
    const formatted = pct.toFixed(2);
    const color = pct >= 0 ? "text-emerald-500" : "text-rose-500";
    return <span className={color}>{pct >= 0 ? "+" : ""}{formatted}%</span>;
  };

  const formatDateTime = (dateStr?: string, timestamp?: number) => {
    if (timestamp) {
      const date = new Date(timestamp * 1000);
      return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    }
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getDateRange = (task: BacktestTask) => {
    // 尝试多种字段名
    const start = task.startDate || task.start_date || '';
    const end = task.endDate || task.end_date || '';

    if (start && end) {
      // 提取 MM-DD 部分
      const startShort = start.slice(5, 16);
      const endShort = end.slice(5, 16);
      return `${startShort} ~ ${endShort}`;
    }
    return '-';
  };

  return (
    <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
      <CardHeader className="pb-4 border-b border-zinc-200 dark:border-white/5">
        <div className="flex items-center justify-between">
          <CardTitle className="text-zinc-900 dark:text-zinc-200">
            回测任务队列
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            disabled={loading}
            className="text-zinc-500 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-300 h-9"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {loading && tasks.length === 0 ? (
          <div className="p-12 text-center text-zinc-500">
            <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin opacity-50" />
            <p>加载任务列表...</p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="p-12 text-center text-zinc-500">
            <Clock className="w-8 h-8 mx-auto mb-3 opacity-20" />
            <p>暂无回测任务</p>
            <p className="text-xs opacity-60 mt-1">
              在上方配置表单中设置参数并启动回测
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-zinc-200 dark:border-white/5">
                  <TableHead className="w-24 text-zinc-500 font-medium">状态</TableHead>
                  <TableHead className="text-zinc-500 font-medium">交易对</TableHead>
                  <TableHead className="text-zinc-500 font-medium">周期</TableHead>
                  <TableHead className="text-zinc-500 font-medium">时间区间</TableHead>
                  <TableHead className="text-right text-zinc-500 font-medium">收益率</TableHead>
                  <TableHead className="text-right text-zinc-500 font-medium">创建时间</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => {
                  const statusInfo = formatStatus(task.status);
                  return (
                    <TableRow
                      key={task.taskId}
                      className="border-zinc-200 dark:border-white/5 hover:bg-white/[0.02] transition-colors"
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(task.status)}
                          <Badge
                            variant="outline"
                            className={`
                              border-zinc-200 dark:border-zinc-700
                              ${statusInfo.color === "green" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : ""}
                              ${statusInfo.color === "blue" ? "bg-blue-500/10 text-blue-600 dark:text-blue-400" : ""}
                              ${statusInfo.color === "yellow" ? "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400" : ""}
                              ${statusInfo.color === "red" ? "bg-red-500/10 text-red-600 dark:text-red-400" : ""}
                            `}
                          >
                            {statusInfo.label}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="font-medium text-zinc-900 dark:text-zinc-100">
                        {task.symbol}
                      </TableCell>
                      <TableCell className="text-zinc-600 dark:text-zinc-400">
                        {task.interval}
                      </TableCell>
                      <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm">
                        {getDateRange(task)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatReturn(task.totalReturnPct)}
                      </TableCell>
                      <TableCell className="text-right text-zinc-500 text-sm">
                        {formatDateTime(task.created_at, task.createdAt)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                          title="查看详情"
                          onClick={() => onViewDetail?.(task.taskId)}
                        >
                          <ExternalLink className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
