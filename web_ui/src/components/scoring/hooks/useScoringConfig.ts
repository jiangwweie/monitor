import { useState, useCallback } from "react";
import type { ScoringConfigData } from "../index";

/**
 * 打分配置默认值
 */
const DEFAULT_CONFIG: ScoringConfigData = {
  mode: "classic",
  classic_shadow_min: 0.6,
  classic_shadow_max: 0.9,
  classic_body_good: 0.1,
  classic_body_bad: 0.5,
  classic_vol_min: 1.2,
  classic_vol_max: 3.0,
  classic_trend_max_dist: 0.03,
  progressive_base_cap: 30.0,
  progressive_shadow_threshold: 0.6,
  progressive_shadow_bonus_rate: 20.0,
  progressive_body_bonus_threshold: 0.1,
  progressive_body_bonus_rate: 100.0,
  progressive_doji_bonus: 5.0,
  progressive_vol_threshold: 2.0,
  progressive_vol_bonus_rate: 15.0,
  progressive_extreme_vol_threshold: 3.0,
  progressive_extreme_vol_bonus: 10.0,
  progressive_penetration_rate: 30.0,
  w_shape: 0.4,
  w_trend: 0.3,
  w_vol: 0.3,
};

/**
 * 打分配置管理 Hook
 * 提供配置的加载、更新、重置功能
 */
export function useScoringConfig() {
  const [config, setConfig] = useState<ScoringConfigData>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 从后端获取当前配置
   */
  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://localhost:8000/api/config/scoring");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setConfig(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * 更新配置到后端
   */
  const updateConfig = useCallback(async (updates: Partial<ScoringConfigData>) => {
    const res = await fetch("http://localhost:8000/api/config/scoring", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "更新失败" }));
      throw new Error(error.detail || "更新失败");
    }
    const data = await res.json();
    setConfig(data.config || { ...config, ...updates });
  }, [config]);

  /**
   * 重置为默认配置
   */
  const resetToDefaults = useCallback(() => {
    setConfig(DEFAULT_CONFIG);
  }, []);

  return {
    config,
    loading,
    error,
    fetchConfig,
    updateConfig,
    resetToDefaults,
  };
}
