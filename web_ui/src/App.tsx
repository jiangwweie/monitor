import { useState, useEffect, useMemo } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { Slider } from "@/components/ui/slider";
import { Toaster } from "@/components/ui/sonner";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import {
  Loader2,
  Settings2,
  Activity,
  Radar,
  Eye,
  EyeOff,
  Trash2,
  Clock,
  Wifi,
  Database,
  ShieldCheck,
  Zap,
  Wallet,
  ArrowUpDown,
  Filter,
} from "lucide-react";

import { ThemeProvider } from "@/components/theme-provider";
import { ModeToggle } from "@/components/mode-toggle";

const AVAILABLE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"];

export default function App() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [showWecomSecret, setShowWecomSecret] = useState(false);
  const [resetCountdown, setResetCountdown] = useState(
    60 - new Date().getSeconds(),
  );
  const [realtimePrices, setRealtimePrices] = useState<Record<string, number>>({});
  const [newSymbolInput, setNewSymbolInput] = useState("");

  // --- Data Models matching docs/api_contract.md ---
  const [systemStatus, setSystemStatus] = useState({
    is_connected: false,
    api_latency_ms: 0,
    api_weight_usage: 0,
    uptime: "0s",
  });

  const [signals, setSignals] = useState<any[]>([]);

  const [dashboardData, setDashboardData] = useState<{
    total_wallet_balance: number;
    available_balance: number;
    total_balance?: number;
    available_margin?: number;
    total_unrealized_pnl: number;
    current_positions_count: number;
    positions: any[];
  } | null>(null);

  const [config, setConfig] = useState({
    system_enabled: false,
    global_push_enabled: true,
    symbols: "BTCUSDT,ETHUSDT",
    monitor_intervals: ["15m", "1h", "4h", "1d"],
    risk_pct: 2.0,
    max_sl_dist: 3.5,
    max_leverage: 20,
    w_shape: 50,
    w_trend: 30,
    w_vol: 20,
    feishu_enabled: false,
    feishu_secret: "",
    wecom_enabled: false,
    wecom_secret: "",
    has_secret: false,
    has_wecom_secret: false,
    binance_api_key: "",
    binance_api_secret: "",
    has_binance_key: false,
    body_max_ratio: 0.25,
    shadow_min_ratio: 2.5,
    volatility_atr_multiplier: 1.2,
  });

  // --- Signal Table States ---
  const [filterSymbol, setFilterSymbol] = useState("ALL");
  const [filterDirection, setFilterDirection] = useState("ALL");
  const [filterTime, setFilterTime] = useState("ALL");
  const [filterInterval, setFilterInterval] = useState("ALL");
  const [selectedSignals, setSelectedSignals] = useState<Set<string>>(new Set());
  const [sortConfig, setSortConfig] = useState<{
    key: string;
    direction: "asc" | "desc";
  }>({ key: "timestamp", direction: "desc" });

  const [tableColumns, setTableColumns] = useState<Record<string, boolean>>({
    timestamp: true,
    symbol: true,
    direction: true,
    score: true,
    entry_price: true,
    shape: false, // Hidden by default
    ema: false,   // Hidden by default
    atr: false    // Hidden by default
  });

  const [selectedPositionDetail, setSelectedPositionDetail] = useState<any>(null);
  const [loadingPositionDetail, setLoadingPositionDetail] = useState(false);
  const [isPositionModalOpen, setIsPositionModalOpen] = useState(false);

  const handleOpenPositionDetail = async (symbol: string) => {
    setIsPositionModalOpen(true);
    setLoadingPositionDetail(true);
    try {
      const res = await fetch(`http://localhost:8000/api/account/position/detail/${symbol}`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success") {
          setSelectedPositionDetail(data.data);
        } else {
          toast.error("获取持仓详情失败");
        }
      } else {
        toast.error("网络异常或接口报错");
      }
    } catch (e) {
      toast.error("请求异常");
    } finally {
      setLoadingPositionDetail(false);
    }
  };

  // Load preferences once
  useEffect(() => {
    fetch("http://localhost:8000/api/preferences/view")
      .then(res => res.json())
      .then(data => {
        if (data.signals_table_columns && Object.keys(data.signals_table_columns).length > 0) {
          setTableColumns(prev => ({ ...prev, ...data.signals_table_columns }));
        } else {
          const local = localStorage.getItem("monitor_table_columns");
          if (local) setTableColumns(JSON.parse(local));
        }
      })
      .catch(() => {
        const local = localStorage.getItem("monitor_table_columns");
        if (local) setTableColumns(JSON.parse(local));
      });
  }, []);

  const handleToggleColumn = async (col: string, checked: boolean) => {
    const newCols = { ...tableColumns, [col]: checked };
    setTableColumns(newCols);
    localStorage.setItem("monitor_table_columns", JSON.stringify(newCols));
    fetch("http://localhost:8000/api/preferences/view", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signals_table_columns: newCols }),
    }).catch(console.error);
  };

  // --- Data Fetching & Polling ---
  useEffect(() => {
    const fetchFullData = async () => {
      try {
        const [configRes, statusRes, signalsRes, dashRes] = await Promise.all([
          fetch("http://localhost:8000/api/config").catch(() => null),
          fetch("http://localhost:8000/api/system/status").catch(() => null),
          fetch("http://localhost:8000/api/signals").catch(() => null),
          fetch("http://localhost:8000/api/account/dashboard").catch(() => null),
        ]);

        if (configRes && configRes.ok) {
          const data = await configRes.json();
          setConfig((prev) => ({
            ...prev,
            system_enabled: data.system_enabled ?? false,
            global_push_enabled: data.global_push_enabled ?? true,
            symbols: Array.isArray(data.active_symbols)
              ? data.active_symbols.join(",")
              : prev.symbols,
            monitor_intervals: data.monitor_intervals || prev.monitor_intervals,
            risk_pct: Number((parseFloat(data.risk_config?.risk_pct || 0) * 100).toFixed(2)),
            max_sl_dist: Number((parseFloat(data.risk_config?.max_sl_dist || 0) * 100).toFixed(2)),
            max_leverage: data.risk_config?.max_leverage || 20,
            w_shape: Math.round(parseFloat(data.scoring_weights?.w_shape || 0) * 100),
            w_trend: Math.round(parseFloat(data.scoring_weights?.w_trend || 0) * 100),
            w_vol: Math.round(parseFloat(data.scoring_weights?.w_vol || 0) * 100),
            feishu_enabled: data.webhook_settings?.feishu_enabled ?? false,
            wecom_enabled: data.webhook_settings?.wecom_enabled ?? false,
            has_secret: data.webhook_settings?.has_secret ?? false,
            has_wecom_secret: data.webhook_settings?.has_wecom_secret ?? false,
            has_binance_key: data.exchange_settings?.has_binance_key ?? false,
            body_max_ratio: data.pinbar_config?.body_max_ratio ?? 0.25,
            shadow_min_ratio: data.pinbar_config?.shadow_min_ratio ?? 2.5,
            volatility_atr_multiplier: data.pinbar_config?.volatility_atr_multiplier ?? 1.2,
          }));
        }

        if (statusRes && statusRes.ok) {
          const sysData = await statusRes.json();
          setSystemStatus((prev) => ({ ...prev, ...sysData }));
        }

        if (signalsRes && signalsRes.ok) {
          const sigData = await signalsRes.json();
          setSignals(Array.isArray(sigData?.items) ? sigData.items : []);
        }

        if (dashRes && dashRes.ok) {
          const dashData = await dashRes.json();
          if (dashData.status === "success" && dashData.data) {
            setDashboardData(dashData.data);
          } else {
            setDashboardData(null);
          }
        }
      } catch (error) {
        console.warn("Initial fetch failed");
      } finally {
        setLoading(false);
      }
    };

    const fetchLiveUpdates = async () => {
      try {
        const [statusRes, dashRes] = await Promise.all([
          fetch("http://localhost:8000/api/system/status").catch(() => null),
          fetch("http://localhost:8000/api/account/dashboard").catch(() => null),
        ]);

        if (statusRes && statusRes.ok) {
          const sysData = await statusRes.json();
          setSystemStatus((prev) => ({ ...prev, ...sysData }));
        }

        if (dashRes && dashRes.ok) {
          const dashData = await dashRes.json();
          if (dashData.status === "success" && dashData.data) {
            setDashboardData(dashData.data);
          }
        }
      } catch (error) {
        // Silently fail polling
      }
    };

    fetchFullData();

    // 5-second polling interval for LIVE UPDATES ONLY (status, dashboard)
    // config and signals are NOT refreshed automatically per user request.
    const interval = setInterval(fetchLiveUpdates, 5000);
    return () => clearInterval(interval);
  }, []);

  // --- Countdown Timer ---
  useEffect(() => {
    const timer = setInterval(() => {
      setResetCountdown(60 - new Date().getSeconds());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // --- Real-time Price Polling ---
  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const activeSymbols = config.symbols.split(",").map((s) => s.trim()).filter(Boolean);
        if (activeSymbols.length === 0) return;

        // Use Binance public API to fetch current prices
        const symbolQuery = `["${activeSymbols.join('","')}"]`;
        const res = await fetch(`https://api.binance.com/api/v3/ticker/price?symbols=${encodeURIComponent(symbolQuery)}`);

        if (res.ok) {
          const data = await res.json();
          const newPrices: Record<string, number> = {};
          data.forEach((item: any) => {
            newPrices[item.symbol] = Number(item.price);
          });
          setRealtimePrices(prev => ({ ...prev, ...newPrices }));
        }
      } catch (error) {
        // silently ignore network errors for public API polling
      }
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 3000); // 3 second polling
    return () => clearInterval(interval);
  }, [config.symbols]);

  // --- Derived Signals ---
  const sortedAndFilteredSignals = useMemo(() => {
    let result = [...signals];
    if (filterSymbol !== "ALL") {
      result = result.filter((s) => s.symbol === filterSymbol);
    }
    if (filterDirection !== "ALL") {
      result = result.filter((s) => s.direction === filterDirection);
    }

    if (filterTime !== "ALL") {
      const now = Date.now();
      const cutoff = filterTime === "1H" ? now - 3600000 : filterTime === "24H" ? now - 86400000 : 0;
      if (cutoff > 0) {
        result = result.filter((s) => new Date(s.timestamp).getTime() >= cutoff);
      }
    }

    if (filterInterval !== "ALL") {
      result = result.filter((s) => s.interval === filterInterval);
    }

    result.sort((a, b) => {
      let valA = a[sortConfig.key];
      let valB = b[sortConfig.key];
      if (valA < valB) return sortConfig.direction === "asc" ? -1 : 1;
      if (valA > valB) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
    return result;
  }, [signals, filterSymbol, filterDirection, filterTime, filterInterval, sortConfig]);

  const getSignalId = (s: any, idx: number) => s.id || `${s.timestamp}-${s.symbol}-${idx}`;

  // --- Handlers ---
  const handleToggleSelectAll = () => {
    if (selectedSignals.size === sortedAndFilteredSignals.length && sortedAndFilteredSignals.length > 0) {
      setSelectedSignals(new Set());
    } else {
      setSelectedSignals(new Set(sortedAndFilteredSignals.map((s, i) => getSignalId(s, i))));
    }
  };

  const handleToggleSelect = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedSignals);
    if (checked) newSelected.add(id);
    else newSelected.delete(id);
    setSelectedSignals(newSelected);
  };

  const handleDeleteSignals = async (idsToDelete: string[]) => {
    if (idsToDelete.length === 0) return;

    try {
      const res = await fetch("http://localhost:8000/api/signals", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signal_ids: idsToDelete }),
      });

      if (res.ok) {
        const idsSet = new Set(idsToDelete);
        setSignals(prev => prev.filter((s, i) => !idsSet.has(getSignalId(s, i))));
        const newSelected = new Set(selectedSignals);
        idsToDelete.forEach(id => newSelected.delete(id));
        setSelectedSignals(newSelected);
        toast.success(`已删除 ${idsToDelete.length} 条信号记录`);
      } else {
        throw new Error("Delete failed");
      }
    } catch (error) {
      toast.error("删除信号失败", { description: "请检查网络或后端服务状态" });
    }
  };

  const handleConfigChange = (field: string, value: any) => {
    if (field === "risk_pct" || field === "max_sl_dist") {
      setConfig((prev) => ({ ...prev, [field]: value }));
    } else {
      setConfig((prev) => ({ ...prev, [field]: value }));
    }
  };

  const handleSymbolToggle = (sym: string) => {
    const current = config.symbols
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (current.includes(sym)) {
      handleConfigChange("symbols", current.filter((s) => s !== sym).join(","));
    } else {
      handleConfigChange("symbols", [...current, sym].join(","));
    }
  };

  const handleWeightAutoBalance = (field: string, value: number[]) => {
    const newVal = value[0];

    setConfig((prev) => {
      // Get the fixed array of keys we are balancing
      const keys = ["w_shape", "w_trend", "w_vol"] as const;
      const otherKeys = keys.filter((k) => k !== field);

      const oldVal = prev[field as keyof typeof prev] as number;
      const diff = newVal - oldVal; // how much we changed
      const sumOthers = otherKeys.reduce(
        (acc, k) => acc + (prev[k as keyof typeof prev] as number),
        0,
      );

      let nextState = { ...prev, [field]: newVal };

      if (sumOthers === 0) {
        // If others were zero, split the remaining evenly
        const remainder = 100 - newVal;
        nextState[otherKeys[0]] = remainder / 2;
        nextState[otherKeys[1]] = remainder / 2;
      } else {
        // Subtract proportionally
        otherKeys.forEach((k) => {
          const current = prev[k as keyof typeof prev] as number;
          const ratio = current / sumOthers;
          nextState[k] = Math.max(0, current - diff * ratio);
        });
      }

      // Snap back to integers to ensure perfect sum
      const intShape = Math.round(nextState.w_shape as number);
      const intTrend = Math.round(nextState.w_trend as number);
      const intVol = 100 - intShape - intTrend; // force complete sum

      return {
        ...nextState,
        w_shape: intShape,
        w_trend: intTrend,
        w_vol: intVol,
      };
    });
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const payload = {
      system_enabled: Boolean(config.system_enabled),
      global_push_enabled: Boolean(config.global_push_enabled),
      active_symbols: config.symbols
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      monitor_intervals: config.monitor_intervals,
      risk_config: {
        risk_pct: Math.round(Number(config.risk_pct) * 100) / 10000.0,
        max_sl_dist: Math.round(Number(config.max_sl_dist) * 100) / 10000.0,
        max_leverage: Number(config.max_leverage),
      },
      scoring_weights: {
        w_shape: Number(config.w_shape) / 100.0,
        w_trend: Number(config.w_trend) / 100.0,
        w_vol: Number(config.w_vol) / 100.0,
      },
      webhook_settings: {
        feishu_enabled: Boolean(config.feishu_enabled),
        ...(config.feishu_secret
          ? { feishu_secret: config.feishu_secret }
          : {}),
        wecom_enabled: Boolean(config.wecom_enabled),
        ...(config.wecom_secret
          ? { wecom_secret: config.wecom_secret }
          : {}),
      },
      exchange_settings: {
        ...(config.binance_api_key
          ? { binance_api_key: config.binance_api_key }
          : {}),
        ...(config.binance_api_secret
          ? { binance_api_secret: config.binance_api_secret }
          : {}),
      },
      pinbar_config: {
        body_max_ratio: Number(config.body_max_ratio),
        shadow_min_ratio: Number(config.shadow_min_ratio),
        volatility_atr_multiplier: Number(config.volatility_atr_multiplier),
      },
    };

    try {
      const res = await fetch("http://localhost:8000/api/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        toast.success("配置已更新 (Configuration Saved)", {
          description: "新的风控与评分权重已生效。",
          className: "bg-zinc-900 border border-white/10 text-zinc-100",
        });
      } else {
        throw new Error("Save failed");
      }
    } catch (error) {
      toast.error("保存失败 (Save Failed)", {
        description: "后端服务离线或网络异常。",
        className: "bg-red-950 border border-red-900",
      });
    } finally {
      setTimeout(() => setSaving(false), 400);
    }
  };

  const getScoreBadgeColor = (score: number) => {
    if (score >= 90)
      return "bg-amber-500/20 text-amber-500 border-amber-500/30 font-bold";
    if (score >= 70) return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    return "bg-zinc-500/20 text-zinc-400 border-zinc-700";
  };

  const handleSortToggle = (key: string) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "desc" ? "asc" : "desc",
    }));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400 dark:text-zinc-600" />
      </div>
    );
  }

  return (
    <ThemeProvider defaultTheme="dark" storageKey="crypto-radar-theme">
      {/* === GLOBAL POSITION DETAIL MODAL === */}
      <Dialog open={isPositionModalOpen} onOpenChange={setIsPositionModalOpen}>
        <DialogContent className="sm:max-w-md bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-zinc-100 rounded-3xl p-6 shadow-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-blue-500" />
              持仓风控详情 ({selectedPositionDetail?.symbol})
            </DialogTitle>
          </DialogHeader>
          {loadingPositionDetail ? (
            <div className="flex justify-center items-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
            </div>
          ) : selectedPositionDetail ? (
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-zinc-50 dark:bg-black/20 p-3 rounded-2xl">
                  <p className="text-xs text-zinc-500 mb-1">方向与杠杆</p>
                  <p className={`font-mono text-xl font-bold ${selectedPositionDetail.direction === "LONG" ? "text-emerald-500" : "text-rose-500"}`}>
                    {selectedPositionDetail.direction === "LONG" ? "做多" : "做空"} <span className="text-sm font-medium text-zinc-500 ml-1">{selectedPositionDetail.leverage}x</span>
                  </p>
                </div>
                <div className="bg-zinc-50 dark:bg-black/20 p-3 rounded-2xl">
                  <p className="text-xs text-zinc-500 mb-1">仓位数量</p>
                  <p className="font-mono text-xl font-bold text-zinc-900 dark:text-zinc-100">{selectedPositionDetail.quantity}</p>
                </div>
              </div>

              <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl">
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-2">核心盈亏信息</p>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-zinc-500">仓位价值 (Value)</span>
                  <span className="font-mono text-zinc-900 dark:text-zinc-100">${Number(selectedPositionDetail.position_value || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-zinc-500">未实现盈亏 (Unrealized PnL)</span>
                  <span className={`font-mono font-bold ${Number(selectedPositionDetail.unrealized_pnl || 0) >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                    {Number(selectedPositionDetail.unrealized_pnl || 0) > 0 ? "+" : ""}{Number(selectedPositionDetail.unrealized_pnl || 0).toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-zinc-500">开单时间 (Open Time)</span>
                  <span className="font-mono text-zinc-900 dark:text-zinc-100">{new Date(selectedPositionDetail.open_time || 0).toLocaleString()}</span>
                </div>
              </div>

              <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl">
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-2">风控委托单</p>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-zinc-500">止盈价格 (TP)</span>
                  <span className="font-mono text-emerald-500">{selectedPositionDetail.take_profit_price ? `$${Number(selectedPositionDetail.take_profit_price).toFixed(4)}` : "未设置"}</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-zinc-500">止损价格 (SL)</span>
                  <span className="font-mono text-rose-500">{selectedPositionDetail.stop_loss_price ? `$${Number(selectedPositionDetail.stop_loss_price).toFixed(4)}` : "未设置"}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-8 text-center text-zinc-500 text-sm">无可用数据</div>
          )}
        </DialogContent>
      </Dialog>

      <div className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100 font-sans selection:bg-blue-500/30 pb-12 transition-colors duration-300">
        {/* Ambient Orbs */}
        <div className="fixed -top-32 -left-32 w-96 h-96 bg-blue-500/10 dark:bg-blue-900/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="fixed top-1/2 right-0 w-[500px] h-[500px] bg-purple-500/10 dark:bg-purple-900/5 rounded-full blur-[150px] pointer-events-none translate-x-1/3 -translate-y-1/2" />

        <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-12 relative z-10 animate-in fade-in slide-in-from-bottom-8 duration-700 ease-out">
          {/* Header Title */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white flex items-center gap-3">
                <Radar className="w-8 h-8 text-blue-500" />
                monitor
              </h1>
              <p className="text-zinc-500 dark:text-zinc-400 mt-1">
                加密货币信号监测系统
              </p>
            </div>

            <div className="flex items-center gap-4">
              <ModeToggle />

              {/* Global Status Pill */}
              <div className="hidden sm:flex items-center gap-4 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-md border border-black/5 dark:border-white/5 py-2 px-4 rounded-full text-sm shadow-sm dark:shadow-none">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2.5 w-2.5">
                    <span
                      className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${systemStatus.is_connected ? "bg-emerald-400" : "bg-red-400"}`}
                    ></span>
                    <span
                      className={`relative inline-flex rounded-full h-2.5 w-2.5 ${systemStatus.is_connected ? "bg-emerald-500" : "bg-red-500"}`}
                    ></span>
                  </span>
                  <span className="text-zinc-700 dark:text-zinc-300 font-medium whitespace-nowrap">
                    币安 WS
                  </span>
                </div>
                <div className="w-px h-4 bg-black/10 dark:bg-white/10" />
                <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400 whitespace-nowrap">
                  <Clock className="w-4 h-4" />
                  运行时间 {systemStatus.uptime}
                </div>
              </div>
            </div>
          </div>

          {/* Apple-style Tabs Layout */}
          <Tabs defaultValue="dashboard" className="w-full">
            <TabsList className="bg-white/50 dark:bg-white/5 border border-black/10 dark:border-white/10 rounded-2xl h-14 w-full justify-start p-1.5 mb-8 shadow-sm dark:shadow-none">
              <TabsTrigger
                value="dashboard"
                className="rounded-xl px-6 data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-800 data-[state=active]:text-zinc-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm dark:data-[state=active]:shadow-none transition-all"
              >
                <Activity className="w-4 h-4 mr-2" />
                仪表盘
              </TabsTrigger>
              <TabsTrigger
                value="signals"
                className="rounded-xl px-6 data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-800 data-[state=active]:text-zinc-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm dark:data-[state=active]:shadow-none transition-all"
              >
                <Radar className="w-4 h-4 mr-2" />
                信号雷达
              </TabsTrigger>
              <TabsTrigger
                value="positions"
                className="rounded-xl px-6 data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-800 data-[state=active]:text-zinc-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm dark:data-[state=active]:shadow-none transition-all"
              >
                <Wallet className="w-4 h-4 mr-2" />
                用户持仓
              </TabsTrigger>
              <TabsTrigger
                value="settings"
                className="rounded-xl px-6 data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-800 data-[state=active]:text-zinc-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm dark:data-[state=active]:shadow-none transition-all"
              >
                <Settings2 className="w-4 h-4 mr-2" />
                系统设置
              </TabsTrigger>
            </TabsList>

            {/* ==================== DASHBOARD TAB ==================== */}
            <TabsContent
              value="dashboard"
              className="space-y-6 animate-in fade-in duration-500"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* API Weight Progress Card */}
                <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-zinc-200">
                      <Wifi className="w-5 h-5 text-blue-400" />
                      API 权重消耗
                    </CardTitle>
                    <CardDescription>
                      币安接口频率与限流实时监控
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex justify-between items-end text-sm mb-2 text-zinc-500 dark:text-zinc-400">
                      <span>当前用量</span>
                      <div className="text-right">
                        <span className="text-xs mr-2 opacity-60">
                          重置倒计时: {resetCountdown}s
                        </span>
                        <span
                          className={
                            systemStatus.api_weight_usage > 80
                              ? "text-red-500 font-bold"
                              : "text-emerald-500 font-bold"
                          }
                        >
                          {systemStatus.api_weight_usage}%
                        </span>
                      </div>
                    </div>
                    <Progress
                      value={systemStatus.api_weight_usage}
                      className="h-3 bg-zinc-200 dark:bg-zinc-800"
                      indicatorColor={
                        systemStatus.api_weight_usage > 80
                          ? "bg-red-500"
                          : "bg-emerald-500"
                      }
                    />
                    <p className="text-xs text-zinc-500 mt-4 leading-relaxed">
                      （每分钟重置）限制保持在 80% 以内可确保高频执行的可靠性与
                      IP 安全。
                    </p>
                  </CardContent>
                </Card>

                {/* Server Stats */}
                <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
                  <CardHeader>
                    <CardTitle className="text-zinc-900 dark:text-zinc-200">
                      系统健康度
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div>
                      <p className="text-sm text-zinc-500 mb-1">API 延迟</p>
                      <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                        {systemStatus.api_latency_ms}{" "}
                        <span className="text-sm font-normal text-zinc-500">
                          ms
                        </span>
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-zinc-500 mb-1">连接状态</p>
                      <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                        {systemStatus.is_connected ? (
                          <>
                            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]" />{" "}
                            在线
                          </>
                        ) : (
                          <>
                            <span className="w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]" />{" "}
                            离线
                          </>
                        )}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Real-time Ticker */}
              <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-hide mt-6">
                {config.symbols.split(",").map(s => s.trim()).filter(Boolean).map(sym => (
                  <div key={sym} className="flex-none bg-white/50 dark:bg-zinc-900/50 backdrop-blur-md border border-zinc-200 dark:border-white/10 rounded-2xl px-5 py-3 shadow-sm min-w-[140px]">
                    <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1">{sym}</p>
                    <p className="text-lg font-bold text-zinc-900 dark:text-zinc-100 font-mono">
                      {realtimePrices[sym] ? `$${realtimePrices[sym].toFixed(realtimePrices[sym] < 10 ? 4 : 2)}` : '---'}
                    </p>
                  </div>
                ))}
              </div>

              {/* Account Dashboard Card (Full Width) */}
              <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden mt-4">
                <CardHeader className="pb-4 border-b border-zinc-200 dark:border-white/5 bg-black/5 dark:bg-black/20">
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-zinc-200">
                      <Wallet className="w-5 h-5 text-blue-400" />
                      账户与持仓
                    </CardTitle>
                    {dashboardData && (
                      <Badge
                        variant="outline"
                        className="bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700"
                      >
                        {dashboardData.current_positions_count} 个活跃持仓
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  {dashboardData ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-zinc-200 dark:divide-white/5">
                      {/* Balance Info */}
                      <div className="p-6 md:col-span-1 space-y-6">
                        <div>
                          <p className="text-sm text-zinc-500 mb-1">
                            账户总资产
                          </p>
                          <p className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
                            $
                            {Number(dashboardData.total_wallet_balance).toFixed(
                              2,
                            )}
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-zinc-500 mb-1">
                            可用保证金
                          </p>
                          <p className="text-xl font-semibold text-zinc-700 dark:text-zinc-300">
                            $
                            {Number(dashboardData.available_balance).toFixed(2)}
                          </p>
                        </div>
                        <div className="pt-4 border-t border-zinc-200 dark:border-white/10">
                          <p className="text-sm text-zinc-500 mb-1">
                            总计未实现盈亏
                          </p>
                          <p className={`text-xl font-bold tracking-tight ${dashboardData.total_unrealized_pnl >= 0 ? "text-emerald-500 dark:text-emerald-400" : "text-rose-500 dark:text-rose-400"}`}>
                            {dashboardData.total_unrealized_pnl > 0 ? "+" : ""}{Number(dashboardData.total_unrealized_pnl).toFixed(2)}
                          </p>
                        </div>
                      </div>

                      {/* Positions List */}
                      <div className="p-0 md:col-span-2">
                        {dashboardData.positions.length === 0 ? (
                          <div className="h-full flex items-center justify-center p-8 text-zinc-500 text-sm">
                            暂无持仓数据
                          </div>
                        ) : (
                          <div className="divide-y divide-zinc-200 dark:divide-white/5">
                            {dashboardData.positions.map((pos, idx) => (
                              <div
                                key={idx}
                                className="p-6 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
                              >
                                <div className="flex items-center gap-4">
                                  <div
                                    className={`w-12 h-12 rounded-2xl flex items-center justify-center font-bold text-lg ${pos.positionAmt > 0 ? "bg-emerald-500/10 text-emerald-500 dark:text-emerald-400" : "bg-rose-500/10 text-rose-500 dark:text-rose-400"}`}
                                  >
                                    {pos.positionAmt > 0 ? "多" : "空"}
                                  </div>
                                  <div>
                                    <div className="flex items-center gap-2 mb-1">
                                      <h4 className="font-semibold text-zinc-900 dark:text-zinc-100">
                                        {pos.symbol}
                                      </h4>
                                      <Badge
                                        variant="outline"
                                        className="bg-transparent border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400"
                                      >
                                        {pos.leverage}x
                                      </Badge>
                                    </div>
                                    <p className="text-xs text-zinc-500">
                                      仓位: {Math.abs(pos.positionAmt)} @{" "}
                                      {Number(pos.entryPrice).toFixed(4)}
                                    </p>
                                  </div>
                                </div>
                                <div className="text-right">
                                  <p
                                    className={`text-lg font-semibold tracking-tight ${pos.unrealized_pnl >= 0 ? "text-emerald-500 dark:text-emerald-400" : "text-rose-500 dark:text-rose-400"}`}
                                  >
                                    {pos.unrealized_pnl > 0 ? "+" : ""}
                                    {Number(pos.unrealized_pnl).toFixed(2)}
                                  </p>
                                  <p className="text-xs text-zinc-500">
                                    未实现盈亏
                                  </p>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    className="mt-2 h-7 text-xs border-zinc-200 dark:border-white/10 hover:bg-zinc-100 dark:hover:bg-white/5"
                                    onClick={() => handleOpenPositionDetail(pos.symbol)}
                                  >
                                    详情
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="p-12 text-center text-zinc-500">
                      <Wallet className="w-8 h-8 mx-auto mb-3 opacity-20" />
                      <p>账户资产数据暂时不可用。</p>
                      <p className="text-xs opacity-60 mt-1">
                        请在"系统设置"中确认币安 API Keys 配置并确保网络畅通。
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* ==================== POSITIONS TAB (USER POSITIONS) ==================== */}
            <TabsContent
              value="positions"
              className="space-y-6 animate-in fade-in duration-500"
            >
              <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden shadow-lg">
                <CardHeader className="pb-4 border-b border-zinc-200 dark:border-white/5 bg-black/5 dark:bg-black/20">
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-zinc-200">
                      <Wallet className="w-5 h-5 text-blue-400" /> 活跃持仓列表
                    </CardTitle>
                    {dashboardData && (
                      <Badge variant="outline" className="bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700">
                        共 {dashboardData.current_positions_count} 个
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="p-6">
                  {!dashboardData || dashboardData.positions.length === 0 ? (
                    <div className="h-64 flex flex-col items-center justify-center text-zinc-500 text-sm">
                      <Wallet className="w-10 h-10 mb-4 opacity-20" />
                      当前无活跃持仓
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {dashboardData.positions.map((pos, idx) => (
                        <div key={idx} className="bg-white/50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-white/10 rounded-2xl p-5 hover:bg-white dark:hover:bg-zinc-800 transition-colors shadow-sm">
                          <div className="flex justify-between items-start mb-4">
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${pos.positionAmt > 0 ? "bg-emerald-500/10 text-emerald-500 dark:text-emerald-400" : "bg-rose-500/10 text-rose-500 dark:text-rose-400"}`}>
                                {pos.positionAmt > 0 ? "多" : "空"}
                              </div>
                              <div>
                                <h4 className="font-bold text-zinc-900 dark:text-zinc-100 text-lg flex items-center gap-2">
                                  {pos.symbol} <Badge variant="secondary" className="text-[10px] h-4 px-1">{pos.leverage}x</Badge>
                                </h4>
                                <p className="text-xs text-zinc-500">仓位数量: {Math.abs(pos.positionAmt)}</p>
                              </div>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 text-xs border-zinc-200 dark:border-white/10"
                              onClick={() => handleOpenPositionDetail(pos.symbol)}
                            >
                              详情
                            </Button>
                          </div>
                          <div className="space-y-2 pt-4 border-t border-zinc-200 dark:border-white/10">
                            <div className="flex justify-between items-center">
                              <span className="text-xs text-zinc-500">入场价</span>
                              <span className="text-sm font-mono text-zinc-900 dark:text-zinc-100">${Number(pos.entryPrice).toFixed(4)}</span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-xs text-zinc-500">未实现盈亏</span>
                              <span className={`text-sm font-mono font-bold ${pos.unrealized_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                                {pos.unrealized_pnl > 0 ? "+" : ""}{Number(pos.unrealized_pnl).toFixed(2)}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* ==================== SIGNALS TAB ==================== */}
            <TabsContent
              value="signals"
              className="space-y-6 animate-in fade-in duration-500"
            >
              <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden shadow-lg">
                <div className="p-4 border-b border-zinc-200 dark:border-white/5 flex flex-wrap gap-4 items-center justify-between bg-black/5 dark:bg-black/20">
                  <div className="flex items-center gap-4">
                    <p className="text-sm font-medium text-zinc-800 dark:text-zinc-300 flex items-center gap-2">
                      <Filter className="w-4 h-4 text-zinc-400" />{" "}
                      信号过滤与筛选
                    </p>
                    <div className="h-4 w-px bg-zinc-300 dark:bg-zinc-700" />

                    {/* Top Filters */}
                    <Select
                      value={filterSymbol}
                      onValueChange={setFilterSymbol}
                    >
                      <SelectTrigger className="w-[120px] h-8 bg-transparent border-zinc-200 dark:border-zinc-800 text-xs text-zinc-800 dark:text-zinc-200">
                        <SelectValue placeholder="币种筛选" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ALL">全部币种</SelectItem>
                        {AVAILABLE_SYMBOLS.map((sym) => (
                          <SelectItem key={sym} value={sym}>
                            {sym}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select
                      value={filterDirection}
                      onValueChange={setFilterDirection}
                    >
                      <SelectTrigger className="w-[100px] h-8 bg-transparent border-zinc-200 dark:border-zinc-800 text-xs text-zinc-800 dark:text-zinc-200">
                        <SelectValue placeholder="方向筛选" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ALL">全部方向</SelectItem>
                        <SelectItem value="LONG">做多 (LONG)</SelectItem>
                        <SelectItem value="SHORT">做空 (SHORT)</SelectItem>
                      </SelectContent>
                    </Select>

                    <Select
                      value={filterTime}
                      onValueChange={setFilterTime}
                    >
                      <SelectTrigger className="w-[110px] h-8 bg-transparent border-zinc-200 dark:border-zinc-800 text-xs text-zinc-800 dark:text-zinc-200">
                        <SelectValue placeholder="时间范围" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ALL">全部时间</SelectItem>
                        <SelectItem value="1H">最近 1 小时</SelectItem>
                        <SelectItem value="24H">最近 24 小时</SelectItem>
                      </SelectContent>
                    </Select>

                    <Select
                      value={filterInterval}
                      onValueChange={setFilterInterval}
                    >
                      <SelectTrigger className="w-[110px] h-8 bg-transparent border-zinc-200 dark:border-zinc-800 text-xs text-zinc-800 dark:text-zinc-200">
                        <SelectValue placeholder="时间级别" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ALL">全部级别</SelectItem>
                        <SelectItem value="15m">15m</SelectItem>
                        <SelectItem value="1h">1h</SelectItem>
                        <SelectItem value="4h">4h</SelectItem>
                        <SelectItem value="1d">1d</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-center gap-2">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-zinc-500 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-900"
                        >
                          <Settings2 className="w-4 h-4 mr-2" />
                          视图设置
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-48 bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 rounded-2xl shadow-xl">
                        <DropdownMenuLabel className="text-xs text-zinc-500 font-semibold px-4 pt-3 pb-2 uppercase tracking-widest">
                          显示列配置
                        </DropdownMenuLabel>
                        <DropdownMenuSeparator className="bg-zinc-100 dark:bg-white/5" />
                        <DropdownMenuCheckboxItem checked={tableColumns.timestamp !== false} onCheckedChange={(c) => handleToggleColumn("timestamp", !!c)}>发生时间</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={tableColumns.symbol !== false} onCheckedChange={(c) => handleToggleColumn("symbol", !!c)}>币种级别</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={tableColumns.direction !== false} onCheckedChange={(c) => handleToggleColumn("direction", !!c)}>方向</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={tableColumns.score !== false} onCheckedChange={(c) => handleToggleColumn("score", !!c)}>综合评分</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={tableColumns.entry_price !== false} onCheckedChange={(c) => handleToggleColumn("entry_price", !!c)}>入场价</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={tableColumns.shape} onCheckedChange={(c) => handleToggleColumn("shape", !!c)}>影线占比</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={tableColumns.ema} onCheckedChange={(c) => handleToggleColumn("ema", !!c)}>EMA距离</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={tableColumns.atr} onCheckedChange={(c) => handleToggleColumn("atr", !!c)}>ATR波动率</DropdownMenuCheckboxItem>
                      </DropdownMenuContent>
                    </DropdownMenu>

                    {selectedSignals.size > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteSignals(Array.from(selectedSignals))}
                        className="text-rose-500 hover:text-rose-600 dark:text-rose-400 dark:hover:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        批量删除 ({selectedSignals.size})
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSignals([])}
                      className="text-zinc-500 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-900"
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      清空记录
                    </Button>
                  </div>
                </div>

                {/* Data Table implementation */}
                <div className="overflow-x-auto">
                  <Table className="min-w-full">
                    <TableHeader className="bg-zinc-100 dark:bg-zinc-900/40">
                      <TableRow className="hover:bg-transparent border-zinc-200 dark:border-white/5">
                        <TableHead className="w-[40px] pl-4">
                          <Checkbox
                            checked={sortedAndFilteredSignals.length > 0 && selectedSignals.size === sortedAndFilteredSignals.length}
                            onCheckedChange={handleToggleSelectAll}
                            className="border-zinc-400 dark:border-zinc-600"
                          />
                        </TableHead>
                        {tableColumns.timestamp !== false && (
                          <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400 w-[160px]">
                            <div
                              className="flex items-center gap-1 cursor-pointer hover:text-zinc-900 dark:hover:text-zinc-200 transition-colors"
                              onClick={() => handleSortToggle("timestamp")}
                            >
                              发生时间{" "}
                              <ArrowUpDown className="w-3 h-3 opacity-50" />
                            </div>
                          </TableHead>
                        )}
                        {tableColumns.symbol !== false && (
                          <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                            币种级别
                          </TableHead>
                        )}
                        {tableColumns.direction !== false && (
                          <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                            方向
                          </TableHead>
                        )}
                        {tableColumns.score !== false && (
                          <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                            <div
                              className="flex items-center gap-1 cursor-pointer hover:text-zinc-900 dark:hover:text-zinc-200 transition-colors"
                              onClick={() => handleSortToggle("score")}
                            >
                              综合评分{" "}
                              <ArrowUpDown className="w-3 h-3 opacity-50" />
                            </div>
                          </TableHead>
                        )}
                        {tableColumns.entry_price !== false && (
                          <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                            入场价
                          </TableHead>
                        )}
                        {tableColumns.shape && (
                          <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                            影线占比
                          </TableHead>
                        )}
                        {tableColumns.ema && (
                          <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                            EMA距离
                          </TableHead>
                        )}
                        {tableColumns.atr && (
                          <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                            ATR波动率
                          </TableHead>
                        )}
                        <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400 text-right pr-4">
                          操作
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortedAndFilteredSignals.length === 0 ? (
                        <TableRow>
                          <TableCell
                            colSpan={7}
                            className="h-32 text-center text-zinc-500"
                          >
                            暂无符合条件的信号记录
                          </TableCell>
                        </TableRow>
                      ) : (
                        sortedAndFilteredSignals.map((sig, idx) => {
                          const sigId = getSignalId(sig, idx);
                          return (
                            <TableRow
                              key={sigId}
                              className="hover:bg-zinc-100/50 dark:hover:bg-white/[0.04] border-zinc-200 dark:border-white/5 transition-colors group"
                            >
                              <TableCell className="pl-4">
                                <Checkbox
                                  checked={selectedSignals.has(sigId)}
                                  onCheckedChange={(c) => handleToggleSelect(sigId, !!c)}
                                  className="border-zinc-300 dark:border-zinc-700 data-[state=checked]:bg-blue-500 data-[state=checked]:text-white"
                                />
                              </TableCell>
                              {tableColumns.timestamp !== false && (
                                <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm whitespace-nowrap">
                                  {new Date(sig.timestamp).toLocaleString()}
                                </TableCell>
                              )}
                              {tableColumns.symbol !== false && (
                                <TableCell className="font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5 pt-4">
                                  {sig.symbol}
                                  {sig.interval && <Badge variant="secondary" className="text-[10px] px-1 h-4">({sig.interval})</Badge>}
                                </TableCell>
                              )}
                              {tableColumns.direction !== false && (
                                <TableCell>
                                  <Badge
                                    variant="outline"
                                    className={`font-medium ${sig.direction === "LONG" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"}`}
                                  >
                                    {sig.direction === "LONG" ? "做多" : "做空"}
                                  </Badge>
                                </TableCell>
                              )}
                              {tableColumns.score !== false && (
                                <TableCell>
                                  <Badge
                                    variant="outline"
                                    className={`min-w-[4rem] justify-center ${getScoreBadgeColor(sig.score)}`}
                                  >
                                    {sig.score} Pts
                                  </Badge>
                                </TableCell>
                              )}
                              {tableColumns.entry_price !== false && (
                                <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">
                                  ${Number(sig.entry_price || sig.price || 0).toFixed(4)}
                                </TableCell>
                              )}
                              {tableColumns.shape && (
                                <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">
                                  {Number(sig.score_details?.shape || 0).toFixed(1)}
                                </TableCell>
                              )}
                              {tableColumns.ema && (
                                <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">
                                  {Number(sig.ema_distance || 0).toFixed(2)}
                                </TableCell>
                              )}
                              {tableColumns.atr && (
                                <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">
                                  {Number(sig.volatility_atr || 0).toFixed(2)}
                                </TableCell>
                              )}
                              <TableCell className="text-right pr-4">
                                <Dialog>
                                  <DialogTrigger asChild>
                                    <Button variant="ghost" size="sm" className="h-8 text-blue-500 hover:text-blue-600 bg-blue-500/10 hover:bg-blue-500/20">
                                      详情
                                    </Button>
                                  </DialogTrigger>
                                  <DialogContent className="sm:max-w-sm bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-zinc-100 rounded-3xl p-6 shadow-2xl">
                                    <DialogHeader>
                                      <DialogTitle className="flex items-center gap-2">
                                        <Radar className="w-5 h-5 text-blue-500" />
                                        指标详情 ({sig.symbol})
                                      </DialogTitle>
                                    </DialogHeader>
                                    <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-zinc-300 dark:scrollbar-thumb-zinc-700">
                                      <div className="grid grid-cols-2 gap-4">
                                        <div className="bg-zinc-50 dark:bg-black/20 p-3 rounded-2xl">
                                          <p className="text-xs text-zinc-500 mb-1">综合评分 (Score)</p>
                                          <p className="font-mono text-xl font-bold">{sig.score}</p>
                                        </div>
                                        <div className="bg-zinc-50 dark:bg-black/20 p-3 rounded-2xl">
                                          <p className="text-xs text-zinc-500 mb-1">操作方向 (Direction)</p>
                                          <p className={`font-medium ${sig.direction === "LONG" ? "text-emerald-500" : "text-rose-500"}`}>{sig.direction === "LONG" ? "做多 (LONG)" : "做空 (SHORT)"}</p>
                                        </div>
                                      </div>

                                      <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl">
                                        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-2">价格与风险控制参数</p>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">建议入场价 (Entry)</span>
                                          <span className="font-mono text-zinc-900 dark:text-zinc-100">${Number(sig.entry_price || sig.price || 0).toFixed(4)}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">止损价 (Stop Loss)</span>
                                          <span className="font-mono text-rose-500">${Number(sig.stop_loss || 0).toFixed(4)}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">第一止盈价 (TP1)</span>
                                          <span className="font-mono text-emerald-500">${Number(sig.take_profit_1 || 0).toFixed(4)}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">止损距离比例 (SL Dist)</span>
                                          <span className="font-mono text-zinc-900 dark:text-zinc-100">{(Number(sig.sl_distance_pct || 0) * 100).toFixed(2)}%</span>
                                        </div>
                                      </div>

                                      <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl">
                                        <div className="flex justify-between items-center text-sm pt-2">
                                          <span className="text-zinc-500 font-semibold text-amber-600 dark:text-amber-500">MTF 趋势校验 (MTF Trend Check)</span>
                                          <span className="font-medium text-amber-600 dark:text-amber-500">已通过上级周期方向校验</span>
                                        </div>
                                        <div className="w-full h-px bg-zinc-200 dark:bg-zinc-800 my-2" />
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">信号触发原因 (Reason)</span>
                                          <span className="font-medium text-blue-500">{sig.reason || "Pinbar+EMA60"}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">形态完美度 (Shape Score)</span>
                                          <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(sig.score_details?.shape ?? 0).toFixed(1)}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">趋势顺应度 (Trend Score)</span>
                                          <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(sig.score_details?.trend ?? 0).toFixed(1)}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">波动率健康度 (Vol Score)</span>
                                          <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(sig.score_details?.vol ?? 0).toFixed(1)}</span>
                                        </div>
                                        <div className="w-full h-px bg-zinc-200 dark:bg-zinc-800 my-2" />
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">引线比例 (Shadow Ratio)</span>
                                          <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(sig.shadow_ratio || 0).toFixed(2)}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">EMA 距离 (EMA Dist)</span>
                                          <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(sig.ema_distance || 0).toFixed(2)}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                          <span className="text-zinc-500">真实波动幅度 (ATR)</span>
                                          <span className="font-mono text-zinc-900 dark:text-zinc-100">{Number(sig.volatility_atr || 0).toFixed(2)}</span>
                                        </div>
                                      </div>
                                    </div>
                                  </DialogContent>
                                </Dialog>
                                <Button variant="ghost" size="icon" onClick={() => handleDeleteSignals([sigId])} className="h-8 w-8 text-rose-500/70 hover:text-rose-500 hover:bg-rose-500/10 ml-2">
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          );
                        })
                      )}
                    </TableBody>
                  </Table>
                </div>
              </Card>
            </TabsContent>

            {/* ==================== SETTINGS TAB ==================== */}
            <TabsContent
              value="settings"
              className="animate-in fade-in duration-500"
            >
              <form
                onSubmit={handleSaveConfig}
                className="grid grid-cols-1 md:grid-cols-2 gap-6"
              >
                {/* Column 1 */}
                <div className="space-y-6">
                  {/* Exchange Integration */}
                  <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
                        <Database className="w-5 h-5" /> 交易所配置
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="space-y-3">
                        <Label className="text-zinc-700 dark:text-zinc-300">
                          监控币种 (可多选)
                        </Label>
                        <div className="flex flex-wrap gap-2 items-center">
                          {config.symbols.split(",").filter(Boolean).map((sym) => {
                            return (
                              <Badge
                                key={sym}
                                onClick={() => handleSymbolToggle(sym)}
                                className="cursor-pointer px-3 py-1.5 text-sm font-medium transition-all bg-blue-500 text-white hover:bg-blue-600 border-transparent shadow-md"
                                variant="outline"
                              >
                                {sym} ✕
                              </Badge>
                            );
                          })}
                          <div className="flex items-center gap-1 ml-2 bg-zinc-100 dark:bg-zinc-800/50 rounded-full pr-1">
                            <Input
                              value={newSymbolInput}
                              onChange={(e) => setNewSymbolInput(e.target.value.toUpperCase())}
                              placeholder="新币种 (如 SOLUSDT)"
                              className="w-32 h-8 text-xs border-none bg-transparent focus-visible:ring-0 px-3 shadow-none"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' && newSymbolInput.trim()) {
                                  e.preventDefault();
                                  if (!config.symbols.includes(newSymbolInput.trim())) {
                                    handleConfigChange("symbols", config.symbols + (config.symbols ? "," : "") + newSymbolInput.trim());
                                  }
                                  setNewSymbolInput("");
                                }
                              }}
                            />
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-3 text-xs rounded-full bg-white dark:bg-zinc-700 shadow-sm hover:text-blue-500"
                              onClick={(e) => {
                                e.preventDefault();
                                if (newSymbolInput.trim() && !config.symbols.includes(newSymbolInput.trim())) {
                                  handleConfigChange("symbols", config.symbols + (config.symbols ? "," : "") + newSymbolInput.trim());
                                }
                                setNewSymbolInput("");
                              }}>
                              + 添加
                            </Button>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3 pt-4 border-t border-zinc-200 dark:border-white/10">
                        <Label className="text-zinc-700 dark:text-zinc-300">
                          监控级别 (多周期 MTF)
                        </Label>
                        <div className="flex flex-col gap-3">
                          <div className="flex flex-wrap gap-2 items-center">
                            {["15m", "1h", "4h", "1d"].map((interval) => {
                              const isSelected = Array.isArray(config.monitor_intervals)
                                ? config.monitor_intervals.includes(interval)
                                : Object.keys(config.monitor_intervals).includes(interval);
                              return (
                                <Badge
                                  key={interval}
                                  onClick={() => {
                                    let newIntervals;
                                    if (Array.isArray(config.monitor_intervals)) {
                                      if (isSelected && config.monitor_intervals.length === 1) {
                                        toast.error("至少保留一个监控级别");
                                        return;
                                      }
                                      newIntervals = isSelected
                                        ? config.monitor_intervals.filter(i => i !== interval)
                                        : [...config.monitor_intervals, interval];
                                    } else {
                                      const keys = Object.keys(config.monitor_intervals);
                                      if (isSelected && keys.length === 1) {
                                        toast.error("至少保留一个监控级别");
                                        return;
                                      }
                                      newIntervals = { ...(config.monitor_intervals as any) };
                                      if (isSelected) {
                                        delete newIntervals[interval];
                                      } else {
                                        newIntervals[interval] = { use_trend_filter: true };
                                      }
                                    }
                                    handleConfigChange("monitor_intervals", newIntervals);
                                  }}
                                  className={`cursor-pointer px-4 py-1.5 text-sm font-medium transition-all shadow-sm ${isSelected ? "bg-blue-500 text-white hover:bg-blue-600 border-transparent shadow-md" : "bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-700"}`}
                                  variant={isSelected ? "default" : "outline"}
                                >
                                  {interval} {isSelected && "✓"}
                                </Badge>
                              );
                            })}
                          </div>

                          {/* Render Trend Filter Switches for selected intervals */}
                          {!Array.isArray(config.monitor_intervals) && Object.keys(config.monitor_intervals).length > 0 && (
                            <div className="mt-3 space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl border border-zinc-200 dark:border-white/5">
                              <p className="text-xs font-medium text-zinc-500 mb-2 uppercase">趋势过滤设置</p>
                              {Object.entries(config.monitor_intervals).map(([interval, intervalCfg]: [string, any]) => (
                                <div key={interval} className="flex justify-between items-center">
                                  <div className="flex items-center gap-2">
                                    <Badge variant="outline" className="w-12 justify-center text-xs">{interval}</Badge>
                                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">参考大级别趋势</span>
                                  </div>
                                  <Switch
                                    checked={intervalCfg.use_trend_filter}
                                    onCheckedChange={(checked) => {
                                      const newIntervals = {
                                        ...config.monitor_intervals,
                                        [interval]: { ...intervalCfg, use_trend_filter: checked }
                                      };
                                      handleConfigChange("monitor_intervals", newIntervals);

                                      // Auto-save instantly
                                      fetch("http://localhost:8000/api/config", {
                                        method: "PUT",
                                        headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify({ monitor_intervals: newIntervals }),
                                      }).then(res => {
                                        if (res.ok) toast.success(`${interval} 趋势过滤状态已保存`);
                                      }).catch(() => toast.error("配置保存失败"));
                                    }}
                                  />
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500 mt-2 bg-blue-500/5 p-3 rounded-xl border border-blue-500/10 dark:border-blue-500/20">
                          <strong className="text-blue-600 dark:text-blue-400">MTF 趋势过滤说明:</strong><br />
                          • 15m 信号必须符合 1h 级别的大趋势方向。<br />
                          • 1h 信号必须符合 4h 级别的大趋势方向。<br />
                          • 4h 及 1d 信号独立判断，无上级约束。
                        </p>
                      </div>

                      <div className="space-y-4 pt-4 border-t border-zinc-200 dark:border-white/10">
                        <Label className="text-zinc-700 dark:text-zinc-300">
                          币安 API Key (仅供读取)
                        </Label>
                        <Input
                          value={config.binance_api_key}
                          onChange={(e) =>
                            handleConfigChange(
                              "binance_api_key",
                              e.target.value,
                            )
                          }
                          className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white placeholder:text-zinc-400 font-mono"
                          placeholder={
                            config.has_binance_key
                              ? "******** (目前密钥已配置成功)"
                              : "输入币安 API Key"
                          }
                        />

                        <Label className="text-zinc-700 dark:text-zinc-300">
                          币安 API Secret
                        </Label>
                        <Input
                          type="password"
                          value={config.binance_api_secret}
                          onChange={(e) =>
                            handleConfigChange(
                              "binance_api_secret",
                              e.target.value,
                            )
                          }
                          className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white placeholder:text-zinc-400 font-mono"
                          placeholder={
                            config.has_binance_key
                              ? "******** (加密隐藏)"
                              : "输入币安 API Secret"
                          }
                        />
                        <p className="text-xs text-zinc-500 mt-2">
                          安全提示:
                          密钥将在后台强制加密存储，请确保该秘钥仅开启只读权限，严禁开启交易与提现权限。
                        </p>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Pinbar Strategy Settings */}
                  <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
                        <Zap className="w-5 h-5 text-amber-500" /> Pinbar 策略参数
                      </CardTitle>
                      <CardDescription>
                        调整 K 线形态识别的核心比例与阈值
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <Label className="text-zinc-700 dark:text-zinc-300">实体最大比例 (Body Ratio)</Label>
                          <span className="font-mono text-sm font-bold text-blue-500">{(Number(config.body_max_ratio) * 100).toFixed(0)}%</span>
                        </div>
                        <Slider
                          value={[Number(config.body_max_ratio) * 100]}
                          max={100}
                          step={1}
                          onValueChange={(val) => handleConfigChange("body_max_ratio", val[0] / 100)}
                          className="py-4"
                        />
                        <p className="text-xs text-zinc-500">实体部分占整根 K 线长度的最大比例。越小越苛刻。</p>
                      </div>

                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <Label className="text-zinc-700 dark:text-zinc-300">影线最小比例 (Shadow Ratio)</Label>
                          <span className="font-mono text-sm font-bold text-blue-500">{Number(config.shadow_min_ratio).toFixed(1)}x</span>
                        </div>
                        <Slider
                          value={[Number(config.shadow_min_ratio) * 10]}
                          max={50}
                          step={1}
                          onValueChange={(val) => handleConfigChange("shadow_min_ratio", val[0] / 10)}
                          className="py-4"
                        />
                        <p className="text-xs text-zinc-500">单边影线长度与实体的最小倍数关系。越大影线越长。</p>
                      </div>

                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <Label className="text-zinc-700 dark:text-zinc-300">波幅 ATR 乘数 (Volatility)</Label>
                          <span className="font-mono text-sm font-bold text-blue-500">{Number(config.volatility_atr_multiplier).toFixed(1)}x</span>
                        </div>
                        <Slider
                          value={[Number(config.volatility_atr_multiplier) * 10]}
                          max={50}
                          step={1}
                          onValueChange={(val) => handleConfigChange("volatility_atr_multiplier", val[0] / 10)}
                          className="py-4"
                        />
                        <p className="text-xs text-zinc-500">K 线总长度与平均 ATR 的比值。用于过滤极小波动。</p>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Risk Limits */}
                  <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
                        <ShieldCheck className="w-5 h-5" /> 风控参数
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-zinc-700 dark:text-zinc-300">
                            单笔风险度 (%)
                          </Label>
                          <Input
                            type="number"
                            step="0.01"
                            value={config.risk_pct}
                            onChange={(e) =>
                              handleConfigChange("risk_pct", e.target.value)
                            }
                            onBlur={(e) =>
                              handleConfigChange(
                                "risk_pct",
                                Number(
                                  parseFloat(e.target.value || "0").toFixed(2),
                                ),
                              )
                            }
                            className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white font-mono"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-zinc-700 dark:text-zinc-300">
                            最大止损距离 (%)
                          </Label>
                          <Input
                            type="number"
                            step="0.01"
                            value={config.max_sl_dist}
                            onChange={(e) =>
                              handleConfigChange("max_sl_dist", e.target.value)
                            }
                            onBlur={(e) =>
                              handleConfigChange(
                                "max_sl_dist",
                                Number(
                                  parseFloat(e.target.value || "0").toFixed(2),
                                ),
                              )
                            }
                            className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white font-mono"
                          />
                        </div>
                        <div className="space-y-2 col-span-2">
                          <Label className="text-zinc-700 dark:text-zinc-300">
                            最大杠杆倍数 (x)
                          </Label>
                          <Input
                            type="number"
                            value={config.max_leverage}
                            onChange={(e) =>
                              handleConfigChange(
                                "max_leverage",
                                Number(e.target.value),
                              )
                            }
                            className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white"
                          />
                        </div>
                      </div>
                      <div className="flex items-center justify-between pt-4 border-t border-zinc-200 dark:border-white/10 mt-4">
                        <div>
                          <Label className="text-base text-zinc-900 dark:text-zinc-200 flex items-center gap-2">
                            全局推送开关
                            <Badge variant="outline" className="text-[10px] h-5 px-1.5 bg-blue-500/10 text-blue-500 border-blue-500/20">生效中</Badge>
                          </Label>
                          <p className="text-xs text-zinc-500 mt-1">
                            控制所有告警通道 (飞书/企微) 的总闸
                          </p>
                        </div>
                        <Switch
                          checked={config.global_push_enabled}
                          onCheckedChange={(c) =>
                            handleConfigChange("global_push_enabled", c)
                          }
                        />
                      </div>
                      <div className="flex items-center justify-between pt-4">
                        <div>
                          <Label className="text-base text-zinc-400 dark:text-zinc-500 flex items-center gap-2">
                            自动下单交易
                            <Badge variant="outline" className="text-[10px] h-5 px-1.5 bg-zinc-500/10 text-zinc-500 border-zinc-500/20">仅监测模式</Badge>
                          </Label>
                          <p className="text-xs text-zinc-500 mt-1">
                            当前系统仅作为信号监测工具，自动交易已禁用
                          </p>
                        </div>
                        <Switch
                          checked={false}
                          disabled
                        />
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Column 2 */}
                <div className="space-y-6">
                  {/* Scoring Engine Weights */}
                  <Card className="backdrop-blur-xl bg-gradient-to-br from-white to-zinc-50 dark:from-zinc-900 dark:to-zinc-950 border border-zinc-200 dark:border-white/10 rounded-3xl shadow-lg ring-1 ring-black/5 dark:ring-white/5 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-full h-1 bg-gradient-to-r from-blue-500 via-purple-500 to-amber-500 opacity-50" />
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
                        <Zap className="w-5 h-5 text-amber-500" /> AI 评分权重
                      </CardTitle>
                      <CardDescription>
                        调整各维度打分的考量基准（互嵌联动以维持 100%）。
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6 pt-4">
                      <div className="space-y-3">
                        <div className="flex justify-between items-end">
                          <Label className="text-zinc-700 dark:text-zinc-300">
                            形态完美度 (影线占比)
                          </Label>
                          <span className="text-xs font-mono text-zinc-500">
                            {config.w_shape}%
                          </span>
                        </div>
                        <Slider
                          value={[config.w_shape]}
                          onValueChange={(v) =>
                            handleWeightAutoBalance("w_shape", v)
                          }
                          max={100}
                          step={1}
                          className="py-2"
                        />
                      </div>

                      <div className="space-y-3">
                        <div className="flex justify-between items-end">
                          <Label className="text-zinc-700 dark:text-zinc-300">
                            趋势顺应度 (EMA距离)
                          </Label>
                          <span className="text-xs font-mono text-zinc-500">
                            {config.w_trend}%
                          </span>
                        </div>
                        <Slider
                          value={[config.w_trend]}
                          onValueChange={(v) =>
                            handleWeightAutoBalance("w_trend", v)
                          }
                          max={100}
                          step={1}
                          className="py-2"
                        />
                      </div>

                      <div className="space-y-3">
                        <div className="flex justify-between items-end">
                          <Label className="text-zinc-700 dark:text-zinc-300">
                            波动率健康度 (ATR)
                          </Label>
                          <span className="text-xs font-mono text-zinc-500">
                            {config.w_vol}%
                          </span>
                        </div>
                        <Slider
                          value={[config.w_vol]}
                          onValueChange={(v) =>
                            handleWeightAutoBalance("w_vol", v)
                          }
                          max={100}
                          step={1}
                          className="py-2"
                        />
                      </div>
                    </CardContent>
                    <CardFooter className="bg-white/[0.02] border-t border-zinc-200 dark:border-white/5 py-3">
                      <p className="text-xs text-zinc-500 w-full text-center">
                        总评分 = (权重1 × 形态) + (权重2 × 趋势) + (权重3 ×
                        波动)
                      </p>
                    </CardFooter>
                  </Card>

                  {/* Notifications */}
                  <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
                    <CardHeader>
                      <CardTitle className="text-lg text-zinc-900 dark:text-white">
                        告警与通知
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <Label className="text-zinc-900 dark:text-zinc-300">
                            飞书机器人推送
                          </Label>
                          <Switch
                            checked={config.feishu_enabled}
                            onCheckedChange={(c) => handleConfigChange("feishu_enabled", c)}
                          />
                        </div>
                        <div className="relative pb-4 border-b border-zinc-200 dark:border-white/5">
                          <Input
                            type={showSecret ? "text" : "password"}
                            value={config.feishu_secret}
                            onChange={(e) => handleConfigChange("feishu_secret", e.target.value)}
                            className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 pr-10 text-zinc-900 dark:text-white"
                            placeholder={config.has_secret ? "•••••••••••••••• (已保存)" : "输入飞书 Webhook 密钥..."}
                          />
                          <button
                            type="button"
                            onClick={() => setShowSecret(!showSecret)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                          >
                            {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>

                        <div className="flex items-center justify-between pt-2">
                          <Label className="text-zinc-900 dark:text-zinc-300">
                            企业微信推送
                          </Label>
                          <Switch
                            checked={config.wecom_enabled}
                            onCheckedChange={(c) => handleConfigChange("wecom_enabled", c)}
                          />
                        </div>
                        <div className="relative pb-2">
                          <Input
                            type={showWecomSecret ? "text" : "password"}
                            value={config.wecom_secret}
                            onChange={(e) => handleConfigChange("wecom_secret", e.target.value)}
                            className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 pr-10 text-zinc-900 dark:text-white"
                            placeholder={config.has_wecom_secret ? "•••••••••••••••• (已保存)" : "输入企微 Webhook 密钥..."}
                          />
                          <button
                            type="button"
                            onClick={() => setShowWecomSecret(!showWecomSecret)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 mb-1"
                          >
                            {showWecomSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Submit Button spanning column */}
                  <Button
                    type="submit"
                    disabled={saving}
                    className="w-full h-14 rounded-2xl bg-zinc-900 text-white dark:bg-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all text-base font-semibold shadow-xl shadow-black/5 dark:shadow-white/5"
                  >
                    {saving ? (
                      <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    ) : null}
                    {saving ? "配置正在后台部署..." : "保存并生效配置"}
                  </Button>
                </div>
              </form>
            </TabsContent>
          </Tabs>
        </main>

        <Toaster />
      </div>
    </ThemeProvider>
  );
}
