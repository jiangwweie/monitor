import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { Activity, Radar, Wallet, Settings2, Clock, Radar as RadarIcon } from "lucide-react";

import { ThemeProvider } from "@/components/theme-provider";
import { ModeToggle } from "@/components/mode-toggle";
import { Dashboard } from "@/components/Dashboard";
import { SignalRadar } from "@/components/SignalRadar";
import { Positions } from "@/components/Positions";
import { Settings } from "@/components/Settings";
import { PositionDetailModal } from "@/components/PositionDetailModal";
import { usePolling } from "@/hooks/usePolling";

const AVAILABLE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"];

// API 基础 URL
const API_BASE = "http://localhost:8000";

export default function App() {
  const [loading, setLoading] = useState(true);
  const [realtimePrices, setRealtimePrices] = useState<Record<string, number>>({});

  const [tableColumns, setTableColumns] = useState<Record<string, boolean>>({
    timestamp: true,
    symbol: true,
    direction: true,
    score: true,
    entry_price: true,
    shape: false,
    ema: false,
    atr: false,
    is_contrarian: false,
  });

  const [selectedPositionDetail, setSelectedPositionDetail] = useState<any>(null);
  const [loadingPositionDetail, setLoadingPositionDetail] = useState(false);
  const [isPositionModalOpen, setIsPositionModalOpen] = useState(false);

  // 配置数据 - 仅初始加载
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
    doji_threshold: 0.05,
    doji_shadow_bonus: 0.6,
    mtf_trend_filter_mode: "soft",
    dynamic_sl_enabled: true,
    dynamic_sl_base: 0.035,
    dynamic_sl_atr_multiplier: 0.5,
  });

  // 系统状态轮询 - 30 秒间隔
  const {
    data: systemStatusData,
  } = usePolling(
    async () => {
      const res = await fetch(`${API_BASE}/api/system/status`);
      if (!res.ok) throw new Error("System status fetch failed");
      return await res.json();
    },
    {
      interval: 30000,
      enabled: true,
      immediate: true,
    }
  );

  const [systemStatus, setSystemStatus] = useState({
    is_connected: false,
    api_latency_ms: 0,
    api_weight_usage: 0,
    uptime: "0s",
  });

  // 账户余额轮询 - 60 秒间隔
  const {
    data: dashboardData,
  } = usePolling(
    async () => {
      const res = await fetch(`${API_BASE}/api/account/balance`);
      if (!res.ok) throw new Error("Balance fetch failed");
      const data = await res.json();
      return data.status === "success" ? data.data : null;
    },
    {
      interval: 60000,
      enabled: true,
      immediate: true,
    }
  );

  // 信号列表轮询 - 60 秒间隔
  const {
    data: signals,
    refresh: refreshSignals,
  } = usePolling(
    async () => {
      const res = await fetch(`${API_BASE}/api/signals`);
      if (!res.ok) throw new Error("Signals fetch failed");
      const resJson = await res.json();
      // API 返回格式：{ status: "success", data: { items: [...], total: 888 }, meta: {...} }
      return Array.isArray(resJson?.data?.items) ? resJson.data.items : [];
    },
    {
      interval: 60000,
      enabled: true,
      immediate: true,
    }
  );

  // 实时价格轮询 - 2 秒间隔
  usePolling(
    async () => {
      const activeSymbols = config.symbols.split(",").map((s) => s.trim()).filter(Boolean);
      if (activeSymbols.length === 0) return {};

      const symbolQuery = `["${activeSymbols.join('","')}"]`;
      const res = await fetch(
        `https://api.binance.com/api/v3/ticker/price?symbols=${encodeURIComponent(symbolQuery)}`
      );

      if (!res.ok) throw new Error("Price fetch failed");

      const data = await res.json();
      const newPrices: Record<string, number> = {};
      data.forEach((item: any) => {
        newPrices[item.symbol] = Number(item.price);
      });
      return newPrices;
    },
    {
      interval: 2000,
      enabled: true,
      immediate: true,
      onSuccess: (data) => {
        if (data) {
          setRealtimePrices((prev) => ({ ...prev, ...data }));
        }
      },
    }
  );

  // 同步系统状态到 state
  useEffect(() => {
    if (systemStatusData?.data) {
      setSystemStatus((prev) => ({ ...prev, ...systemStatusData.data }));
    }
  }, [systemStatusData]);

  // Load preferences
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const [configRes, preferencesRes] = await Promise.all([
          fetch(`${API_BASE}/api/config`).catch(() => null),
          fetch(`${API_BASE}/api/preferences/view`).catch(() => null),
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
            doji_threshold: data.pinbar_config?.doji_threshold ?? 0.05,
            doji_shadow_bonus: data.pinbar_config?.doji_shadow_bonus ?? 0.6,
            mtf_trend_filter_mode: data.pinbar_config?.mtf_trend_filter_mode ?? "soft",
            dynamic_sl_enabled: data.pinbar_config?.dynamic_sl_enabled ?? true,
            dynamic_sl_base: data.pinbar_config?.dynamic_sl_base ?? 0.035,
            dynamic_sl_atr_multiplier: data.pinbar_config?.dynamic_sl_atr_multiplier ?? 0.5,
          }));
        }

        if (preferencesRes && preferencesRes.ok) {
          const data = await preferencesRes.json();
          if (data.signals_table_columns && Object.keys(data.signals_table_columns).length > 0) {
            setTableColumns((prev) => ({ ...prev, ...data.signals_table_columns }));
          } else {
            const local = localStorage.getItem("monitor_table_columns");
            if (local) setTableColumns(JSON.parse(local));
          }
        } else {
          const local = localStorage.getItem("monitor_table_columns");
          if (local) setTableColumns(JSON.parse(local));
        }
      } catch (error) {
        console.warn("Initial config load failed");
      } finally {
        setLoading(false);
      }
    };

    loadConfig();
  }, []);

  // 配置变更处理
  const handleConfigChange = (field: string, value: any) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const handleOpenPositionDetail = async (symbol: string) => {
    setIsPositionModalOpen(true);
    setLoadingPositionDetail(true);
    try {
      const res = await fetch(
        `http://localhost:8000/api/account/position/detail/${symbol}`
      );
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

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center">
        <div className="w-8 h-8 animate-spin text-zinc-400 dark:text-zinc-600">
          <svg className="w-full h-full" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </div>
    );
  }

  return (
    <ThemeProvider defaultTheme="dark" storageKey="crypto-radar-theme">
      <PositionDetailModal
        open={isPositionModalOpen}
        onOpenChange={setIsPositionModalOpen}
        position={selectedPositionDetail}
        loading={loadingPositionDetail}
      />

      <div className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100 font-sans selection:bg-blue-500/30 pb-12 transition-colors duration-300">
        {/* Ambient Orbs */}
        <div className="fixed -top-32 -left-32 w-96 h-96 bg-blue-500/10 dark:bg-blue-900/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="fixed top-1/2 right-0 w-[500px] h-[500px] bg-purple-500/10 dark:bg-purple-900/5 rounded-full blur-[150px] pointer-events-none translate-x-1/3 -translate-y-1/2" />

        <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-12 relative z-10 animate-in fade-in slide-in-from-bottom-8 duration-700 ease-out">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white flex items-center gap-3">
                <RadarIcon className="w-8 h-8 text-blue-500" />
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
                      className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                        systemStatus.is_connected ? "bg-emerald-400" : "bg-red-400"
                      }`}
                    ></span>
                    <span
                      className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                        systemStatus.is_connected ? "bg-emerald-500" : "bg-red-500"
                      }`}
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

          {/* Tabs */}
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

            {/* Dashboard Tab */}
            <TabsContent value="dashboard">
              <Dashboard
                systemStatus={systemStatus}
                dashboardData={dashboardData}
                realtimePrices={realtimePrices}
                activeSymbols={config.symbols.split(",").map((s) => s.trim()).filter(Boolean)}
                onOpenPositionDetail={handleOpenPositionDetail}
              />
            </TabsContent>

            {/* Signals Tab */}
            <TabsContent value="signals">
              <SignalRadar
                signals={signals || []}
                availableSymbols={AVAILABLE_SYMBOLS}
                tableColumns={tableColumns}
                onTableColumnsChange={setTableColumns}
                onSignalsChange={(newSignals) => {
                  // 手动更新信号列表用于删除后的即时响应
                  // 实际数据会在下一次轮询时与后端同步
                  const event = new CustomEvent("local-signals-update", { detail: newSignals });
                  window.dispatchEvent(event);
                }}
                onRefresh={refreshSignals}
              />
            </TabsContent>

            {/* Positions Tab */}
            <TabsContent value="positions">
              <Positions
                dashboardData={dashboardData}
                onOpenPositionDetail={handleOpenPositionDetail}
              />
            </TabsContent>

            {/* Settings Tab */}
            <TabsContent value="settings">
              <Settings
                config={config}
                onConfigChange={handleConfigChange}
              />
            </TabsContent>
          </Tabs>
        </main>

        <Toaster />
      </div>
    </ThemeProvider>
  );
}
