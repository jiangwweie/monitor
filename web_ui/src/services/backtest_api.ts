/**
 * Backtest Lab API Service
 * 封装 FMZ 回测引擎相关的 API 请求
 */

// ============ Type Definitions ============

export interface BacktestConfig {
  symbol: string;
  interval: string;
  start_date: string;
  end_date: string;
  fmz_config: {
    initial_balance: number;
    fee_maker: number;
    fee_taker: number;
    fee_denominator: number;
    slip_point: number;
  };
  strategy_config: {
    max_sl_dist: number;
    pinbar_config: {
      body_max_ratio: number;
      shadow_min_ratio: number;
      volatility_atr_multiplier: number;
      doji_threshold: number;
      doji_shadow_bonus: number;
      mtf_trend_filter_mode: string;
      dynamic_sl_enabled: boolean;
      dynamic_sl_base: number;
      dynamic_sl_atr_multiplier: number;
    };
    scoring_weights: {
      w_shape: number;
      w_trend: number;
      w_vol: number;
    };
  };
}

export interface BacktestRunResponse {
  taskId: string;
  status: string;
}

export interface BacktestTask {
  taskId: string;
  symbol: string;
  interval: string;
  startDate?: string;
  start_date?: string;
  endDate?: string;
  end_date?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  totalReturnPct?: number;
  progress?: number;
  createdAt?: number;
  created_at?: string;
  startedAt?: number;
  completedAt?: number;
  completed_at?: string;
  errorMessage?: string | null;
}

export interface BacktestResult {
  status: string;
  taskId?: string;
  stats: {
    initialBalance: number;
    finalBalance: number;
    totalReturnPct: number;
    totalPnl?: number;
    maxDrawdownPct: number;
    winRate: number;
    totalTrades: number;
    winCount?: number;
    lossCount?: number;
    profitFactor?: number;
    buyCount?: number;
    sellCount?: number;
    errorCount?: number;
    avgWin?: number;
    avgLoss?: number;
    consecutiveWins?: number;
    consecutiveLosses?: number;
    sharpeRatio?: number;
  };
  equityCurve: Array<{
    timestamp: number;
    balance: number;
    pnl?: number;
    equity?: number;
    utilization?: number;
  }>;
  klineData?: KlineBar[];
  tradeLogs?: Array<{
    action?: number;
    action_name?: string;
    timestamp: number;
    datetime?: string;
    price: number;
    amount: number;
    symbol?: string;
    profit?: number;
    runBalance?: number;
    kline_index?: number;
    direction?: string;        // "LONG" 或 "SHORT"
    realized_pnl?: number;     // 实现盈亏（CLOSE 记录有值，OPEN 记录为 0）
    fee?: number;              // 手续费
  }>;
  profitLogs?: Array<{
    timestamp: number;
    profit: number;
  }>;
  runtimeLogs?: string[];
  errorMessage?: string | null;
}

export interface KlineBar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ============ Utility Functions ============

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * 运行回测任务
 */
export async function runBacktest(config: BacktestConfig): Promise<BacktestRunResponse> {
  const response = await fetch(`${API_BASE}/api/backtest/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || '回测启动失败');
  }

  return response.json();
}

/**
 * 获取回测任务列表
 */
export async function getBacktestTasks(): Promise<BacktestTask[]> {
  const response = await fetch(`${API_BASE}/api/backtest/tasks`);

  if (!response.ok) {
    throw new Error('获取任务列表失败');
  }

  const data = await response.json();
  // 适配后端返回格式：{ tasks: [...], total: number }
  return data.tasks || data || [];
}

/**
 * 获取单个回测任务结果
 */
export async function getBacktestResult(taskId: string): Promise<BacktestResult> {
  const response = await fetch(`${API_BASE}/api/backtest/task/${taskId}/result`);

  if (!response.ok) {
    throw new Error('获取回测结果失败');
  }

  return response.json();
}

// ============ Utility Functions ============

/**
 * 获取支持的交易对列表
 */
export function getAvailableSymbols(): string[] {
  return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT'];
}

/**
 * 获取支持的周期列表
 */
export function getIntervals(): { value: string; label: string }[] {
  return [
    { value: '15m', label: '15 分钟' },
    { value: '1h', label: '1 小时' },
    { value: '4h', label: '4 小时' },
    { value: '1d', label: '1 天' },
  ];
}

/**
 * 格式化日期为 API 所需格式
 */
export function formatDateForApi(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * 格式化状态显示
 */
export function formatStatus(status: string): { label: string; color: string } {
  switch (status) {
    case 'pending':
    case 'pending_in_queue':
      return { label: '等待中', color: 'yellow' };
    case 'running':
      return { label: '运行中', color: 'blue' };
    case 'completed':
      return { label: '已完成', color: 'green' };
    case 'failed':
      return { label: '失败', color: 'red' };
    default:
      return { label: status, color: 'gray' };
  }
}

// ============ Optimization Types ============

export interface OptimizationRequest {
  base_config: Record<string, any>;
  params: Array<{ name: string; values: any[] }>;
  objective: string;
  top_n: number;
  max_combinations: number;
}

export interface OptimizationResultRow {
  rank: number;
  params: Record<string, any>;
  totalReturnPct: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
}

export interface OptimizationRunResponse {
  optTaskId: string;
  status: string;
  totalCombinations: number;
}

export interface OptimizationResult {
  status: string;
  optTaskId: string;
  totalCombinations: number;
  completedCombinations: number;
  results: OptimizationResultRow[];
}

// ============ Optimization API Functions ============

/**
 * 运行参数优化任务
 */
export async function runOptimization(config: OptimizationRequest): Promise<OptimizationRunResponse> {
  const response = await fetch(`${API_BASE}/api/backtest/optimize/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || '优化任务启动失败');
  }

  return response.json();
}

/**
 * 获取参数优化任务结果
 */
export async function getOptimizationResult(optTaskId: string): Promise<OptimizationResult> {
  const response = await fetch(`${API_BASE}/api/backtest/optimize/${optTaskId}/result`);

  if (!response.ok) {
    throw new Error('获取优化结果失败');
  }

  return response.json();
}
