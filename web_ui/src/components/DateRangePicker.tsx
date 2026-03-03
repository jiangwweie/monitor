import * as React from "react";
import { format } from "date-fns";
import { Calendar as CalendarIcon, Clock } from "lucide-react";
import type { DateRange } from "react-day-picker";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface DateRangePickerProps extends React.ComponentProps<"div"> {
  /** 选中的日期范围 */
  dateRange: DateRange | undefined;
  /** 日期范围变化回调 */
  onDateRangeChange: (dateRange: DateRange | undefined) => void;
  /** 快捷选项标签 */
  presetLabel?: string;
  /** 是否显示时间选择 */
  showTimePicker?: boolean;
  /** 自定义类名 */
  className?: string;
}

/**
 * 日期范围选择器组件
 *
 * 功能:
 * - 预设快捷选项：最近 1 小时、最近 24 小时、最近 7 天、全部
 * - 自定义日期时间选择
 * - 与 SignalRadar 筛选条件联动
 *
 * @example
 * ```tsx
 * const [dateRange, setDateRange] = React.useState<DateRange>();
 *
 * <DateRangePicker
 *   dateRange={dateRange}
 *   onDateRangeChange={setDateRange}
 *   presetLabel="时间范围"
 * />
 * ```
 */
export function DateRangePicker({
  dateRange,
  onDateRangeChange,
  presetLabel = "快捷选择",
  showTimePicker = false,
  className,
}: DateRangePickerProps) {
  const [open, setOpen] = React.useState(false);

  // 预设选项处理
  const handlePresetChange = (value: string) => {
    const now = new Date();
    let from: Date;
    let to: Date = now;

    switch (value) {
      case "1h":
        from = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case "24h":
        from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      case "7d":
        from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case "all":
        onDateRangeChange(undefined);
        setOpen(false);
        return;
      default:
        from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    }

    onDateRangeChange({ from, to });
    setOpen(false);
  };

  // 获取当前选中的预设值
  const getCurrentPreset = (): string => {
    if (!dateRange?.from) return "24h";

    const now = new Date();
    const from = dateRange.from;
    const diffMs = now.getTime() - from.getTime();

    // 允许 1 分钟的误差范围
    const oneHour = 60 * 60 * 1000;
    const oneDay = 24 * 60 * 60 * 1000;
    const sevenDays = 7 * oneDay;

    if (Math.abs(diffMs - oneHour) < 60 * 1000) return "1h";
    if (Math.abs(diffMs - oneDay) < 60 * 1000) return "24h";
    if (Math.abs(diffMs - sevenDays) < 60 * 1000) return "7d";

    return "custom";
  };

  const currentPreset = getCurrentPreset();

  // 格式化显示文本
  const formatDisplayText = () => {
    if (!dateRange?.from) {
      return "全部时间";
    }

    const fromStr = showTimePicker
      ? format(dateRange.from, "yyyy-MM-dd HH:mm")
      : format(dateRange.from, "yyyy-MM-dd");

    if (dateRange.to) {
      const toStr = showTimePicker
        ? format(dateRange.to, "yyyy-MM-dd HH:mm")
        : format(dateRange.to, "yyyy-MM-dd");
      return `${fromStr} - ${toStr}`;
    }

    return `${fromStr} - 至今`;
  };

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {/* 预设选项下拉框 */}
      <Select value={currentPreset} onValueChange={handlePresetChange}>
        <SelectTrigger className="w-[140px] h-9 bg-transparent border-zinc-200 dark:border-zinc-800 text-xs">
          <SelectValue placeholder={presetLabel} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="1h">最近 1 小时</SelectItem>
          <SelectItem value="24h">最近 24 小时</SelectItem>
          <SelectItem value="7d">最近 7 天</SelectItem>
          <SelectItem value="all">全部</SelectItem>
          <SelectItem value="custom">自定义...</SelectItem>
        </SelectContent>
      </Select>

      {/* 自定义日期选择器 */}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className={cn(
              "h-9 justify-start text-left font-normal",
              !dateRange?.from && "text-muted-foreground"
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            <span className="text-xs">
              {formatDisplayText()}
            </span>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <div className="p-3 border-b border-zinc-200 dark:border-zinc-800">
            <div className="flex items-center gap-2 text-sm text-zinc-500">
              <Clock className="w-4 h-4" />
              <span>自定义日期范围</span>
            </div>
          </div>
          <Calendar
            initialFocus
            mode="range"
            defaultMonth={dateRange?.from}
            selected={dateRange}
            onSelect={(range) => {
              if (range) {
                onDateRangeChange(range);
              }
            }}
            numberOfMonths={2}
          />
          {showTimePicker && (
            <div className="p-3 border-t border-zinc-200 dark:border-zinc-800">
              <p className="text-xs text-zinc-500 text-center">
                时间选择功能敬请期待
              </p>
            </div>
          )}
        </PopoverContent>
      </Popover>
    </div>
  );
}

/**
 * 简化的日期范围选择器 (仅预设选项)
 */
export interface SimpleDateRangePickerProps {
  dateRange: DateRange | undefined;
  onDateRangeChange: (dateRange: DateRange | undefined) => void;
  className?: string;
}

export function SimpleDateRangePicker({
  dateRange,
  onDateRangeChange,
  className,
}: SimpleDateRangePickerProps) {
  const handlePresetChange = (value: string) => {
    const now = new Date();
    let from: Date;
    let to: Date = now;

    switch (value) {
      case "1h":
        from = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case "24h":
        from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      case "7d":
        from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case "all":
        onDateRangeChange(undefined);
        return;
      default:
        from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    }

    onDateRangeChange({ from, to });
  };

  return (
    <Select
      value={
        !dateRange?.from
          ? "all"
          : dateRange.to
          ? (() => {
              const diffMs = dateRange.to.getTime() - dateRange.from.getTime();
              const oneHour = 60 * 60 * 1000;
              const oneDay = 24 * 60 * 60 * 1000;
              const sevenDays = 7 * oneDay;
              if (Math.abs(diffMs - oneHour) < 60 * 1000) return "1h";
              if (Math.abs(diffMs - oneDay) < 60 * 1000) return "24h";
              if (Math.abs(diffMs - sevenDays) < 60 * 1000) return "7d";
              return "custom";
            })()
          : "24h"
      }
      onValueChange={handlePresetChange}
    >
      <SelectTrigger className={cn("w-[120px] h-8", className)}>
        <SelectValue placeholder="时间范围" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="1h">最近 1 小时</SelectItem>
        <SelectItem value="24h">最近 24 小时</SelectItem>
        <SelectItem value="7d">最近 7 天</SelectItem>
        <SelectItem value="all">全部</SelectItem>
      </SelectContent>
    </Select>
  );
}
