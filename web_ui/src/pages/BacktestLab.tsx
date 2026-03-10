/**
 * Backtest Lab - 回测实验室
 * FMZ 回测引擎集成前端界面
 */

import { useState, useEffect } from "react";
import { FlaskConical, History, ChevronDown, ChevronUp, Zap } from "lucide-react";
import { toast } from "sonner";

import { BacktestConfigForm } from "@/components/BacktestConfigForm";
import { BacktestTaskList } from "@/components/BacktestTaskList";
import { BacktestResultDialog } from "@/components/BacktestResultDialog";
import { OptimizationForm, type OptimizationRequest } from "@/components/OptimizationForm";
import { OptimizationResultTable, type OptimizationResultRow } from "@/components/OptimizationResultTable";
import { runBacktest, runOptimization, getOptimizationResult, type BacktestConfig } from "@/services/backtest_api";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

export function BacktestLab() {
  const [isRunning, setIsRunning] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // 参数优化相关状态
  const [optimizationOpen, setOptimizationOpen] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizationProgress, setOptimizationProgress] = useState<{
    current: number;
    total: number;
    status: string;
  } | null>(null);
  const [optimizationResults, setOptimizationResults] = useState<OptimizationResultRow[]>([]);
  const [currentObjective, setCurrentObjective] = useState("total_return_pct");
  const [optTaskId, setOptTaskId] = useState<string | null>(null);

  // 轮询任务列表（用于自动更新运行中任务的状态）
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshTrigger((prev) => prev + 1);
    }, 5000); // 每 5 秒刷新一次

    return () => clearInterval(interval);
  }, []);

  // 轮询优化任务状态
  useEffect(() => {
    if (!isOptimizing || !optTaskId) return;

    const pollInterval = setInterval(async () => {
      try {
        const data = await getOptimizationResult(optTaskId);
        setOptimizationProgress({
          current: data.completedCombinations,
          total: data.totalCombinations,
          status: data.status,
        });

        if (data.status === "completed") {
          setOptimizationResults(data.results || []);
          setIsOptimizing(false);
          setOptimizationProgress(null);
          toast.success("参数优化完成", {
            description: `共完成 ${data.completedCombinations}/${data.totalCombinations} 个组合`,
          });
          clearInterval(pollInterval);
        } else if (data.status === "failed") {
          setIsOptimizing(false);
          setOptimizationProgress(null);
          toast.error("参数优化失败");
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error("轮询优化结果失败:", error);
      }
    }, 3000); // 每 3 秒轮询一次

    // 10 分钟超时
    const timeoutId = setTimeout(() => {
      setIsOptimizing(false);
      setOptimizationProgress(null);
      toast.error("参数优化超时", {
        description: "10 分钟超时限制，请刷新页面重试",
      });
      clearInterval(pollInterval);
    }, 600000);

    return () => {
      clearInterval(pollInterval);
      clearTimeout(timeoutId);
    };
  }, [isOptimizing, optTaskId]);

  const handleSubmit = async (config: BacktestConfig) => {
    setIsRunning(true);
    try {
      const response = await runBacktest(config);
      toast.success("回测任务已启动", {
        description: `任务 ID: ${response.taskId}`,
      });
      // 触发任务列表刷新
      setRefreshTrigger((prev) => prev + 1);
    } catch {
      toast.error("启动回测失败", {
        description: "请稍后重试或检查后端服务状态",
      });
    } finally {
      setIsRunning(false);
    }
  };

  const handleRunOptimization = async (config: OptimizationRequest) => {
    setIsOptimizing(true);
    setCurrentObjective(config.objective);
    setOptimizationResults([]);
    setOptimizationProgress(null);

    try {
      const response = await runOptimization(config);
      setOptTaskId(response.optTaskId);
      toast.success("优化任务已启动", {
        description: `任务 ID: ${response.optTaskId}, 总组合数：${response.totalCombinations}`,
      });
    } catch (error) {
      toast.error("启动优化失败", {
        description: "请稍后重试或检查后端服务状态",
      });
      setIsOptimizing(false);
    }
  };

  const handleViewDetail = (taskId: string) => {
    setSelectedTaskId(taskId);
    setDialogOpen(true);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* 页面头部 */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-blue-500/10">
          <FlaskConical className="w-6 h-6 text-blue-500" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            Backtest Lab
          </h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            FMZ 回测引擎 - 策略验证与参数优化
          </p>
        </div>
      </div>

      {/* 上半部分：配置表单 */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <History className="w-4 h-4 text-zinc-500" />
          <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            新建回测
          </h3>
        </div>
        <BacktestConfigForm onSubmit={handleSubmit} isLoading={isRunning} />
      </section>

      {/* 参数优化折叠面板 */}
      <section>
        <div className="space-y-4">
          <Button
            variant="outline"
            onClick={() => setOptimizationOpen(!optimizationOpen)}
            className="w-full justify-between border-dashed border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <span className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-500" />
              参数优化（网格搜索）
            </span>
            {optimizationOpen ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </Button>

          {optimizationOpen && (
            <div className="space-y-4">
              <OptimizationForm
                baseConfig={{
                  symbol: "BTCUSDT",
                  interval: "1h",
                  start_date: "",
                  end_date: "",
                  fmz_config: { initial_balance: 100000, fee_maker: 75, fee_taker: 80, fee_denominator: 5, slip_point: 0 },
                  strategy_config: {
                    max_sl_dist: 0.035,
                    pinbar_config: { body_max_ratio: 0.3, shadow_min_ratio: 0.5, volatility_atr_multiplier: 2, doji_threshold: 0.1, doji_shadow_bonus: 0.5, mtf_trend_filter_mode: "none", dynamic_sl_enabled: false, dynamic_sl_base: 0.01, dynamic_sl_atr_multiplier: 1.5 },
                    scoring_weights: { w_shape: 0.4, w_trend: 0.3, w_vol: 0.3 },
                  },
                } as BacktestConfig}
                onSubmit={handleRunOptimization}
              />

              {/* 优化进度显示 */}
              {isOptimizing && optimizationProgress && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-zinc-600 dark:text-zinc-400">
                      优化进行中...
                    </span>
                    <span className="font-mono text-zinc-500">
                      {optimizationProgress.current} / {optimizationProgress.total}
                    </span>
                  </div>
                  <Progress
                    value={(optimizationProgress.current / optimizationProgress.total) * 100}
                    className="h-2"
                  />
                  <p className="text-xs text-zinc-500 text-center">
                    状态：{optimizationProgress.status}
                  </p>
                </div>
              )}

              {/* 优化结果表格 */}
              {optimizationResults.length > 0 && (
                <OptimizationResultTable
                  results={optimizationResults}
                  objective={currentObjective}
                />
              )}
            </div>
          )}
        </div>
      </section>

      {/* 下半部分：任务队列 */}
      <section>
        <BacktestTaskList
          onRefresh={() => setRefreshTrigger((prev) => prev + 1)}
          onViewDetail={handleViewDetail}
        />
      </section>

      {/* 回测结果详情对话框 */}
      <BacktestResultDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        taskId={selectedTaskId}
      />
    </div>
  );
}
