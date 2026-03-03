import { useState, useEffect, useCallback } from "react";
import { ModeSelector } from "./ModeSelector";
import { WeightConfig } from "./WeightConfig";
import { ScoreDistributionChart } from "./ScoreDistributionChart";
import { ClassicModePanel } from "./ClassicModePanel";
import { ProgressiveModePanel } from "./ProgressiveModePanel";
import { ActionButtons } from "./ActionButtons";
import { useScoringConfig } from "./hooks/useScoringConfig";
import { useScorePreview } from "./hooks/useScorePreview";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

/**
 * 打分配置数据类型定义
 */
export interface ScoringConfigData {
  mode: "classic" | "progressive" | "custom";
  classic_shadow_min: number;
  classic_shadow_max: number;
  classic_body_good: number;
  classic_body_bad: number;
  classic_vol_min: number;
  classic_vol_max: number;
  classic_trend_max_dist: number;
  progressive_base_cap: number;
  progressive_shadow_threshold: number;
  progressive_shadow_bonus_rate: number;
  progressive_body_bonus_threshold: number;
  progressive_body_bonus_rate: number;
  progressive_doji_bonus: number;
  progressive_vol_threshold: number;
  progressive_vol_bonus_rate: number;
  progressive_extreme_vol_threshold: number;
  progressive_extreme_vol_bonus: number;
  progressive_penetration_rate: number;
  w_shape: number;
  w_trend: number;
  w_vol: number;
}

/**
 * ScoringConfigPanel - 打分配置中心根组件
 *
 * 提供可视化界面让用户配置打分参数，支持：
 * - 打分模式切换（经典/累进/自定义）
 * - 权重配置
 * - 参数调整
 * - 实时分数预览
 * - 配置保存/重置
 */
export function ScoringConfigPanel() {
  const {
    config,
    loading,
    error,
    fetchConfig,
    updateConfig,
    resetToDefaults,
  } = useScoringConfig();

  const { previewData, fetchPreview, submitting: previewSubmitting } =
    useScorePreview();

  const [modifiedConfig, setModifiedConfig] = useState<ScoringConfigData | null>(
    null
  );
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // 初始化加载配置
  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // 配置变更时更新预览（防抖）
  useEffect(() => {
    if (modifiedConfig) {
      const debounce = setTimeout(() => {
        fetchPreview(modifiedConfig);
      }, 500);
      return () => clearTimeout(debounce);
    }
  }, [modifiedConfig, fetchPreview]);

  /**
   * 处理配置变更
   */
  const handleConfigChange = useCallback((updates: Partial<ScoringConfigData>) => {
    setModifiedConfig((prev) => {
      // 基于当前有效配置（修改后的配置或原始配置）进行更新
      const base = prev || config;
      const updated = { ...base, ...updates };
      return updated;
    });
    setHasUnsavedChanges(true);
  }, [config]);

  /**
   * 处理保存配置
   */
  const handleSave = async () => {
    if (!modifiedConfig) return;

    try {
      await updateConfig(modifiedConfig);
      setHasUnsavedChanges(false);
      toast.success("配置已保存", {
        description: "新的打分配置已生效",
      });
    } catch (err) {
      toast.error("保存失败", {
        description: err instanceof Error ? err.message : "请检查网络或后端服务",
      });
    }
  };

  /**
   * 处理重置配置
   */
  const handleReset = () => {
    resetToDefaults();
    setModifiedConfig(null);
    setHasUnsavedChanges(false);
    toast.success("已重置为默认配置");
  };

  // 加载状态
  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  // 错误状态
  if (error) {
    return (
      <div className="text-center text-rose-500 p-8">
        <p className="font-medium">加载配置失败：{error}</p>
        <p className="text-sm text-rose-400 mt-2">请检查后端服务是否正常运行</p>
      </div>
    );
  }

  const activeConfig = modifiedConfig || config;

  return (
    <ScrollArea className="h-[calc(100vh-100px)]">
      <div className="p-6 space-y-6">
        {/* 标题和操作按钮 */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
              打分配置中心
            </h2>
            <p className="text-sm text-zinc-500 mt-1">
              可视化配置打分参数，实时预览分数分布
            </p>
          </div>
          <ActionButtons
            onSave={handleSave}
            onReset={handleReset}
            hasUnsavedChanges={hasUnsavedChanges}
            disabled={previewSubmitting}
          />
        </div>

        {/* 模式选择器 */}
        <Card>
          <CardContent className="p-0">
            <ModeSelector
              mode={activeConfig.mode}
              onModeChange={(mode) => handleConfigChange({ mode })}
            />
          </CardContent>
        </Card>

        {/* 权重配置 + 分数预览 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <WeightConfig
              w_shape={activeConfig.w_shape}
              w_trend={activeConfig.w_trend}
              w_vol={activeConfig.w_vol}
              onWeightsChange={(weights) =>
                handleConfigChange({
                  w_shape: weights.w_shape,
                  w_trend: weights.w_trend,
                  w_vol: weights.w_vol,
                })
              }
            />
          </Card>
          <Card>
            <ScoreDistributionChart
              data={previewData}
              loading={previewSubmitting}
            />
          </Card>
        </div>

        {/* 经典模式参数面板 */}
        {activeConfig.mode === "classic" && (
          <Card>
            <ClassicModePanel
              config={activeConfig}
              onChange={handleConfigChange}
            />
          </Card>
        )}

        {/* 累进模式参数面板 */}
        {activeConfig.mode === "progressive" && (
          <Card>
            <ProgressiveModePanel
              config={activeConfig}
              onChange={handleConfigChange}
            />
          </Card>
        )}

        {/* 自定义模式提示 */}
        {activeConfig.mode === "custom" && (
          <Card>
            <div className="p-8 text-center text-zinc-500">
              <p className="text-sm">自定义模式开发中...</p>
              <p className="text-xs mt-2">
                即将支持自定义公式系数配置
              </p>
            </div>
          </Card>
        )}
      </div>
    </ScrollArea>
  );
}

export default ScoringConfigPanel;
