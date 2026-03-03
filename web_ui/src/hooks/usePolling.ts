import { useState, useEffect, useCallback, useRef } from "react";

export interface UsePollingOptions<T> {
  /** 轮询间隔 (毫秒) */
  interval: number;
  /** 是否启用轮询 */
  enabled?: boolean;
  /** 数据加载成功回调 */
  onSuccess?: (data: T) => void;
  /** 数据加载失败回调 */
  onError?: (error: Error) => void;
  /** 立即执行一次 (默认 true) */
  immediate?: boolean;
}

export interface UsePollingReturn<T> {
  /** 加载的数据 */
  data: T | null;
  /** 加载状态 */
  loading: boolean;
  /** 错误信息 */
  error: Error | null;
  /** 手动刷新函数 */
  refresh: () => Promise<void>;
  /** 重置状态 */
  reset: () => void;
}

/**
 * 统一轮询 Hook
 *
 * @param fetcher 数据获取函数
 * @param options 配置选项
 * @returns { data, loading, error, refresh, reset }
 *
 * @example
 * ```ts
 * const { data, loading, error, refresh } = usePolling(
 *   async () => {
 *     const res = await fetch("/api/data");
 *     return await res.json();
 *   },
 *   {
 *     interval: 5000,
 *     enabled: true,
 *     onSuccess: (data) => console.log("Data updated:", data),
 *     onError: (error) => console.error("Polling error:", error),
 *   }
 * );
 * ```
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  options: UsePollingOptions<T>
): UsePollingReturn<T> {
  const {
    interval,
    enabled = true,
    onSuccess,
    onError,
    immediate = true,
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(immediate);
  const [error, setError] = useState<Error | null>(null);

  // 使用 ref 保存回调函数，避免依赖变化导致轮询重启
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  const fetcherRef = useRef(fetcher);

  // 更新 ref
  useEffect(() => {
    onSuccessRef.current = onSuccess;
  }, [onSuccess]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  // 核心数据获取函数
  const fetchData = useCallback(async (): Promise<T | null> => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
      onSuccessRef.current?.(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      onErrorRef.current?.(error);
      return null;
    }
  }, []);

  // 手动刷新函数
  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchData();
    setLoading(false);
  }, [fetchData]);

  // 重置函数
  const reset = useCallback(() => {
    setData(null);
    setLoading(false);
    setError(null);
  }, []);

  // 轮询逻辑
  useEffect(() => {
    if (!enabled) {
      return;
    }

    // 立即执行
    if (immediate) {
      fetchData().finally(() => {
        setLoading(false);
      });
    }

    // 设置轮询间隔
    const pollInterval = setInterval(() => {
      fetchData();
    }, interval);

    return () => {
      clearInterval(pollInterval);
    };
  }, [interval, enabled, immediate, fetchData]);

  return { data, loading, error, refresh, reset };
}
