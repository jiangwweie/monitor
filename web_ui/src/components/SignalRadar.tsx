import { useState } from "react";
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
  Filter,
  Settings2,
  Trash2,
  ScanSearch,
  Calendar,
  ArrowUpDown,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { SignalChartModal } from "@/components/SignalChartModal";
import { DateRangePicker } from "@/components/DateRangePicker";
import type { DateRange } from "react-day-picker";

interface SignalRadarProps {
  signals: any[];
  availableSymbols: string[];
  tableColumns: Record<string, boolean>;
  onTableColumnsChange: (columns: Record<string, boolean>) => void;
  onSignalsChange: (signals: any[]) => void;
  onRefresh?: () => void;
}

export function SignalRadar({
  signals,
  availableSymbols,
  tableColumns,
  onTableColumnsChange,
  onSignalsChange,
  onRefresh,
}: SignalRadarProps) {
  const [filterSymbol, setFilterSymbol] = useState("ALL");
  const [filterDirection, setFilterDirection] = useState("ALL");
  const [filterInterval, setFilterInterval] = useState("ALL");
  const [filterTier, setFilterTier] = useState("ALL");
  const [selectedSignals, setSelectedSignals] = useState<Set<string>>(new Set());
  const [sortConfig, setSortConfig] = useState<{
    key: string;
    direction: "asc" | "desc";
  }>({ key: "timestamp", direction: "desc" });
  const [isQuerying, setIsQuerying] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);

  // History Scan Modal States
  const [isHistoryScanOpen, setIsHistoryScanOpen] = useState(false);
  const [historyScanSubmitting, setHistoryScanSubmitting] = useState(false);
  const [historyScanForm, setHistoryScanForm] = useState({
    start_date: "",
    end_date: "",
    symbol: "",
    interval: "",
  });

  // Signal Chart Detail Modal
  const [chartDetailSignal, setChartDetailSignal] = useState<any>(null);
  const [isChartDetailOpen, setIsChartDetailOpen] = useState(false);

  const getScoreBadgeColor = (score: number) => {
    if (score >= 90)
      return "bg-amber-500/20 text-amber-500 border-amber-500/30 font-bold";
    if (score >= 70)
      return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    return "bg-zinc-500/20 text-zinc-400 border-zinc-700";
  };

  // 信号质量分级辅助函数
  const getTierBadgeProps = (tier: string) => {
    switch (tier) {
      case "A":
        return {
          label: "A 级",
          className: "bg-orange-500/10 text-orange-500 border-orange-500/20 font-bold",
        };
      case "B":
        return {
          label: "B 级",
          className: "bg-blue-500/10 text-blue-400 border-blue-500/20",
        };
      case "C":
        return {
          label: "C 级",
          className: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
        };
      default:
        return {
          label: "未知",
          className: "bg-zinc-500/10 text-zinc-400 border-zinc-700",
        };
    }
  };

  const getTierBadgeColor = (tier: string) => {
    return getTierBadgeProps(tier).className;
  };

  const sortedAndFilteredSignals = (() => {
    let result = [...signals];
    if (filterSymbol !== "ALL") {
      result = result.filter((s) => s.symbol === filterSymbol);
    }
    if (filterDirection !== "ALL") {
      result = result.filter((s) => s.direction === filterDirection);
    }
    if (filterInterval !== "ALL") {
      result = result.filter((s) => s.interval === filterInterval);
    }
    if (filterTier !== "ALL") {
      result = result.filter((s) => (s.quality_tier || "B") === filterTier);
    }

    result.sort((a, b) => {
      let valA = a[sortConfig.key];
      let valB = b[sortConfig.key];
      if (valA < valB) return sortConfig.direction === "asc" ? -1 : 1;
      if (valA > valB) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
    return result;
  })();

  const getSignalId = (s: any, idx: number) => s.id || `${s.timestamp}-${s.symbol}-${idx}`;

  const handleToggleSelectAll = () => {
    if (
      selectedSignals.size === sortedAndFilteredSignals.length &&
      sortedAndFilteredSignals.length > 0
    ) {
      setSelectedSignals(new Set());
    } else {
      setSelectedSignals(
        new Set(sortedAndFilteredSignals.map((s, i) => getSignalId(s, i)))
      );
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
        onSignalsChange(
          signals.filter((s, i) => !idsSet.has(getSignalId(s, i)))
        );
        const newSelected = new Set(selectedSignals);
        idsToDelete.forEach((id) => newSelected.delete(id));
        setSelectedSignals(newSelected);
        toast.success(`已删除 ${idsToDelete.length} 条信号记录`);
      } else {
        throw new Error("Delete failed");
      }
    } catch (error) {
      toast.error("删除信号失败", {
        description: "请检查网络或后端服务状态",
      });
    }
  };

  const handleSortToggle = (key: string) => {
    setSortConfig((prev) => ({
      key,
      direction:
        prev.key === key && prev.direction === "desc" ? "asc" : "desc",
    }));
  };

  /**
   * 调用后端 API 进行真正的筛选查询
   */
  const handleApplyFilters = async () => {
    setIsQuerying(true);
    try {
      // 构建查询参数
      const params = new URLSearchParams();

      if (filterSymbol !== "ALL") {
        params.append("symbols", filterSymbol);
      }
      if (filterDirection !== "ALL") {
        params.append("directions", filterDirection);
      }
      if (filterInterval !== "ALL") {
        params.append("intervals", filterInterval);
      }

      // 日期范围筛选 (优先使用 dateRange)
      if (dateRange?.from) {
        params.append("start_time", dateRange.from.getTime().toString());
        if (dateRange.to) {
          params.append("end_time", dateRange.to.getTime().toString());
        } else {
          params.append("end_time", Date.now().toString());
        }
      }

      // 最小分数筛选（可以基于等级推算）
      if (filterTier === "A") {
        params.append("min_score", "70");
      } else if (filterTier === "C") {
        params.append("min_score", "0");
      }

      params.append("sort_by", sortConfig.key);
      params.append("order", sortConfig.direction);
      params.append("size", "200");
      params.append("page", "1");

      const res = await fetch(`http://localhost:8000/api/signals?${params.toString()}`);

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      onSignalsChange(data.items || []);
      setSelectedSignals(new Set());

      toast.success(`查询完成，找到 ${data.total || 0} 条信号`);
    } catch (error) {
      toast.error("查询失败", {
        description: error instanceof Error ? error.message : "请检查后端服务状态",
      });
    } finally {
      setIsQuerying(false);
    }
  };

  const handleSubmitHistoryScan = async () => {
    const { start_date, end_date, symbol, interval } = historyScanForm;
    if (!start_date || !end_date || !symbol || !interval) {
      toast.error("请完整填写所有配置项");
      return;
    }
    setHistoryScanSubmitting(true);
    try {
      const res = await fetch(
        "http://localhost:8000/api/signals/history-check",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ start_date, end_date, symbol, interval }),
        }
      );
      if (res.ok || res.status === 202) {
        const data = await res.json();
        setIsHistoryScanOpen(false);
        setHistoryScanForm({
          start_date: "",
          end_date: "",
          symbol: "",
          interval: "",
        });
        toast.success("历史扫描任务已在后台启动", {
          description: `任务 ID: ${data.task_id}。识别到的信号将自动录入并通知。`,
        });
      } else {
        const errData = await res.json().catch(() => ({}));
        toast.error("提交失败", {
          description: errData.detail || "请检查参数与后端服务状态",
        });
      }
    } catch (error) {
      toast.error("网络异常", { description: "无法连接后端服务" });
    } finally {
      setHistoryScanSubmitting(false);
    }
  };

  return (
    <>
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden shadow-lg">
        <div className="p-4 border-b border-zinc-200 dark:border-white/5 flex flex-wrap gap-4 items-center justify-between bg-black/5 dark:bg-black/20">
          <div className="flex items-center gap-4 flex-wrap">
            <p className="text-sm font-medium text-zinc-800 dark:text-zinc-300 flex items-center gap-2">
              <Filter className="w-4 h-4 text-zinc-400" /> 信号过滤与筛选
            </p>
            <div className="h-4 w-px bg-zinc-300 dark:bg-zinc-700" />

            {/* 日期范围选择器 */}
            <DateRangePicker
              dateRange={dateRange}
              onDateRangeChange={setDateRange}
              presetLabel="时间范围"
              className="flex-shrink-0"
            />

            <div className="h-4 w-px bg-zinc-300 dark:bg-zinc-700" />

            <Select value={filterSymbol} onValueChange={setFilterSymbol}>
              <SelectTrigger className="w-[120px] h-8 bg-transparent border-zinc-200 dark:border-zinc-800 text-xs text-zinc-800 dark:text-zinc-200">
                <SelectValue placeholder="币种筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部币种</SelectItem>
                {availableSymbols.map((sym) => (
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

            <Select value={filterTier} onValueChange={setFilterTier}>
              <SelectTrigger className="w-[110px] h-8 bg-transparent border-zinc-200 dark:border-zinc-800 text-xs text-zinc-800 dark:text-zinc-200">
                <SelectValue placeholder="信号等级" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部等级</SelectItem>
                <SelectItem value="A">A 级 (精品)</SelectItem>
                <SelectItem value="B">B 级 (普通)</SelectItem>
                <SelectItem value="C">C 级 (观察)</SelectItem>
              </SelectContent>
            </Select>

            <Button
              variant="default"
              size="sm"
              onClick={handleApplyFilters}
              disabled={isQuerying}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {isQuerying ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> 查询中...
                </>
              ) : (
                <>
                  <ScanSearch className="w-3.5 h-3.5 mr-1.5" /> 查询
                </>
              )}
            </Button>

            {/* 刷新按钮 */}
            {onRefresh && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onRefresh}
                className="text-zinc-500 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-300"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
            )}
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
              <DropdownMenuContent
                align="end"
                className="w-48 bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 rounded-2xl shadow-xl"
              >
                <DropdownMenuLabel className="text-xs text-zinc-500 font-semibold px-4 pt-3 pb-2 uppercase tracking-widest">
                  显示列配置
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-zinc-100 dark:bg-white/5" />
                <DropdownMenuCheckboxItem
                  checked={tableColumns.timestamp !== false}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, timestamp: !!c })
                  }
                >
                  发生时间
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={tableColumns.symbol !== false}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, symbol: !!c })
                  }
                >
                  币种级别
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={tableColumns.direction !== false}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, direction: !!c })
                  }
                >
                  方向
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={tableColumns.score !== false}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, score: !!c })
                  }
                >
                  综合评分
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={tableColumns.entry_price !== false}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, entry_price: !!c })
                  }
                >
                  入场价
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={tableColumns.shape}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, shape: !!c })
                  }
                >
                  影线占比
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={tableColumns.ema}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, ema: !!c })
                  }
                >
                  EMA 距离
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={tableColumns.atr}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, atr: !!c })
                  }
                >
                  ATR 波动率
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={tableColumns.qualityTier}
                  onCheckedChange={(c) =>
                    onTableColumnsChange({ ...tableColumns, qualityTier: !!c })
                  }
                >
                  信号等级
                </DropdownMenuCheckboxItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {selectedSignals.size > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  handleDeleteSignals(Array.from(selectedSignals))
                }
                className="text-rose-500 hover:text-rose-600 dark:text-rose-400 dark:hover:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-950/30"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                批量删除 ({selectedSignals.size})
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsHistoryScanOpen(true)}
              className="border-blue-500/30 text-blue-600 dark:text-blue-400 hover:bg-blue-500/10 hover:border-blue-500/50"
            >
              <ScanSearch className="w-4 h-4 mr-2" />
              历史信号检查
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSignalsChange([])}
              className="text-zinc-500 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-900"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              清空记录
            </Button>
          </div>
        </div>

        {/* Data Table */}
        <div className="overflow-x-auto">
          <Table className="min-w-full">
            <TableHeader className="bg-zinc-100 dark:bg-zinc-900/40">
              <TableRow className="hover:bg-transparent border-zinc-200 dark:border-white/5">
                <TableHead className="w-[40px] pl-4">
                  <Checkbox
                    checked={
                      sortedAndFilteredSignals.length > 0 &&
                      selectedSignals.size ===
                        sortedAndFilteredSignals.length
                    }
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
                      发生时间 <ArrowUpDown className="w-3 h-3 opacity-50" />
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
                      综合评分 <ArrowUpDown className="w-3 h-3 opacity-50" />
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
                    EMA 距离
                  </TableHead>
                )}
                {tableColumns.is_contrarian && (
                  <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                    逆势信号
                  </TableHead>
                )}
                {tableColumns.atr && (
                  <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                    ATR 波动率
                  </TableHead>
                )}
                {tableColumns.qualityTier && (
                  <TableHead className="font-semibold text-zinc-600 dark:text-zinc-400">
                    信号等级
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
                    colSpan={12}
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
                          onCheckedChange={(c) =>
                            handleToggleSelect(sigId, !!c)
                          }
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
                          {sig.interval && (
                            <Badge
                              variant="secondary"
                              className="text-[10px] px-1 h-4"
                            >
                              ({sig.interval})
                            </Badge>
                          )}
                          {sig.source === "history_scan" && (
                            <Badge
                              variant="outline"
                              className="text-[10px] px-1.5 h-4 bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20"
                            >
                              历史
                            </Badge>
                          )}
                        </TableCell>
                      )}
                      {tableColumns.direction !== false && (
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={`font-medium ${
                              sig.direction === "LONG"
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                                : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                            }`}
                          >
                            {sig.direction === "LONG" ? "做多" : "做空"}
                          </Badge>
                        </TableCell>
                      )}
                      {tableColumns.score !== false && (
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={`min-w-[4rem] justify-center ${getScoreBadgeColor(
                              sig.score
                            )}`}
                          >
                            {sig.score} Pts
                          </Badge>
                        </TableCell>
                      )}
                      {tableColumns.entry_price !== false && (
                        <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">
                          $
                          {Number(sig.entry_price || sig.price || 0).toFixed(4)}
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
                      {tableColumns.is_contrarian && (
                        <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm">
                          {sig.is_contrarian ? (
                            <Badge
                              variant="outline"
                              className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 text-xs"
                            >
                              逆势
                            </Badge>
                          ) : (
                            <span className="text-zinc-400 text-xs">
                              顺势
                            </span>
                          )}
                        </TableCell>
                      )}
                      {tableColumns.atr && (
                        <TableCell className="text-zinc-600 dark:text-zinc-400 text-sm font-mono font-medium">
                          {Number(sig.volatility_atr || 0).toFixed(2)}
                        </TableCell>
                      )}
                      {tableColumns.qualityTier && (
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={`min-w-[3.5rem] justify-center ${getTierBadgeColor(
                              sig.quality_tier || "B"
                            )}`}
                          >
                            {getTierBadgeProps(sig.quality_tier || "B").label}
                          </Badge>
                        </TableCell>
                      )}
                      <TableCell className="text-right pr-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 text-blue-500 hover:text-blue-600 bg-blue-500/10 hover:bg-blue-500/20"
                          onClick={() => {
                            setChartDetailSignal(sig);
                            setIsChartDetailOpen(true);
                          }}
                        >
                          详情
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteSignals([sigId])}
                          className="h-8 w-8 text-rose-500/70 hover:text-rose-500 hover:bg-rose-500/10 ml-2"
                        >
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

      {/* History Scan Modal */}
      <Dialog open={isHistoryScanOpen} onOpenChange={setIsHistoryScanOpen}>
        <DialogContent className="sm:max-w-md bg-white/80 dark:bg-zinc-900/80 backdrop-blur-2xl border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-zinc-100 rounded-3xl p-6 shadow-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ScanSearch className="w-5 h-5 text-blue-500" />
              历史信号检查
            </DialogTitle>
            <DialogDescription className="text-zinc-500 dark:text-zinc-400">
              回溯指定日期范围内的历史 K 线，全量复用当前策略与评分逻辑进行信号扫描。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-5 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
                  开始日期
                </Label>
                <div className="relative">
                  <Calendar className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
                  <Input
                    type="date"
                    value={historyScanForm.start_date}
                    onChange={(e) =>
                      setHistoryScanForm((prev) => ({
                        ...prev,
                        start_date: e.target.value,
                      }))
                    }
                    className="pl-10 bg-zinc-50 dark:bg-black/20 border-zinc-200 dark:border-white/10 rounded-xl h-10"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
                  结束日期
                </Label>
                <div className="relative">
                  <Calendar className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
                  <Input
                    type="date"
                    value={historyScanForm.end_date}
                    onChange={(e) =>
                      setHistoryScanForm((prev) => ({
                        ...prev,
                        end_date: e.target.value,
                      }))
                    }
                    className="pl-10 bg-zinc-50 dark:bg-black/20 border-zinc-200 dark:border-white/10 rounded-xl h-10"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
                监控币种
              </Label>
              <Select
                value={historyScanForm.symbol}
                onValueChange={(v) =>
                  setHistoryScanForm((prev) => ({ ...prev, symbol: v }))
                }
              >
                <SelectTrigger className="bg-zinc-50 dark:bg-black/20 border-zinc-200 dark:border-white/10 rounded-xl h-10">
                  <SelectValue placeholder="选择币种" />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 rounded-xl">
                  {availableSymbols.map((sym) => (
                    <SelectItem key={sym} value={sym}>
                      {sym}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
                时间级别
              </Label>
              <Select
                value={historyScanForm.interval}
                onValueChange={(v) =>
                  setHistoryScanForm((prev) => ({ ...prev, interval: v }))
                }
              >
                <SelectTrigger className="bg-zinc-50 dark:bg-black/20 border-zinc-200 dark:border-white/10 rounded-xl h-10">
                  <SelectValue placeholder="选择级别" />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 rounded-xl">
                  {["15m", "1h", "4h", "1d"].map((ivl) => (
                    <SelectItem key={ivl} value={ivl}>
                      {ivl}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setIsHistoryScanOpen(false)}
              className="rounded-xl"
            >
              取消
            </Button>
            <Button
              onClick={handleSubmitHistoryScan}
              disabled={historyScanSubmitting}
              className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-6"
            >
              {historyScanSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> 扫描中...
                </>
              ) : (
                <>
                  <ScanSearch className="w-4 h-4 mr-2" /> 开始检查
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Signal Chart Detail Modal */}
      <SignalChartModal
        signal={chartDetailSignal}
        open={isChartDetailOpen}
        onOpenChange={setIsChartDetailOpen}
      />
    </>
  );
}
