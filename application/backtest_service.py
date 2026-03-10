"""
FMZ 回测服务模块

提供基于 FMZ C++ 引擎的回测执行服务，支持：
- 多进程并发执行回测任务
- 任务状态管理（pending, running, completed, failed）
- 回测结果解析（ProfitLogs, Snapshots, 胜率统计）

架构要点：
- VCtx 是纯 CPU 密集型阻塞操作，必须使用 ProcessPoolExecutor 执行
- 任务状态存储于内存 Dict（生产环境可升级为 SQLite/Redis）
- 完全复用现有的 PinbarStrategy.evaluate() 作为策略大脑
"""
import os
import sys
import json
import time
import uuid
import asyncio
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ProcessPoolExecutor, Future
from datetime import datetime

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.entities import PinbarConfig, ScoringWeights
from domain.strategy.pinbar import PinbarStrategy
from infrastructure.backtest.fmz_adapter import fmz_records_to_bars
# NOTE: BacktestExecutor 必须在 _execute_fmz_backtest_worker 函数内部 import，
# 因为该函数运行在 ProcessPoolExecutor 独立子进程中，进程内没有父进程的模块状态。

logger = logging.getLogger(__name__)


# ==============================================================================
# 任务状态枚举
# ==============================================================================
class TaskStatus(str):
    PENDING = "pending"           # 已提交，等待执行
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 执行失败
    CANCELLED = "cancelled"       # 已取消


# ==============================================================================
# 数据类定义
# ==============================================================================
@dataclass
class BacktestTask:
    """回测任务定义"""
    task_id: str
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    start_date: str = "2024-01-01 00:00:00"
    end_date: str = "2024-02-01 00:00:00"

    # FMZ 配置
    initial_balance: float = 100000.0
    fee_maker: int = 75       # 手续费 maker (万分之 7.5)
    fee_taker: int = 80       # 手续费 taker (万分之 8)
    fee_denominator: int = 5  # 手续费分母 (5 = 万分比)
    slip_point: int = 0       # 滑点

    # 策略配置
    max_sl_dist: float = 0.035
    ema_period: int = 60
    atr_period: int = 14
    pinbar_config: Optional[Dict] = None
    scoring_weights: Optional[Dict] = None

    # 风控配置（新增）
    leverage: int = 10
    risk_pct: float = 0.02
    funding_rate: float = 0.0001

    # 运行时状态
    status: str = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    progress: int = 0  # 0-100

    # 结果缓存
    result: Optional[Dict] = None


@dataclass
class BacktestStats:
    """回测统计结果"""
    initial_balance: float = 0.0
    final_balance: float = 0.0
    total_return_pct: float = 0.0
    total_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    profit_factor: float = 0.0


# ==============================================================================
# FMZ 回测执行器（进程池函数）
# ==============================================================================
# 这个函数必须在独立的进程中执行，因为 FMZ 会污染全局命名空间
def _execute_fmz_backtest_worker(config_string: str, strategy_config: dict) -> dict:
    """
    在独立进程中执行的 FMZ 回测函数

    :param config_string: FMZ 配置字符串
    :param strategy_config: PinbarStrategy 配置字典
    :return: task.Join() 返回的原始结果字典
    """
    import sys
    import os
    import json
    import logging
    from dataclasses import asdict
    # 确保项目根目录在路径中（进程池需要重新设置）
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # 【关键】BacktestExecutor 必须在 worker 函数内部 import，不能依赖父进程的模块状态
    from infrastructure.backtest.executor import BacktestExecutor

    # 1. 直接将 fmz 导入到 worker 的全局运行环境中
    from fmz import VCtx

    # 2. 启动 C++ 引擎 (它会将 exchange 注入到 globals)
    task = VCtx(config_string)

    # 3. 从 globals() 中安全提取 exchange 对象 ！！！这是核心修复！！！
    g = globals()
    exchange = g.get('exchange')

    if not exchange:
        # 如果 globals 没有，说明底层模块注册方式改变，再尝试直接从 fmz 导入或 sys.modules 获取
        import sys as _sys
        if 'fmz' in _sys.modules and hasattr(_sys.modules['fmz'], 'exchange'):
            exchange = getattr(_sys.modules['fmz'], 'exchange')
        else:
            raise RuntimeError("Failed to get exchange object from FMZ globals()")

    # 4. 实例化策略大脑
    strategy = PinbarStrategy(
        ema_period=strategy_config.get("ema_period", 60),
        atr_period=strategy_config.get("atr_period", 14)
    )

    pinbar_config = PinbarConfig(**strategy_config.get("pinbar_config", {})) if strategy_config.get("pinbar_config") else PinbarConfig()
    scoring_weights = ScoringWeights(**strategy_config.get("scoring_weights", {})) if strategy_config.get("scoring_weights") else ScoringWeights(w_shape=0.4, w_trend=0.3, w_vol=0.3)

    max_sl_dist = strategy_config.get("max_sl_dist", 0.035)

    # 5. 实例化 BacktestExecutor（替换手工账本）
    executor = BacktestExecutor(
        initial_balance=strategy_config["initial_balance"],
        fee_maker=strategy_config.get("fee_maker", 75) / 100000,
        fee_taker=strategy_config.get("fee_taker", 80) / 100000,
        default_leverage=strategy_config.get("leverage", 10)
    )

    # 【新增】收集 K 线 OHLCV 数据，用于前端渲染 K 线图
    all_klines = []  # 存储所有 K 线 OHLCV 数据

    bar_count = 0
    last_progress_bar = 0

    # 6. 回测主循环（while True 范式）
    while True:
        try:
            records = exchange.GetRecords()
        except EOFError:
            # FMZ C++ 引擎到达回测终点
            break

        if not records:
            break

        bar_count = len(records)

        # 【新增】收集 K 线数据：取最后一根 K 线追加到 all_klines
        if records:
            last_record = records[-1]
            kline_entry = {
                "timestamp": last_record['Time'],       # 毫秒时间戳
                "open": last_record['Open'],
                "high": last_record['High'],
                "low": last_record['Low'],
                "close": last_record['Close'],
                "volume": last_record.get('Volume', 0.0),
            }
            # 避免重复追加：FMZ 返回的是到目前为止的完整最新 K 线
            # 遇到相同时间戳时，用最新的记录覆盖，以累积完整的 H/L/C 数据
            if not all_klines or all_klines[-1]["timestamp"] != kline_entry["timestamp"]:
                all_klines.append(kline_entry)
            else:
                all_klines[-1] = kline_entry

        # 进度上报（每 100 根 K 线）
        if bar_count - last_progress_bar >= 100:
            logger.info(f"回测进度：{bar_count} 根 K 线")
            last_progress_bar = bar_count

        # 数据转换
        bars = fmz_records_to_bars(
            records=records,
            symbol=strategy_config.get("symbol", "BTCUSDT"),
            interval=strategy_config.get("interval", "1h"),
            is_closed=True
        )

        # 历史数据不够 EMA 计算，跳过
        min_bars_needed = strategy_config.get("ema_period", 60)
        if len(bars) < min_bars_needed:
            continue

        # 分隔历史 K 线和当前 K 线
        history_bars = bars[:-1]
        current_bar = bars[-1]

        # 策略评估
        signal = strategy.evaluate(
            current_bar=current_bar,
            history_bars=history_bars,
            max_sl_dist=max_sl_dist,
            weights=scoring_weights,
            pinbar_config=pinbar_config
        )

        # 执行交易
        if signal:
            # 从 executor 获取可用保证金
            available_margin = executor.get_available_margin()

            # 计算仓位数量：qty = (available_margin × risk_pct × leverage) / current_bar.close
            risk_pct = strategy_config.get("risk_pct", 0.02)
            leverage = strategy_config.get("leverage", 10)

            qty = (available_margin * risk_pct * leverage) / current_bar.close

            if qty <= 0:
                logger.warning(f"[{current_bar.symbol}] 可用保证金不足，跳过开仓")
                continue

            # 调用 executor 开仓
            success = executor.open_position(
                symbol=current_bar.symbol,
                direction=signal.direction,
                quantity=qty,
                price=current_bar.close,
                leverage=leverage,
                order_type="market",
                stop_loss_price=signal.stop_loss,
                timestamp=current_bar.timestamp
            )

            if not success:
                logger.warning(f"[{current_bar.symbol}] 开仓失败，跳过本次信号")
                continue

            # 仍然调用 exchange.Buy/Sell 驱动 FMZ 引擎时间步进
            if signal.direction == 'LONG':
                exchange.Buy(current_bar.close, qty)
            else:
                exchange.Sell(current_bar.close, qty)

        # 每根 K 线末尾：更新权益并检查止损
        prices = {current_bar.symbol: current_bar.close}
        executor.update_equity(prices, current_bar.timestamp)

        # 检查现有持仓是否触及止损价
        executor.check_stop_loss(prices, current_bar.timestamp)

    # 7. 强制平仓所有持仓（以最后一根 K 线收盘价平仓）
    if records:
        final_bar = fmz_records_to_bars(
            records=[records[-1]],
            symbol=strategy_config.get("symbol", "BTCUSDT"),
            interval=strategy_config.get("interval", "1h"),
            is_closed=True
        )
        if final_bar:
            final_price = final_bar[-1].close
            # 平仓所有活跃持仓
            for position in list(executor.get_all_positions()):
                executor.close_position(position.id, final_price, order_type="market", timestamp=final_bar[-1].timestamp)
                logger.info(f"[{position.symbol}] 回测结束强制平仓 @ {final_price}")

    # 8. 回收 FMZ 结果
    result = task.Join()

    # bytes 转字符串
    if isinstance(result, bytes):
        result = result.decode('utf-8')

    result_dict = json.loads(result)

    # 9. 注入 CustomMetrics（使用 executor 的数据）
    stats = executor.get_stats()

    # 从 strategy_config 读取风控参数
    leverage = strategy_config.get("leverage", 10)
    risk_pct = strategy_config.get("risk_pct", 0.02)
    funding_rate = strategy_config.get("funding_rate", 0.0001)

    # 计算资金费（简化估算）
    total_funding_fees = stats['total_trades'] * funding_rate * executor.initial_balance / leverage

    # 【新增】为 trade_records 增加 kline_index 字段
    # 构建 K 线时间戳到索引的映射
    kline_ts_set = {k["timestamp"]: i for i, k in enumerate(all_klines)}

    # 为每条交易记录添加 kline_index
    trade_records_with_index = []
    for r in executor.get_trade_records():
        rd = asdict(r)
        rd["kline_index"] = kline_ts_set.get(r.timestamp, -1)  # -1 表示找不到对应 K 线
        trade_records_with_index.append(rd)

    result_dict["CustomMetrics"] = {
        **stats,
        "initial_balance": executor.initial_balance,
        "final_balance": executor.balance,
        "equity_curve": executor.get_equity_curve(),
        "trade_records": trade_records_with_index,  # 使用带 kline_index 的版本
        "klines": all_klines,  # 【新增】K 线 OHLCV 数据
        "interval": strategy_config["interval"],
        # 新增字段
        "leverage_used": leverage,
        "risk_pct": risk_pct,
        "funding_rate": funding_rate,
        "total_fees": stats.get("total_fees", 0),
        "total_funding_fees": total_funding_fees,
        "sharpe_ratio": stats.get("sharpe_ratio", 0),
    }

    logger.info(f"[Worker] CustomMetrics: total_trades={stats['total_trades']}, "
                f"win={stats['win_count']}, loss={stats['loss_count']}, "
                f"return={stats['total_return_pct']:.2f}%, leverage={leverage}, "
                f"final_balance={executor.balance:.2f}")

    return result_dict


# ==============================================================================
# FMZ 结果解析器
# ==============================================================================
class FMZResultParser:
    """
    FMZ 回测结果解析器

    从 task.Join() 返回的 JSON 字典中提取：
    - 基础统计（余额、盈亏、胜率）
    - 权益曲线（ProfitLogs）
    - 交易日志（RuntimeLogs）
    """

    @staticmethod
    def parse(raw_result: Dict) -> Dict[str, Any]:
        """
        解析原始结果

        :param raw_result: task.Join() 返回的字典
        :return: 解析后的前端友好格式
        """
        if not raw_result:
            return {"error": "Empty result"}

        # 1. 提取基础快照
        snapshots = raw_result.get("Snapshots", [])
        stats = FMZResultParser._extract_stats(snapshots, raw_result)

        # 2. 提取权益曲线
        equity_curve = FMZResultParser._extract_profit_logs(raw_result)

        # 3. 提取交易日志
        trade_logs = FMZResultParser._extract_trade_logs(raw_result)

        # 4. 计算详细统计
        detailed_stats = FMZResultParser._calculate_detailed_stats(raw_result, trade_logs)

        return {
            "stats": {**asdict(stats), **detailed_stats},
            "equityCurve": equity_curve,
            "tradeLogs": trade_logs,
            "raw": raw_result  # 保留原始数据供调试
        }

    @staticmethod
    def _extract_stats(snapshots: List, raw_result: Dict) -> BacktestStats:
        """
        提取基础统计

        修复：如果 FMZ 返回的 balance 为 0，使用 custom_metrics 中的 initial_balance
        """
        stats = BacktestStats()

        # 优先使用 custom_metrics（手工账本）的数据
        custom_metrics = raw_result.get("CustomMetrics", {})
        if custom_metrics:
            stats.initial_balance = custom_metrics.get("initial_balance", 0.0)
            stats.final_balance = custom_metrics.get("final_balance", 0.0)
            stats.total_pnl = stats.final_balance - stats.initial_balance
            stats.total_trades = custom_metrics.get("total_trades", 0)
            stats.win_count = custom_metrics.get("win_count", 0)
            stats.loss_count = custom_metrics.get("loss_count", 0)

            if stats.initial_balance > 0:
                stats.total_return_pct = round((stats.final_balance - stats.initial_balance) / stats.initial_balance * 100, 2)

            # 【修复 1 - P0-1】MDD 计算基准修正：从权益曲线计算最大回撤
            equity_curve = custom_metrics.get("equity_curve", [])
            if equity_curve:
                peak_equity = equity_curve[0].get("equity", equity_curve[0].get("balance", 0)) if isinstance(equity_curve[0], dict) else 0
                max_drawdown = 0.0
                for point in equity_curve:
                    current_equity = point.get("equity", point.get("balance", 0)) if isinstance(point, dict) else 0
                    if current_equity > peak_equity:
                        peak_equity = current_equity
                    drawdown = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
                stats.max_drawdown_pct = round(max_drawdown * 100, 2)

            return stats

        # 降级：使用 FMZ 原生 Snapshots
        if snapshots:
            # 初始快照
            initial = snapshots[0][1][0] if snapshots[0][1] else {}
            # 最终快照
            final = snapshots[-1][1][0] if snapshots[-1][1] else {}

            # 【修复】如果 balance 为 0，强制使用 Initial 或 fallback
            stats.initial_balance = initial.get("Initial", 0.0) or initial.get("Balance", 0.0)
            stats.final_balance = final.get("Balance", 0.0)
            stats.total_pnl = final.get("PnL", 0.0)

            # 【修复】如果 initial_balance 仍为 0，使用默认值 100000
            if stats.initial_balance == 0.0:
                stats.initial_balance = 100000.0

            if stats.initial_balance > 0:
                stats.total_return_pct = round((stats.final_balance - stats.initial_balance) / stats.initial_balance * 100, 2)

        return stats

    @staticmethod
    def _extract_profit_logs(raw_result: Dict) -> List[Dict]:
        """
        提取盈亏日志（权益曲线）

        修复：
        1. 优先使用 CustomMetrics["equity_curve"]（从 BacktestExecutor）
        2. 降级使用 custom_profit_logs（手工账本）
        3. 再降级从 Snapshots 提取

        equity_curve 格式（从 BacktestExecutor）：
        [
            {
                "timestamp": int,
                "balance": float,
                "unrealized_pnl": float,
                "total_equity": float,
                "margin_used": float,
                "free_margin": float,
            },
            ...
        ]
        """
        custom_metrics = raw_result.get("CustomMetrics", {})
        initial_balance = custom_metrics.get("initial_balance", 100000.0)

        # 【修复】优先使用 equity_curve（从 BacktestExecutor）
        equity_curve_data = custom_metrics.get("equity_curve", [])

        if equity_curve_data and len(equity_curve_data) > 0:
            # 检查是否是 dict 列表（从 asdict 转换）
            if isinstance(equity_curve_data[0], dict):
                # 从 equity_curve 构建前端友好的格式
                equity_curve = []
                for point in equity_curve_data:
                    equity_curve.append({
                        "timestamp": point.get("timestamp", 0),
                        "balance": point.get("balance", 0),
                        "pnl": point.get("total_equity", 0) - initial_balance,
                        "equity": point.get("total_equity", 0),
                        "utilization": point.get("margin_used", 0) / point.get("total_equity", 1) if point.get("total_equity", 0) > 0 else 0,
                    })
                return equity_curve

        # 降级：使用 custom_profit_logs（旧格式兼容）
        custom_profit_logs = custom_metrics.get("custom_profit_logs", [])

        if custom_profit_logs:
            # 从 custom_profit_logs 构建权益曲线
            equity_curve = []
            current_balance = initial_balance

            # 添加起点
            equity_curve.append({
                "timestamp": 0,
                "balance": initial_balance,
                "pnl": 0.0,
                "utilization": 0.0
            })

            # 添加每个平仓事件的权益点
            for log in custom_profit_logs:
                current_balance = log.get("balance_after", current_balance + log.get("profit", 0))
                pnl = current_balance - initial_balance
                equity_curve.append({
                    "timestamp": log.get("timestamp", 0),
                    "balance": current_balance,
                    "pnl": pnl,
                    "utilization": 0.0
                })

            return equity_curve

        # 降级：使用 FMZ 原生 Snapshots
        equity_curve = []
        snapshots = raw_result.get("Snapshots", [])
        last_timestamp = -1

        for snapshot in snapshots:
            if len(snapshot) >= 2:
                timestamp = snapshot[0]
                # 【修复】跳过重复的时间戳
                if timestamp == last_timestamp:
                    continue
                last_timestamp = timestamp

                account = snapshot[1][0] if snapshot[1] else {}
                balance = account.get("Balance", 0.0)
                pnl = account.get("PnL", 0.0)

                # 【修复】如果 balance 为 0，使用 initial_balance 修正
                if balance == 0.0:
                    balance = initial_balance + pnl

                equity_curve.append({
                    "timestamp": timestamp,
                    "balance": balance,
                    "pnl": pnl,
                    "utilization": account.get("Utilization", 0.0)
                })

        return equity_curve

    @staticmethod
    def _extract_trade_logs(raw_result: Dict) -> List[Dict]:
        """
        提取交易日志

        优先从 CustomMetrics["trade_records"] 读取（TradeRecord 字典列表），
        格式化为前端友好的 tradeLogs 格式（含 action_name、direction、realized_pnl 等字段）。

        降级：如果 trade_records 不存在，从 RuntimeLogs 提取。

        TradeRecord 格式（从 BacktestExecutor）：
        {
            "id": str,
            "position_id": str,
            "symbol": str,
            "action": str,              # "OPEN" 或 "CLOSE"
            "direction": str,           # "LONG" 或 "SHORT"
            "quantity": float,
            "price": float,
            "order_type": str,
            "fee": float,
            "fee_rate": float,
            "pnl": float,               # 实现盈亏（仅平仓时有值）
            "timestamp": int,
        }
        """
        trade_logs = []
        custom_metrics = raw_result.get("CustomMetrics", {})

        # 优先使用 trade_records（从 BacktestExecutor）
        trade_records = custom_metrics.get("trade_records", [])

        if trade_records:
            # 从 trade_records 构建交易日志
            for record in trade_records:
                action_str = record.get("action", "")
                direction = record.get("direction", "")
                timestamp = record.get("timestamp", 0)
                price = record.get("price", 0)
                amount = record.get("quantity", 0)
                value = amount * price
                realized_pnl = record.get("pnl", 0)
                fee = record.get("fee", 0)
                symbol = record.get("symbol", "")

                # 将 action 字符串转换为整数码
                # 1=OPEN_LONG, 2=OPEN_SHORT, 3=CLOSE_LONG, 4=CLOSE_SHORT
                if action_str == "OPEN":
                    action_code = 1 if direction == "LONG" else 2
                    action_name = f"OPEN_{direction}"
                elif action_str == "CLOSE":
                    action_code = 3 if direction == "LONG" else 4
                    action_name = f"CLOSE_{direction}"
                else:
                    action_code = 0
                    action_name = action_str

                log_entry = {
                    "action": action_code,
                    "action_name": action_name,
                    "direction": direction,
                    "timestamp": timestamp,
                    "datetime": datetime.fromtimestamp(timestamp / 1000).isoformat() if timestamp else None,
                    "price": price,
                    "amount": amount,
                    "value": value,
                    "realized_pnl": realized_pnl,
                    "fee": fee,
                    "position_qty": 0,  # TradeRecord 没有 position_qty，需要从持仓聚合
                    "symbol": symbol,
                }
                trade_logs.append(log_entry)

            return trade_logs

        # 降级：使用 RuntimeLogs（FMZ 原生格式）
        runtime_logs = raw_result.get("RuntimeLogs", [])

        for log in runtime_logs:
            if len(log) >= 10:
                action = log[0]
                timestamp = log[1]

                # 只保留 BUY(1) 和 SELL(2)，过滤其他垃圾日志
                if action not in [1, 2]:
                    continue

                log_entry = {
                    "action": action,
                    "action_name": FMZResultParser._action_to_string(action),
                    "direction": "",  # RuntimeLogs 没有方向信息
                    "timestamp": timestamp,
                    "datetime": datetime.fromtimestamp(timestamp / 1000).isoformat() if timestamp else None,
                    "price": log[5] if len(log) > 5 else 0,
                    "amount": log[6] if len(log) > 6 else 0,
                    "value": 0,
                    "realized_pnl": 0,
                    "fee": 0,
                    "position_qty": 0,
                    "symbol": log[8] if len(log) > 8 else "",
                }

                trade_logs.append(log_entry)

        return trade_logs

    @staticmethod
    def _action_to_string(action: int) -> str:
        """动作码转字符串"""
        mapping = {
            1: "OPEN_LONG",
            2: "OPEN_SHORT",
            3: "CLOSE_LONG",
            4: "CLOSE_SHORT",
            11: "BUY",       # 旧格式兼容
            12: "SELL",      # 旧格式兼容
        }
        return mapping.get(action, str(action))

    @staticmethod
    def _calculate_detailed_stats(raw_result: Dict, trade_logs: List[Dict]) -> Dict[str, Any]:
        """
        计算详细统计

        修复：优先使用 custom_metrics 中的真实交易数据计算胜率
        """
        # 【修复】优先使用 custom_metrics（手工账本）的数据
        custom_metrics = raw_result.get("CustomMetrics", {})

        if custom_metrics:
            total_trades = custom_metrics.get("total_trades", 0)
            win_count = custom_metrics.get("win_count", 0)
            loss_count = custom_metrics.get("loss_count", 0)

            # 【修复】从 trade_records（CLOSE 记录）读取 PnL，而非旧的 custom_profit_logs
            # trade_records 中 pnl 字段仅 CLOSE 记录有值，OPEN 记录 pnl=0.0
            trade_records = custom_metrics.get("trade_records", [])
            close_records = [r for r in trade_records if r.get("action") == "CLOSE"]
            gross_profit = sum(r.get("pnl", 0) for r in close_records if r.get("pnl", 0) > 0)
            gross_loss = abs(sum(r.get("pnl", 0) for r in close_records if r.get("pnl", 0) < 0))
            profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0

            total_closed = win_count + loss_count
            win_rate = round(win_count / total_closed * 100, 2) if total_closed > 0 else 0

            # 【修复 2 - P0-2】夏普比率年化因子修正
            # 从 interval 推算每日 K 线数
            interval = custom_metrics.get("interval", "1h")
            interval_to_bars_per_day = {
                "1m": 1440, "5m": 288, "15m": 96, "30m": 48,
                "1h": 24, "4h": 6, "1d": 1
            }
            bars_per_day = interval_to_bars_per_day.get(interval, 24)

            # 从 equity_curve 提取日收益率序列
            equity_curve = custom_metrics.get("equity_curve", [])
            daily_returns = []
            if equity_curve and len(equity_curve) >= 2:
                # 按日期分组，取每日最后一条的权益值
                daily_equity = {}
                for point in equity_curve:
                    if isinstance(point, dict):
                        ts = point.get("timestamp", 0)
                        eq = point.get("equity", point.get("balance", 0))
                        date = ts // (86400 * 1000) if ts > 0 else 0  # 毫秒时间戳转天
                        daily_equity[date] = eq

                # 计算日收益率
                sorted_dates = sorted(daily_equity.keys())
                for i in range(1, len(sorted_dates)):
                    prev_eq = daily_equity[sorted_dates[i - 1]]
                    curr_eq = daily_equity[sorted_dates[i]]
                    if prev_eq > 0:
                        daily_returns.append((curr_eq - prev_eq) / prev_eq)

            # 计算夏普比率
            if len(daily_returns) >= 2:
                import statistics
                mean_return = statistics.mean(daily_returns)
                std_return = statistics.stdev(daily_returns)  # ddof=1
                sharpe_ratio = round((mean_return / std_return) * (252 ** 0.5), 2) if std_return > 0 else 0
            else:
                sharpe_ratio = 0

            # 【修复】新动作码：1=OPEN_LONG, 2=OPEN_SHORT, 3=CLOSE_LONG, 4=CLOSE_SHORT
            # 旧格式降级路径（RuntimeLogs）中 action=1 表示 BUY，action=2 表示 SELL
            # 现在 trade_records 路径下 buy_count/sell_count 统计开多和开空次数
            return {
                "buy_count": sum(1 for log in trade_logs if log.get("action") in [1, 2]),   # 所有开仓
                "sell_count": sum(1 for log in trade_logs if log.get("action") in [3, 4]),  # 所有平仓
                "error_count": 0,
                "win_count": win_count,
                "loss_count": loss_count,
                "total_closed": total_closed,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "sharpe_ratio": sharpe_ratio,
            }

        # 降级：使用原有逻辑
        # 统计交易次数
        buy_count = sum(1 for log in trade_logs if log.get("action") == 1)
        sell_count = sum(1 for log in trade_logs if log.get("action") == 2)
        error_count = sum(1 for log in trade_logs if log.get("action") == 3)

        # 从 ProfitLogs 计算胜率
        profit_logs = raw_result.get("ProfitLogs", [])
        win_count = sum(1 for log in profit_logs if log.get("Profit", 0) > 0) if profit_logs else 0
        loss_count = sum(1 for log in profit_logs if log.get("Profit", 0) < 0) if profit_logs else 0
        total_closed = win_count + loss_count

        win_rate = round(win_count / total_closed * 100, 2) if total_closed > 0 else 0

        # 计算盈亏比
        gross_profit = sum(log.get("Profit", 0) for log in profit_logs if log.get("Profit", 0) > 0) if profit_logs else 0
        gross_loss = abs(sum(log.get("Profit", 0) for log in profit_logs if log.get("Profit", 0) < 0)) if profit_logs else 0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0

        return {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "error_count": error_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "total_closed": total_closed,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "sharpe_ratio": 0,  # 降级模式下不计算夏普比率
        }


# ==============================================================================
# 回测服务（主类）
# ==============================================================================
class BacktestService:
    """
    回测服务

    特性：
    - 使用 ProcessPoolExecutor 实现多进程并发
    - 内存 Dict 管理任务状态
    - 支持任务查询和结果获取
    """

    def __init__(self, max_workers: int = 4):
        """
        初始化回测服务

        :param max_workers: 最大并发进程数
        """
        self.max_workers = max_workers
        self.executor = ProcessPoolExecutor(max_workers=max_workers)

        # 任务状态存储（内存 Dict）
        # 生产环境可升级为 SQLite/Redis
        self.tasks: Dict[str, BacktestTask] = {}
        self.futures: Dict[str, Future] = {}

        logger.info(f"BacktestService 初始化完成，最大并发数：{max_workers}")

    def shutdown(self):
        """关闭服务"""
        self.executor.shutdown(wait=False)
        logger.info("BacktestService 已关闭")

    def create_task(self, config: Dict[str, Any]) -> BacktestTask:
        """
        创建回测任务

        :param config: 任务配置字典
        :return: BacktestTask 实例
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        task = BacktestTask(
            task_id=task_id,
            symbol=config.get("symbol", "BTCUSDT"),
            interval=config.get("interval", "1h"),
            start_date=config.get("start_date", "2024-01-01 00:00:00"),
            end_date=config.get("end_date", "2024-02-01 00:00:00"),
            initial_balance=config.get("initial_balance", 100000.0),
            fee_maker=config.get("fee_maker", 75),
            fee_taker=config.get("fee_taker", 80),
            fee_denominator=config.get("fee_denominator", 5),
            slip_point=config.get("slip_point", 0),
            max_sl_dist=config.get("max_sl_dist", 0.035),
            ema_period=config.get("ema_period", 60),
            atr_period=config.get("atr_period", 14),
            pinbar_config=config.get("pinbar_config"),
            scoring_weights=config.get("scoring_weights"),
            # 风控配置（新增）
            leverage=config.get("leverage", 10),
            risk_pct=config.get("risk_pct", 0.02),
            funding_rate=config.get("funding_rate", 0.0001),
        )

        self.tasks[task_id] = task
        logger.info(f"创建回测任务：{task_id}")

        return task

    async def run_backtest(self, task: BacktestTask) -> str:
        """
        运行回测任务（异步提交到进程池）

        :param task: BacktestTask 实例
        :return: task_id
        """
        # 更新状态
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        # 构建 FMZ 配置字符串
        config_string = self._build_fmz_config(task)

        # 构建策略配置
        strategy_config = {
            "symbol": task.symbol,
            "interval": task.interval,
            "max_sl_dist": task.max_sl_dist,
            "ema_period": task.ema_period,
            "atr_period": task.atr_period,
            "pinbar_config": task.pinbar_config or {},
            "scoring_weights": task.scoring_weights or {
                "w_shape": 0.4, "w_trend": 0.3, "w_vol": 0.3
            },
            # 风控配置（新增）
            "leverage": task.leverage,
            "risk_pct": task.risk_pct,
            "funding_rate": task.funding_rate,
            "initial_balance": task.initial_balance,
            "fee_maker": task.fee_maker,
            "fee_taker": task.fee_taker,
            "fee_denominator": task.fee_denominator,
        }

        # 提交到进程池
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            self.executor,
            _execute_fmz_backtest_worker,
            config_string,
            strategy_config
        )

        self.futures[task.task_id] = future

        # 添加回调
        future.add_done_callback(lambda f: self._on_task_complete(task, f))

        logger.info(f"回测任务已提交：{task.task_id}")
        return task.task_id

    def _build_fmz_config(self, task: BacktestTask) -> str:
        """
        构建 FMZ 配置字符串

        格式：
        backtest
        start: 2024-01-01 00:00:00
        end: 2024-02-01 00:00:00
        period: 1h
        exchanges: [{"eid":"Binance","currency":"BTC_USDT","balance":100000}]
        """
        # 转换币种格式（BTCUSDT -> BTC_USDT）
        currency = task.symbol.replace("USDT", "_USDT")

        config = f"""backtest
start: {task.start_date}
end: {task.end_date}
period: {task.interval}
exchanges: [{{"eid":"Binance","currency":"{currency}","balance":{task.initial_balance},"fee_maker":{task.fee_maker},"fee_taker":{task.fee_taker},"fee_denominator":{task.fee_denominator},"slip_point":{task.slip_point}}}]
"""
        return config

    def _on_task_complete(self, task: BacktestTask, future: Future):
        """
        任务完成回调

        :param task: BacktestTask 实例
        :param future: Future 对象
        """
        task.completed_at = time.time()

        try:
            result = future.result()
            logger.info(f"[Callback] task={task.task_id}, result type={type(result)}, has CustomMetrics={'CustomMetrics' in result if result else 'N/A'}")
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            logger.info(f"回测任务完成：{task.task_id}")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.error(f"回测任务失败：{task.task_id}, 错误：{e}")

    def get_task(self, task_id: str) -> Optional[BacktestTask]:
        """获取任务信息"""
        return self.tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[BacktestTask]:
        """
        获取任务列表

        :param status: 可选的状态过滤
        :return: BacktestTask 列表
        """
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    def get_task_result(self, task_id: str) -> Optional[Dict]:
        """
        获取任务解析结果

        :param task_id: 任务 ID
        :return: 解析后的结果字典
        """
        task = self.tasks.get(task_id)
        if not task or not task.result:
            return None

        # 解析结果
        parsed = FMZResultParser.parse(task.result)
        return parsed


# ==============================================================================
# 全局服务实例
# ==============================================================================
# 单例模式，在 main.py 中初始化
_backtest_service: Optional[BacktestService] = None


def get_backtest_service() -> BacktestService:
    """获取 BacktestService 单例"""
    global _backtest_service
    if _backtest_service is None:
        _backtest_service = BacktestService(max_workers=4)
    return _backtest_service


def shutdown_backtest_service():
    """关闭 BacktestService"""
    global _backtest_service
    if _backtest_service:
        _backtest_service.shutdown()
        _backtest_service = None
