import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ShieldCheck, Loader2 } from "lucide-react";

interface PositionDetailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  position: any | null;
  loading: boolean;
}

export function PositionDetailModal({
  open,
  onOpenChange,
  position,
  loading,
}: PositionDetailModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-white dark:bg-zinc-900 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-zinc-100 rounded-3xl p-6 shadow-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-500" />
            持仓风控详情 ({position?.symbol})
          </DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="flex justify-center items-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
          </div>
        ) : position ? (
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-50 dark:bg-black/20 p-3 rounded-2xl">
                <p className="text-xs text-zinc-500 mb-1">方向与杠杆</p>
                <p
                  className={`font-mono text-xl font-bold ${
                    position.direction === "LONG"
                      ? "text-emerald-500"
                      : "text-rose-500"
                  }`}
                >
                  {position.direction === "LONG" ? "做多" : "做空"}{" "}
                  <span className="text-sm font-medium text-zinc-500 ml-1">
                    {position.leverage}x
                  </span>
                </p>
              </div>
              <div className="bg-zinc-50 dark:bg-black/20 p-3 rounded-2xl">
                <p className="text-xs text-zinc-500 mb-1">仓位数量</p>
                <p className="font-mono text-xl font-bold text-zinc-900 dark:text-zinc-100">
                  {position.quantity}
                </p>
              </div>
            </div>

            <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl">
              <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-2">
                核心盈亏信息
              </p>
              <div className="flex justify-between items-center text-sm">
                <span className="text-zinc-500">仓位价值 (Value)</span>
                <span className="font-mono text-zinc-900 dark:text-zinc-100">
                  ${Number(position.position_value || 0).toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-zinc-500">未实现盈亏 (Unrealized PnL)</span>
                <span
                  className={`font-mono font-bold ${
                    Number(position.unrealized_pnl || 0) >= 0
                      ? "text-emerald-500"
                      : "text-rose-500"
                  }`}
                >
                  {Number(position.unrealized_pnl || 0) > 0 ? "+" : ""}
                  {Number(position.unrealized_pnl || 0).toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-zinc-500">开单时间 (Open Time)</span>
                <span className="font-mono text-zinc-900 dark:text-zinc-100">
                  {new Date(position.open_time || 0).toLocaleString()}
                </span>
              </div>
            </div>

            <div className="space-y-3 bg-zinc-50 dark:bg-black/20 p-4 rounded-2xl">
              <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-2">
                风控委托单
              </p>
              <div className="flex justify-between items-center text-sm">
                <span className="text-zinc-500">止盈价格 (TP)</span>
                <span className="font-mono text-emerald-500">
                  {position.take_profit_price
                    ? `$${Number(position.take_profit_price).toFixed(4)}`
                    : "未设置"}
                </span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-zinc-500">止损价格 (SL)</span>
                <span className="font-mono text-rose-500">
                  {position.stop_loss_price
                    ? `$${Number(position.stop_loss_price).toFixed(4)}`
                    : "未设置"}
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="py-8 text-center text-zinc-500 text-sm">无可用数据</div>
        )}
      </DialogContent>
    </Dialog>
  );
}
