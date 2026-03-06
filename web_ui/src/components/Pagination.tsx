import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

interface PaginationProps {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
  onSizeChange: (size: number) => void;
}

export function Pagination({
  page,
  size,
  total,
  onPageChange,
  onSizeChange,
}: PaginationProps) {
  const [jumpPage, setJumpPage] = useState("");

  const totalPages = Math.ceil(total / size);
  const startItem = (page - 1) * size + 1;
  const endItem = Math.min(page * size, total);

  const handleJumpToPage = () => {
    const pageNum = parseInt(jumpPage, 10);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      onPageChange(pageNum);
      setJumpPage("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleJumpToPage();
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 py-4">
      {/* 左侧：单页大小选择器 */}
      <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
        <span>每页显示</span>
        <Select value={size.toString()} onValueChange={(v) => onSizeChange(parseInt(v, 10))}>
          <SelectTrigger className="w-[70px] h-8 bg-transparent border-zinc-200 dark:border-zinc-800">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="10">10</SelectItem>
            <SelectItem value="20">20</SelectItem>
            <SelectItem value="50">50</SelectItem>
            <SelectItem value="100">100</SelectItem>
          </SelectContent>
        </Select>
        <span>条</span>
      </div>

      {/* 中间：页码信息 */}
      <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
        <span>
          第 {page} 页 / 共 {totalPages} 页 ({total} 条)
        </span>
        {total > 0 && (
          <span className="text-xs opacity-60">
            (显示 {startItem}-{endItem} 条)
          </span>
        )}
      </div>

      {/* 右侧：分页控制 */}
      <div className="flex items-center gap-1">
        {/* 首页按钮 */}
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 border-zinc-200 dark:border-zinc-800"
          onClick={() => onPageChange(1)}
          disabled={page === 1}
        >
          <ChevronsLeft className="w-4 h-4" />
        </Button>

        {/* 上一页按钮 */}
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 border-zinc-200 dark:border-zinc-800"
          onClick={() => onPageChange(page - 1)}
          disabled={page === 1}
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>

        {/* 页码跳转输入 */}
        <div className="flex items-center gap-1 px-2">
          <Input
            type="number"
            min={1}
            max={totalPages}
            value={jumpPage}
            onChange={(e) => setJumpPage(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-16 h-8 text-center bg-transparent border-zinc-200 dark:border-zinc-800"
            placeholder={totalPages.toString()}
          />
          <Button
            variant="outline"
            size="sm"
            className="h-8 px-2 border-zinc-200 dark:border-zinc-800"
            onClick={handleJumpToPage}
            disabled={!jumpPage || totalPages === 0}
          >
            跳转
          </Button>
        </div>

        {/* 下一页按钮 */}
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 border-zinc-200 dark:border-zinc-800"
          onClick={() => onPageChange(page + 1)}
          disabled={page === totalPages || totalPages === 0}
        >
          <ChevronRight className="w-4 h-4" />
        </Button>

        {/* 末页按钮 */}
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 border-zinc-200 dark:border-zinc-800"
          onClick={() => onPageChange(totalPages)}
          disabled={page === totalPages || totalPages === 0}
        >
          <ChevronsRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
