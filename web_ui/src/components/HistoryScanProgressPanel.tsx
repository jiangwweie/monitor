import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { X, RadioTower, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { usePolling } from "@/hooks/usePolling";

export interface TaskStatus {
  task_id: string;
  status: "running" | "completed" | "failed";
  progress: number;      // 0-100
  message: string;
  result?: {
    total_bars_scanned: number;
    signals_found: number;
    signals_saved: number;
  };
  config?: {
    symbol: string;
    interval: string;
    start_date: string;
    end_date: string;
  };
}

interface HistoryScanProgressPanelProps {
  taskId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTaskComplete?: () => void;
}

const API_BASE = "http://localhost:8000";

export function HistoryScanProgressPanel({
  taskId,
  open,
  onOpenChange,
  onTaskComplete,
}: HistoryScanProgressPanelProps) {
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);

  // 轮询任务状态
  const { data: _data } = usePolling(
    async () => {
      if (!taskId) return null;
      const res = await fetch(`${API_BASE}/api/signals/history-check/${taskId}`);
      if (!res.ok) throw new Error("Status fetch failed");
      return await res.json();
    },
    {
      interval: 1000,  // 1 秒轮询
      enabled: open && taskId !== null && taskStatus?.status === "running",
      immediate: true,
      onSuccess: (data) => {
        if (data) {
          setTaskStatus(data as TaskStatus);

          // 任务完成
          if (data.status === "completed") {
            onTaskComplete?.();
          } else if (data.status === "failed") {
            // 任务失败，停止轮询由 enabled 控制
          }
        }
      },
      onError: (error) => {
        console.error("轮询任务状态失败:", error);
      },
    }
  );

  // 计时器
  useEffect(() => {
    if (!open || taskStatus?.status !== "running") {
      return;
    }

    const startTime = Date.now();
    const interval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [open, taskStatus?.status]);

  // 格式化时间
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (!open || !taskId) {
    return null;
  }

  const isRunning = taskStatus?.status === "running";
  const isCompleted = taskStatus?.status === "completed";
  const isFailed = taskStatus?.status === "failed";

  return (
    <div className="fixed bottom-6 right-6 z-50 w-[420px] animate-in slide-in-from-bottom-4 fade-in duration-300">
      <Card className="backdrop-blur-xl bg-white/95 dark:bg-zinc-900/95 border border-zinc-200 dark:border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-white/5 bg-gradient-to-r from-blue-500/10 to-purple-500/10 dark:from-blue-500/5 dark:to-purple-500/5">
          <div className="flex items-center gap-2">
            {isRunning && <RadioTower className="w-5 h-5 text-blue-500 animate-pulse" />}
            {isCompleted && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
            {isFailed && <AlertCircle className="w-5 h-5 text-rose-500" />}
            <span className="font-semibold text-sm text-zinc-800 dark:text-zinc-200">
              {isRunning && "📡 历史信号扫描"}
              {isCompleted && "✅ 扫描完成"}
              {isFailed && "❌ 扫描失败"}
              {!taskStatus && "📡 历史信号扫描"}
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 hover:bg-zinc-200/50 dark:hover:bg-zinc-800/50"
            onClick={() => onOpenChange(false)}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Task ID */}
          <div className="flex items-center justify-between text-xs">
            <span className="text-zinc-500 dark:text-zinc-400">任务 ID:</span>
            <Badge variant="secondary" className="font-mono text-[10px]">
              {taskId?.slice(0, 12)}...
            </Badge>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-zinc-600 dark:text-zinc-400">扫描进度</span>
              <span className="font-semibold text-zinc-800 dark:text-zinc-200">
                {taskStatus?.progress || 0}%
              </span>
            </div>
            <Progress
              value={taskStatus?.progress || 0}
              className="h-2"
              indicatorColor={
                isCompleted ? "bg-emerald-500" :
                isFailed ? "bg-rose-500" :
                "bg-blue-500"
              }
            />
          </div>

          {/* Status Message */}
          <div className="flex items-start gap-2">
            {isRunning && <Loader2 className="w-4 h-4 text-blue-500 animate-spin mt-0.5" />}
            <p className={`text-sm ${
              isFailed ? "text-rose-500" : "text-zinc-600 dark:text-zinc-400"
            }`}>
              {taskStatus?.message || "正在初始化任务..."}
            </p>
          </div>

          {/* Stats (when running) */}
          {isRunning && taskStatus?.result && (
            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-zinc-200 dark:border-white/5">
              <div className="text-xs">
                <span className="text-zinc-500 dark:text-zinc-400">已扫描</span>
                <p className="font-semibold text-zinc-800 dark:text-zinc-200">
                  {taskStatus.result.total_bars_scanned.toLocaleString()} 根 K 线
                </p>
              </div>
              <div className="text-xs">
                <span className="text-zinc-500 dark:text-zinc-400">发现信号</span>
                <p className="font-semibold text-blue-500">
                  {taskStatus.result.signals_found.toLocaleString()} 个
                </p>
              </div>
            </div>
          )}

          {/* Elapsed Time */}
          {isRunning && (
            <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
              <span>已运行：</span>
              <span className="font-mono">{formatTime(elapsedTime)}</span>
            </div>
          )}

          {/* Result Summary (when completed) */}
          {isCompleted && taskStatus?.result && (
            <div className="space-y-3 pt-3 border-t border-zinc-200 dark:border-white/5">
              <p className="font-semibold text-sm text-zinc-800 dark:text-zinc-200">
                📊 扫描结果
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg p-3 text-xs">
                  <span className="text-zinc-500 dark:text-zinc-400">扫描 K 线总数</span>
                  <p className="font-semibold text-zinc-800 dark:text-zinc-200 text-lg">
                    {taskStatus.result.total_bars_scanned.toLocaleString()}
                  </p>
                </div>
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 text-xs">
                  <span className="text-blue-600 dark:text-blue-400">发现信号数</span>
                  <p className="font-semibold text-blue-600 dark:text-blue-400 text-lg">
                    {taskStatus.result.signals_found.toLocaleString()}
                  </p>
                </div>
                <div className="bg-emerald-50 dark:bg-emerald-900/20 rounded-lg p-3 text-xs col-span-2">
                  <span className="text-emerald-600 dark:text-emerald-400">成功入库</span>
                  <p className="font-semibold text-emerald-600 dark:text-emerald-400 text-lg">
                    {taskStatus.result.signals_saved.toLocaleString()} 个信号
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Config Summary */}
          {taskStatus?.config && (
            <div className="pt-3 border-t border-zinc-200 dark:border-white/5">
              <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                <span>扫描配置：</span>
                <Badge variant="outline" className="text-[10px]">
                  {taskStatus.config.symbol}
                </Badge>
                <Badge variant="outline" className="text-[10px]">
                  {taskStatus.config.interval}
                </Badge>
                <span className="font-mono">
                  {taskStatus.config.start_date} ~ {taskStatus.config.end_date}
                </span>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
