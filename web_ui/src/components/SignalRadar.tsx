import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Trash2,
  ScanSearch,
  Calendar,
  ArrowUpDown,
  Loader2,
  RefreshCw,
  Eye,
} from "lucide-react";
import { toast } from "sonner";
import { SignalChartModal } from "@/components/SignalChartModal";
import { DateRangePicker } from "@/components/DateRangePicker";
import type { DateRange } from "react-day-picker";
import { HistoryScanProgressPanel } from "@/components/HistoryScanProgressPanel";
import { Pagination } from "@/components/Pagination";

interface Signal {
  id: number;
  symbol: string;
  interval: string;
  direction: string;
  score: number;
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  timestamp: number;
  quality_tier: string;
  source?: string;
  score_details?: {
    shape?: number;
  };
  ema_distance?: number;
  is_contrarian?: boolean;
  volatility_atr?: number;
}

interface SignalRadarProps {
  availableSymbols: string[];
  tableColumns: Record<string, boolean>;
  onTableColumnsChange: (columns: Record<string, boolean>) => void;
}

export function SignalRadar({
  availableSymbols,
  tableColumns,
  onTableColumnsChange,
}: SignalRadarProps) {
  // 信号数据
  const [signals, setSignals] = useState<Signal[]>([]);

  // 筛选条件 - 改变时不触发请求
  const [filterSymbol, setFilterSymbol] = useState("ALL");
  const [filterDirection, setFilterDirection] = useState("ALL");
  const [filterInterval, setFilterInterval] = useState("ALL");
  const [filterTier, setFilterTier] = useState("ALL");
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);

  // 分页状态
  const [pagination, setPagination] = useState({
    page: 1,
    size: 20,
    total: 0,
  });

  // 查询触发器 - 仅点击查询按钮时更新
  const [queryTrigger, setQueryTrigger] = useState(0);
  const [isQuerying, setIsQuerying] = useState(false);

  // 排序状态
  const [sortConfig, setSortConfig] = useState<{
    key: string;
    direction: "asc" | "desc";
  }>({ key: "timestamp", direction: "desc" });

  // 选中状态
  const [selectedSignals, setSelectedSignals] = useState<Set<string>>(new Set());

  // History Scan Modal States
  const [isHistoryScanOpen, setIsHistoryScanOpen] = useState(false);
  const [historyScanSubmitting, setHistoryScanSubmitting] = useState(false);
  const [historyScanForm, setHistoryScanForm] = useState({
    start_date: "",
    end_date: "",
    symbol: "",
    interval: "",
  });

  // History Scan Progress Panel States
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [isProgressPanelOpen, setIsProgressPanelOpen] = useState(false);

  // Signal Chart Detail Modal
  const [chartDetailSignal, setChartDetailSignal] = useState<Signal | null>(null);
  const [isChartDetailOpen, setIsChartDetailOpen] = useState(false);

  // 暴露刷新方法给父组件（用于删除后和历史扫描完成后）
  const refreshSignals = async () => {
    await fetchSignals();
  };

  // 查询信号的实际执行函数 - 使用 useCallback 包裹
  const fetchSignals = useCallback(async () => {
    setIsQuerying(true);
    try {
      const params = new URLSearchParams();
      params.append("page", pagination.page.toString());
      params.append("size", pagination.size.toString());

      // 添加筛选条件
      if (filterSymbol !== "ALL") params.append("symbols", filterSymbol);
      if (filterDirection !== "ALL") params.append("directions", filterDirection);
      if (filterInterval !== "ALL") params.append("intervals", filterInterval);
      if (filterTier === "A") params.append("min_score", "70");
      else if (filterTier === "C") params.append("min_score", "0");

      // 时间范围
      if (dateRange?.from) {
        params.append("start_time", dateRange.from.getTime().toString());
        params.append("end_time", dateRange.to ? dateRange.to.getTime().toString() : Date.now().toString());
      }

      // 排序
      params.append("sort_by", sortConfig.key);
      params.append("order", sortConfig.direction);

      const res = await fetch(`http://localhost:8000/api/signals?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setSignals(data.items || []);
      setPagination(prev => ({ ...prev, total: data.total || 0 }));
      setSelectedSignals(new Set());

      if (queryTrigger > 0) {
        toast.success(`查询完成，找到 ${data.total || 0} 条信号`);
      }
    } catch {
      toast.error("查询失败", { description: "请检查后端服务状态" });
    } finally {
      setIsQuerying(false);
    }
  }, [pagination.page, pagination.size, filterSymbol, filterDirection, filterInterval, filterTier, dateRange, sortConfig.key, sortConfig.direction, queryTrigger]);

  // 合并所有数据加载逻辑为一个 useEffect
  useEffect(() => {
    if (queryTrigger > 0) {
      fetchSignals();
    }
  }, [queryTrigger, fetchSignals]);

  const getScoreBadgeColor = (score: number) => {
    if (score >= 90)
      return "bg-amber-500/20 text-amber-500 border-amber-500/30 font-bold";
    if (score >= 70)
      return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    return "bg-zinc-500/20 text-zinc-400 border-zinc-700";
  };

  const getTierBadgeProps = (tier: string) => {
    switch (tier) {
      case "A":
        return { label: "A 级", className: "bg-orange-500/10 text-orange-500 border-orange-500/20 font-bold" };
      case "B":
        return { label: "B 级", className: "bg-blue-500/10 text-blue-400 border-blue-500/20" };
      case "C":
        return { label: "C 级", className: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20" };
      default:
        return { label: "未知", className: "bg-zinc-500/10 text-zinc-400 border-zinc-700" };
    }
  };

  const getTierBadgeColor = (tier: string) => getTierBadgeProps(tier).className;

  // 信号列表直接使用后端返回的数据（已分页）
  const displaySignals = signals;

  const getSignalId = (s: Signal, idx: number): string => s.id?.toString() || `${s.timestamp}-${s.symbol}-${idx}`;

  const handleToggleSelectAll = () => {
    if (selectedSignals.size === displaySignals.length && displaySignals.length > 0) {
      setSelectedSignals(new Set());
    } else {
      setSelectedSignals(new Set(displaySignals.map((s, i) => getSignalId(s, i))));
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
        await refreshSignals();
        const newSelected = new Set(selectedSignals);
        idsToDelete.forEach((id) => newSelected.delete(id));
        setSelectedSignals(newSelected);
        toast.success(`已删除 ${idsToDelete.length} 条信号记录`);
      } else {
        throw new Error("Delete failed");
      }
    } catch {
      toast.error("删除信号失败", { description: "请检查网络或后端服务状态" });
    }
  };

  const handleClearAllSignals = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/signals/clear", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
      });
      if (res.ok) {
        await refreshSignals();
        setSelectedSignals(new Set());
        toast.success("已清空所有信号记录");
      } else {
        throw new Error("Clear failed");
      }
    } catch {
      toast.error("清空信号失败", { description: "请检查网络或后端服务状态" });
    }
  };

  const handleSortToggle = (key: string) => {
    setSortConfig((prev) => {
      const newDirection = prev.key === key && prev.direction === "desc" ? "asc" : "desc";
      // 排序变更时触发查询
      setPagination(p => ({ ...p, page: 1 }));
      setQueryTrigger(t => t + 1);
      return { key, direction: newDirection };
    });
  };

  // 处理筛选条件变更 - 不触发查询
  const handleFilterChange = (setter: React.Dispatch<React.SetStateAction<string>>) => (value: string) => {
    setter(value);
  };

  // 点击查询按钮 - 触发查询
  const handleApplyFilters = () => {
    setPagination(prev => ({ ...prev, page: 1 })); // 重置页码
    setQueryTrigger(prev => prev + 1);
  };

  const handleSubmitHistoryScan = async () => {
    const { start_date, end_date, symbol, interval } = historyScanForm;
    if (!start_date || !end_date || !symbol || !interval) {
      toast.error("请完整填写所有配置项");
      return;
    }
    setHistoryScanSubmitting(true);
    try {
      const res = await fetch("http://localhost:8000/api/signals/history-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start_date, end_date, symbol, interval }),
      });
      if (res.ok || res.status === 202) {
        const data = await res.json();
        setIsHistoryScanOpen(false);
        setHistoryScanForm({ start_date: "", end_date: "", symbol: "", interval: "" });
        // 打开进度面板
        setActiveTaskId(data.task_id);
        setIsProgressPanelOpen(true);
        toast.success("历史扫描任务已启动", { description: `任务 ID: ${data.task_id.slice(0, 12)}...` });
      } else {
        const errData = await res.json().catch(() => ({}));
        toast.error("提交失败", { description: errData.detail || "请检查参数与后端服务状态" });
      }
    } catch {
      toast.error("网络异常", { description: "无法连接后端服务" });
    } finally {
      setHistoryScanSubmitting(false);
    }
  };

  const handleTaskComplete = () => {
    refreshSignals();
    toast.success("历史信号扫描完成！");
  };

  // 分页处理
  const handlePageChange = (newPage: number) => {
    setPagination(prev => ({ ...prev, page: newPage }));
  };

  const handleSizeChange = (newSize: number) => {
    setPagination(prev => ({ ...prev, size: newSize, page: 1 }));
  };

  return (
    <>
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden shadow-lg">
        {/* 上层：主筛选条件 */}
        <div className="p-4 border-b border-zinc-200 dark:border-white/5 bg-black/5 dark:bg-black/20">
          <div className="flex items-center gap-2 mb-4">
            <Eye className="w-4 h-4 text-zinc-400" />
            <p className="text-sm font-medium text-zinc-800 dark:text-zinc-300">信号过滤与筛选</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <DateRangePicker dateRange={dateRange} onDateRangeChange={setDateRange} presetLabel="时间范围" className="flex-shrink-0" />
            <Select value={filterSymbol} onValueChange={handleFilterChange(setFilterSymbol)} disabled={isQuerying}>
              <SelectTrigger className="w-[130px] h-9 bg-transparent border-zinc-200 dark:border-zinc-800 text-sm text-zinc-800 dark:text-zinc-200">
                <SelectValue placeholder="币种筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部币种</SelectItem>
                {availableSymbols.map((sym) => (<SelectItem key={sym} value={sym}>{sym}</SelectItem>))}
              </SelectContent>
            </Select>
            <Select value={filterDirection} onValueChange={handleFilterChange(setFilterDirection)} disabled={isQuerying}>
              <SelectTrigger className="w-[110px] h-9 bg-transparent border-zinc-200 dark:border-zinc-800 text-sm text-zinc-800 dark:text-zinc-200">
                <SelectValue placeholder="方向筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部方向</SelectItem>
                <SelectItem value="LONG">做多 (LONG)</SelectItem>
                <SelectItem value="SHORT">做空 (SHORT)</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterInterval} onValueChange={handleFilterChange(setFilterInterval)} disabled={isQuerying}>
              <SelectTrigger className="w-[120px] h-9 bg-transparent border-zinc-200 dark:border-zinc-800 text-sm text-zinc-800 dark:text-zinc-200">
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
            <Select value={filterTier} onValueChange={handleFilterChange(setFilterTier)} disabled={isQuerying}>
              <SelectTrigger className="w-[120px] h-9 bg-transparent border-zinc-200 dark:border-zinc-800 text-sm text-zinc-800 dark:text-zinc-200">
                <SelectValue placeholder="信号等级" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部等级</SelectItem>
                <SelectItem value="A">A 级 (精品)</SelectItem>
                <SelectItem value="B">B 级 (普通)</SelectItem>
                <SelectItem value="C">C 级 (观察)</SelectItem>
              </SelectContent>
            </Select>
            <div className="flex-1" />
            <Button variant="default" size="sm" onClick={handleApplyFilters} disabled={isQuerying} className="bg-blue-600 hover:bg-blue-700 text-white h-9">
              {isQuerying ? (<><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> 查询中...</>) : (<><ScanSearch className="w-4 h-4 mr-1.5" /> 查询</>)}
            </Button>
            <Button variant="ghost" size="sm" onClick={refreshSignals} className="text-zinc-500 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-300 h-9">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* 下层：操作按钮 */}
        <div className="p-3 border-b border-zinc-200 dark:border-white/5 bg-black/5 dark:bg-black/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="text-zinc-500 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-900 h-8">
                    <Eye className="w-4 h-4 mr-2" /> 视图设置
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48 bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 rounded-2xl shadow-xl">
                  <DropdownMenuLabel className="text-xs text-zinc-500 font-semibold px-4 pt-3 pb-2 uppercase tracking-widest">显示列配置</DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-zinc-100 dark:bg-white/5" />
                  <DropdownMenuCheckboxItem checked={tableColumns.timestamp !== false} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, timestamp: !!c })}>发生时间</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem checked={tableColumns.symbol !== false} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, symbol: !!c })}>币种级别</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem checked={tableColumns.direction !== false} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, direction: !!c })}>方向</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem checked={tableColumns.score !== false} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, score: !!c })}>综合评分</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem checked={tableColumns.entry_price !== false} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, entry_price: !!c })}>入场价</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem checked={tableColumns.shape} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, shape: !!c })}>影线占比</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem checked={tableColumns.ema} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, ema: !!c })}>EMA 距离</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem checked={tableColumns.atr} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, atr: !!c })}>ATR 波动率</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem checked={tableColumns.qualityTier} onCheckedChange={(c) => onTableColumnsChange({ ...tableColumns, qualityTier: !!c })}>信号等级</DropdownMenuCheckboxItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button variant="outline" size="sm" onClick={() => setIsHistoryScanOpen(true)} className="border-blue-500/30 text-blue-600 dark:text-blue-400 hover:bg-blue-500/10 hover:border-blue-500/50 h-8">
                <ScanSearch className="w-4 h-4 mr-2" /> 历史信号检查
              </Button>
              <Button variant="ghost" size="sm" onClick={handleClearAllSignals} className="text-zinc-500 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-900 h-8">
                <Trash2 className="w-4 h-4 mr-2" /> 清空记录
              </Button>
            </div>
            {selectedSignals.size > 0 && (
              <Button variant="ghost" size="sm" onClick={() => handleDeleteSignals(Array.from(selectedSignals))} className="text-rose-500 hover:text-rose-600 dark:text-rose-400 dark:hover:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-950/30 h-8">
                <Trash2 className="w-4 h-4 mr-2" /> 批量删除 ({selectedSignals.size})
              </Button>
            )}
          </div>
        </div>

        {/* Data Table */}
        <div className="overflow-x-auto">
          <Table className="min-w-full">
            <TableHeader className="bg-zinc-100 dark:bg-zinc-900/40">
              <TableRow className="hover:bg-transparent border-zinc-200 dark:border-white/5">
                <TableHead className="w-[40px] pl-4">
                  <Checkbox checked={displaySignals.length > 0 && selectedSignals.size === displaySignals.length} onCheckedChange={handleToggleSelectAll} className="border-zinc-400 dark:border-zinc-600" />
                </TableHead>
                {tableColumns.timestamp !== false && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400 w-[160px]"><div className="flex items-center gap-1 cursor-pointer hover:text-zinc-900 dark:hover:text-zinc-200 transition-colors" onClick={() => handleSortToggle("timestamp")}>发生时间 <ArrowUpDown className="w-3 h-3 opacity-50" /></div></TableHead>)}
                {tableColumns.symbol !== false && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">币种级别</TableHead>)}
                {tableColumns.direction !== false && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">方向</TableHead>)}
                {tableColumns.score !== false && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400"><div className="flex items-center gap-1 cursor-pointer hover:text-zinc-900 dark:hover:text-zinc-200 transition-colors" onClick={() => handleSortToggle("score")}>综合评分 <ArrowUpDown className="w-3 h-3 opacity-50" /></div></TableHead>)}
                {tableColumns.entry_price !== false && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">入场价</TableHead>)}
                {tableColumns.shape && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">影线占比</TableHead>)}
                {tableColumns.ema && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">EMA 距离</TableHead>)}
                {tableColumns.is_contrarian && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">逆势信号</TableHead>)}
                {tableColumns.atr && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">ATR 波动率</TableHead>)}
                {tableColumns.qualityTier && (<TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">信号等级</TableHead>)}
                <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400 text-right pr-4">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {displaySignals.length === 0 ? (
                <TableRow><TableCell colSpan={12} className="h-32 text-center text-zinc-500">暂无符合条件的信号记录</TableCell></TableRow>
              ) : (
                displaySignals.map((sig, idx) => {
                  const sigId = getSignalId(sig, idx);
                  return (
                    <TableRow key={sigId} className="hover:bg-zinc-100/50 dark:hover:bg-white/[0.04] border-zinc-200 dark:border-white/5 transition-colors group">
                      <TableCell className="pl-4"><Checkbox checked={selectedSignals.has(sigId)} onCheckedChange={(c) => handleToggleSelect(sigId, !!c)} className="border-zinc-300 dark:border-zinc-700 data-[state=checked]:bg-blue-500 data-[state=checked]:text-white" /></TableCell>
                      {tableColumns.timestamp !== false && (<TableCell className="text-zinc-600 dark:text-zinc-400 text-sm whitespace-nowrap">{new Date(sig.timestamp).toLocaleString()}</TableCell>)}
                      {tableColumns.symbol !== false && (<TableCell className="font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5 pt-4">{sig.symbol}{sig.interval && (<Badge variant="secondary" className="text-[10px] px-1 h-4">({sig.interval})</Badge>)}{sig.source === "history_scan" && (<Badge variant="outline" className="text-[10px] px-1.5 h-4 bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20">历史</Badge>)}</TableCell>)}
                      {tableColumns.direction !== false && (<TableCell><Badge variant="outline" className={`font-medium ${sig.direction === "LONG" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"}`}>{sig.direction === "LONG" ? "做多" : "做空"}</Badge></TableCell>)}
                      {tableColumns.score !== false && (<TableCell><Badge variant="outline" className={`min-w-[4rem] justify-center ${getScoreBadgeColor(sig.score)}`}>{sig.score} Pts</Badge></TableCell>)}
                      {tableColumns.entry_price !== false && (<TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">${Number(sig.entry_price || 0).toFixed(4)}</TableCell>)}
                      {tableColumns.shape && (<TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">{Number(sig.score_details?.shape || 0).toFixed(1)}</TableCell>)}
                      {tableColumns.ema && (<TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">{Number(sig.ema_distance || 0).toFixed(2)}</TableCell>)}
                      {tableColumns.is_contrarian && (<TableCell className="text-zinc-600 dark:text-zinc-400 text-sm">{sig.is_contrarian ? (<Badge variant="outline" className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 text-xs">逆势</Badge>) : (<span className="text-zinc-400 text-xs">顺势</span>)}</TableCell>)}
                      {tableColumns.atr && (<TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">{Number(sig.volatility_atr || 0).toFixed(2)}</TableCell>)}
                      {tableColumns.qualityTier && (<TableCell><Badge variant="outline" className={`min-w-[3.5rem] justify-center ${getTierBadgeColor(sig.quality_tier || "B")}`}>{getTierBadgeProps(sig.quality_tier || "B").label}</Badge></TableCell>)}
                      <TableCell className="text-right pr-4">
                        <Button variant="ghost" size="sm" className="h-8 text-blue-500 hover:text-blue-600 bg-blue-500/10 hover:bg-blue-500/20" onClick={() => { setChartDetailSignal(sig); setIsChartDetailOpen(true); }}>详情</Button>
                        <Button variant="ghost" size="icon" onClick={() => handleDeleteSignals([sigId])} className="h-8 w-8 text-rose-500/70 hover:text-rose-500 hover:bg-rose-500/10 ml-2"><Trash2 className="w-4 h-4" /></Button>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>

        {/* 分页组件 */}
        <div className="px-4">
          <Pagination
            page={pagination.page}
            size={pagination.size}
            total={pagination.total}
            onPageChange={handlePageChange}
            onSizeChange={handleSizeChange}
          />
        </div>
      </Card>

      {/* History Scan Modal - 配置对话框 */}
      <Dialog open={isHistoryScanOpen} onOpenChange={setIsHistoryScanOpen}>
        <DialogContent className="sm:max-w-md bg-white/80 dark:bg-zinc-900/80 backdrop-blur-2xl border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-zinc-100 rounded-3xl p-6 shadow-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><ScanSearch className="w-5 h-5 text-blue-500" /> 历史信号检查</DialogTitle>
            <DialogDescription className="text-zinc-500 dark:text-zinc-400">回溯指定日期范围内的历史 K 线，全量复用当前策略与评分逻辑进行信号扫描。</DialogDescription>
          </DialogHeader>
          <div className="space-y-5 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">开始日期</Label>
                <div className="relative">
                  <Calendar className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
                  <Input type="date" value={historyScanForm.start_date} onChange={(e) => setHistoryScanForm((prev) => ({ ...prev, start_date: e.target.value }))} className="pl-10 bg-zinc-50 dark:bg-black/20 border-zinc-200 dark:border-white/10 rounded-xl h-10" />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">结束日期</Label>
                <div className="relative">
                  <Calendar className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
                  <Input type="date" value={historyScanForm.end_date} onChange={(e) => setHistoryScanForm((prev) => ({ ...prev, end_date: e.target.value }))} className="pl-10 bg-zinc-50 dark:bg-black/20 border-zinc-200 dark:border-white/10 rounded-xl h-10" />
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">监控币种</Label>
              <Select value={historyScanForm.symbol} onValueChange={(v) => setHistoryScanForm((prev) => ({ ...prev, symbol: v }))}>
                <SelectTrigger className="bg-zinc-50 dark:bg-black/20 border-zinc-200 dark:border-white/10 rounded-xl h-10"><SelectValue placeholder="选择币种" /></SelectTrigger>
                <SelectContent className="bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 rounded-xl">
                  {availableSymbols.map((sym) => (<SelectItem key={sym} value={sym}>{sym}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">时间级别</Label>
              <Select value={historyScanForm.interval} onValueChange={(v) => setHistoryScanForm((prev) => ({ ...prev, interval: v }))}>
                <SelectTrigger className="bg-zinc-50 dark:bg-black/20 border-zinc-200 dark:border-white/10 rounded-xl h-10"><SelectValue placeholder="选择级别" /></SelectTrigger>
                <SelectContent className="bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 rounded-xl">
                  {["15m", "1h", "4h", "1d"].map((ivl) => (<SelectItem key={ivl} value={ivl}>{ivl}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsHistoryScanOpen(false)} className="rounded-xl">取消</Button>
            <Button onClick={handleSubmitHistoryScan} disabled={historyScanSubmitting} className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-6">
              {historyScanSubmitting ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" /> 扫描中...</>) : (<><ScanSearch className="w-4 h-4 mr-2" /> 开始检查</>)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History Scan Progress Panel - 进度面板 */}
      <HistoryScanProgressPanel taskId={activeTaskId} open={isProgressPanelOpen} onOpenChange={setIsProgressPanelOpen} onTaskComplete={handleTaskComplete} />

      {/* Signal Chart Detail Modal */}
      <SignalChartModal signal={chartDetailSignal} open={isChartDetailOpen} onOpenChange={setIsChartDetailOpen} />
    </>
  );
}
