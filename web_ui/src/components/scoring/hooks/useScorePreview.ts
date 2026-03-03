import { useState, useCallback } from "react";

/**
 * 分数预览 Hook
 * 提供基于当前配置的分数分布预览功能
 */
export function useScorePreview() {
  const [previewData, setPreviewData] = useState<{
    total_bars?: number;
    signals_found?: number;
    score_distribution?: Record<string, number>;
    tier_distribution?: Record<string, number>;
    sample_signals?: any[];
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 获取分数预览数据
   * @param config - 打分配置对象
   * @param symbol - 回测币种，默认 BTCUSDT
   * @param interval - 回测周期，默认 1h
   * @param limit - 回测 K 线数量，默认 500
   */
  const fetchPreview = useCallback(async (
    config: Record<string, any>,
    symbol = "BTCUSDT",
    interval = "1h",
    limit = 500
  ) => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("http://localhost:8000/api/config/scoring/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config,
          symbol,
          interval,
          limit,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPreviewData(data.data);
    } catch (err) {
      console.error("预览失败:", err);
      setError(err instanceof Error ? err.message : "预览失败");
    } finally {
      setSubmitting(false);
    }
  }, []);

  /**
   * 清除预览数据
   */
  const clearPreview = useCallback(() => {
    setPreviewData(null);
    setError(null);
  }, []);

  return {
    previewData,
    fetchPreview,
    submitting,
    error,
    clearPreview,
  };
}
