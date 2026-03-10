"""
回测执行器模块

提供基于内存的永续合约回测执行引擎，支持：
- 多/空双向开仓
- 全仓或部分平仓
- 逐 K 线更新浮动盈亏和权益曲线
- 开仓前保证金校验
- Maker/Taker 差异化手续费
- 完整的回测统计指标计算

架构设计：
- 使用 dataclass 作为纯数据载体
- 所有金额计算使用 float（生产环境可升级为 Decimal）
- 权益曲线逐 K 线快照，用于 MDD 和 Sharpe 计算
- 严格区分"余额 balance"和"总权益 equity"
"""
import math
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# ==============================================================================
# 数据类定义
# ==============================================================================
@dataclass
class Position:
    """
    持仓数据类

    表示一个未平仓的永续合约持仓。
    支持多/空双向，quantity > 0 为多仓，direction 字段表示方向。

    Attributes:
        id: 持仓唯一 ID
        symbol: 交易对 (如 "BTCUSDT")
        direction: 持仓方向 "LONG" 或 "SHORT"
        quantity: 持仓数量 (绝对值)
        entry_price: 开仓均价
        leverage: 杠杆倍数
        initial_qty: 初始开仓数量 (用于计算手续费分摊，开仓时赋值)
        stop_loss_price: 止损价格 (可选)
        unrealized_pnl: 未实现盈亏 (动态计算)
        position_value: 持仓名义价值 (quantity * entry_price)
        margin_used: 占用保证金 (position_value / leverage)
        open_timestamp: 开仓时间戳
    """
    id: str
    symbol: str
    direction: str                   # "LONG" 或 "SHORT"
    quantity: float                  # 持仓数量（绝对值）
    entry_price: float               # 入场均价
    leverage: float                  # 杠杆倍数
    initial_qty: float = 0.0         # 初始开仓数量（__post_init__ 中保证与 quantity 一致，永不为 None）
    stop_loss_price: Optional[float] = None
    unrealized_pnl: float = 0.0      # 未实现盈亏
    position_value: float = 0.0      # 仓位价值
    margin_used: float = 0.0         # 占用保证金
    open_timestamp: int = 0          # 开仓时间戳

    def __post_init__(self):
        """
        初始化后钩子：自动计算派生字段

        确保 position_value 和 margin_used 在创建时即有正确值。
        【修复 4 - P0-4】initial_qty 必须在构造时与 quantity 一致，不依赖 hasattr 动态检测
        """
        # initial_qty == 0.0 表示未显式传入（dataclass 默认值），此时对齐 quantity
        if self.initial_qty == 0.0:
            self.initial_qty = self.quantity
        if self.position_value == 0.0:
            self.position_value = self.quantity * self.entry_price
        if self.margin_used == 0.0 and self.leverage > 0:
            self.margin_used = self.position_value / self.leverage


@dataclass
class TradeRecord:
    """
    成交记录数据类

    记录每一笔开仓/平仓的成交细节，用于计算统计指标。

    Attributes:
        id: 成交 ID
        position_id: 关联的持仓 ID
        symbol: 交易对
        action: 动作 "OPEN" 或 "CLOSE"
        direction: 方向 "LONG" 或 "SHORT"
        quantity: 成交数量
        price: 成交均价
        order_type: 订单类型 "market" / "limit" / "stop"
        fee: 手续费 (Quote 资产，如 USDT)
        fee_rate: 手续费率 (maker/taker)
        pnl: 实现盈亏 (仅平仓时有值)
        timestamp: 成交时间戳
    """
    id: str
    position_id: str
    symbol: str
    action: str                    # "OPEN" 或 "CLOSE"
    direction: str                 # "LONG" 或 "SHORT"
    quantity: float                # 成交数量（绝对值）
    price: float                   # 成交均价
    order_type: str                # "market" / "limit" / "stop"
    fee: float                     # 手续费（USDT）
    fee_rate: float                # 手续费率
    pnl: float = 0.0               # 实现盈亏
    timestamp: int = 0             # 成交时间戳


@dataclass
class EquitySnapshot:
    """
    权益快照数据类

    每根 K 线结束时的权益状态快照，用于绘制权益曲线和计算 MDD。

    Attributes:
        timestamp: 时间戳
        balance: 账户余额 (已实现盈亏 + 初始资金 - 累计手续费)
        unrealized_pnl: 总未实现盈亏 (所有持仓的浮动盈亏之和)
        total_equity: 总权益 (balance + unrealized_pnl)
        margin_used: 总占用保证金
        free_margin: 可用保证金
    """
    timestamp: int
    balance: float
    unrealized_pnl: float
    total_equity: float
    margin_used: float
    free_margin: float


@dataclass
class BacktestStats:
    """
    回测统计结果数据类

    get_stats() 方法返回的完整统计指标。
    """
    total_return_pct: float = 0.0
    total_pnl: float = 0.0
    total_fees: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0


# ==============================================================================
# BacktestExecutor 主类
# ==============================================================================
class BacktestExecutor:
    """
    回测执行器

    核心功能：
    1. 支持永续合约多/空双向开仓 (open_position)
    2. 支持全仓或部分平仓 (close_position)
    3. 每根 K 线调用 update_equity() 更新浮动盈亏和权益曲线快照
    4. 开仓前校验可用保证金
    5. 区分 Maker/Taker 手续费
    6. 提供完整的统计指标计算 (get_stats)

    使用示例:
        executor = BacktestExecutor(initial_balance=100000, fee_maker=0.00075, fee_taker=0.0008)

        # 开仓
        success = executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            order_type="market",
            timestamp=1700000000000
        )

        # 每根 K 线更新权益
        executor.update_equity(current_prices={"BTCUSDT": 51000}, timestamp=1700000001000)

        # 平仓
        executor.close_position(position_id="pos_1", quantity=0.1, price=51000, ...)

        # 获取统计结果
        stats = executor.get_stats()
    """

    def __init__(
        self,
        initial_balance: float = 100000.0,
        fee_maker: float = 0.00075,   # Maker 费率 (万分之 7.5)
        fee_taker: float = 0.0008,    # Taker 费率 (万分之 8)
        default_leverage: float = 10.0
    ):
        """
        初始化回测执行器

        Args:
            initial_balance: 初始资金 (USDT)
            fee_maker: Maker 手续费率 (默认 0.075%)
            fee_taker: Taker 手续费率 (默认 0.08%)
            default_leverage: 默认杠杆倍数
        """
        # 账户状态
        self.initial_balance = initial_balance
        self.balance = initial_balance          # 当前余额 (已实现 PnL - 累计手续费)
        self.cumulative_fees = 0.0              # 累计手续费
        self.default_leverage = default_leverage

        # 手续费率
        self.fee_maker = fee_maker
        self.fee_taker = fee_taker

        # 持仓管理
        self.positions: Dict[str, Position] = {}    # 活跃持仓 {position_id: Position}
        self._position_counter = 0                   # 持仓 ID 计数器

        # 成交记录
        self.trade_records: List[TradeRecord] = []
        self._trade_counter = 0                      # 成交 ID 计数器

        # 权益曲线 (逐 K 线快照)
        self.equity_curve: List[EquitySnapshot] = []

        # 拒绝日志 (用于调试)
        self.rejection_log: List[Dict] = []

        logger.info(f"BacktestExecutor 初始化：initial_balance={initial_balance}, "
                   f"maker_fee={fee_maker}, taker_fee={fee_taker}, leverage={default_leverage}")

    # ==========================================================================
    # 开仓方法
    # ==========================================================================
    def open_position(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
        leverage: Optional[float] = None,
        order_type: str = "market",
        stop_loss_price: Optional[float] = None,
        timestamp: int = 0
    ) -> bool:
        """
        开仓（多仓或空仓）

        永续合约双向开仓：
        - direction="LONG": 做多
        - direction="SHORT": 做空

        开仓前校验：
        1. 可用保证金 >= 新开仓所需保证金
        2. quantity > 0, price > 0, leverage > 0

        Args:
            symbol: 交易对 (如 "BTCUSDT")
            direction: 方向 "LONG" 或 "SHORT"
            quantity: 开仓数量 (绝对值，始终为正)
            price: 开仓价格
            leverage: 杠杆倍数 (默认使用 default_leverage)
            order_type: 订单类型 "market" / "limit" / "stop"
            stop_loss_price: 止损价格 (可选)
            timestamp: 时间戳 (毫秒)

        Returns:
            bool: 开仓成功返回 True，失败返回 False

        边界条件:
            - quantity <= 0: 返回 False
            - price <= 0: 返回 False
            - leverage <= 0: 返回 False
            - 可用保证金不足：返回 False，记录拒绝原因
        """
        # ========== 参数校验 ==========
        if quantity <= 0:
            self._log_rejection(symbol, "OPEN", "quantity 必须 > 0", timestamp)
            logger.warning(f"[{symbol}] 开仓数量无效：{quantity}")
            return False

        if price <= 0:
            self._log_rejection(symbol, "OPEN", "price 必须 > 0", timestamp)
            logger.warning(f"[{symbol}] 开仓价格无效：{price}")
            return False

        if leverage is None:
            leverage = self.default_leverage

        if leverage <= 0:
            self._log_rejection(symbol, "OPEN", "leverage 必须 > 0", timestamp)
            logger.warning(f"[{symbol}] 杠杆倍数无效：{leverage}")
            return False

        if direction not in ["LONG", "SHORT"]:
            self._log_rejection(symbol, "OPEN", f"无效方向：{direction}", timestamp)
            logger.warning(f"[{symbol}] 持仓方向无效：{direction}")
            return False

        # ========== 计算所需保证金 ==========
        position_value = quantity * price           # 名义价值
        required_margin = position_value / leverage # 所需保证金

        # 计算开仓手续费
        fee_rate = self._get_fee_rate(order_type)
        open_fee = position_value * fee_rate

        # ========== 保证金校验 ==========
        available_margin = self.get_available_margin()

        if available_margin < required_margin:
            self._log_rejection(
                symbol, "OPEN",
                f"可用保证金不足：需要 {required_margin:.4f}, 可用 {available_margin:.4f}",
                timestamp
            )
            logger.warning(f"[{symbol}] 保证金不足：需要 {required_margin:.2f}, 可用 {available_margin:.2f}")
            return False

        # ========== 检查是否已有同向持仓（加仓逻辑） ==========
        existing_position = self._get_position_by_symbol(symbol)

        if existing_position and existing_position.direction == direction:
            # 同向加仓：更新平均成本
            return self._add_to_position(
                existing_position,
                quantity, price, leverage,
                order_type, open_fee, timestamp
            )

        # ========== 创建新持仓 ==========
        self._position_counter += 1
        position_id = f"pos_{self._position_counter}"

        position = Position(
            id=position_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            entry_price=price,
            leverage=leverage,
            initial_qty=quantity,       # 【关键】在初始化时赋值 initial_qty
            stop_loss_price=stop_loss_price,
            position_value=position_value,
            margin_used=required_margin,
            open_timestamp=timestamp
        )

        # ========== 扣除手续费 ==========
        self.balance -= open_fee
        self.cumulative_fees += open_fee

        # ========== 记录成交 ==========
        self._trade_counter += 1
        trade = TradeRecord(
            id=f"trade_{self._trade_counter}",
            position_id=position_id,
            symbol=symbol,
            action="OPEN",
            direction=direction,
            quantity=quantity,
            price=price,
            order_type=order_type,
            fee=open_fee,
            fee_rate=fee_rate,
            pnl=0.0,
            timestamp=timestamp
        )
        self.trade_records.append(trade)

        # ========== 添加到持仓字典 ==========
        self.positions[position_id] = position

        logger.info(f"[{symbol}] 开仓：{direction} {quantity} @ {price}, 杠杆={leverage}, 手续费={open_fee:.4f}")
        return True

    def _add_to_position(
        self,
        position: Position,
        add_qty: float,
        add_price: float,
        leverage: float,
        order_type: str,
        open_fee: float,
        timestamp: int
    ) -> bool:
        """
        加仓逻辑（同向增加持仓）

        更新平均开仓价格，不创建新持仓 ID。

        Args:
            position: 现有持仓
            add_qty: 加仓数量
            add_price: 加仓价格
            leverage: 杠杆倍数
            order_type: 订单类型
            open_fee: 手续费
            timestamp: 时间戳

        Returns:
            bool: 成功返回 True
        """
        # 计算新的平均成本
        old_value = position.quantity * position.entry_price
        new_value = add_qty * add_price
        total_qty = position.quantity + add_qty

        if total_qty > 0:
            position.entry_price = (old_value + new_value) / total_qty
        else:
            position.entry_price = add_price

        # 更新持仓数量和派生字段
        position.quantity = total_qty
        position.position_value = position.quantity * position.entry_price
        position.margin_used = position.position_value / leverage
        position.leverage = leverage

        # 扣除手续费
        self.balance -= open_fee
        self.cumulative_fees += open_fee

        # 记录成交
        self._trade_counter += 1
        trade = TradeRecord(
            id=f"trade_{self._trade_counter}",
            position_id=position.id,
            symbol=position.symbol,
            action="OPEN",
            direction=position.direction,
            quantity=add_qty,
            price=add_price,
            order_type=order_type,
            fee=open_fee,
            fee_rate=self._get_fee_rate(order_type),
            pnl=0.0,
            timestamp=timestamp
        )
        self.trade_records.append(trade)

        logger.info(f"[{position.symbol}] 加仓：{add_qty} @ {add_price}, 新均价={position.entry_price:.4f}")
        return True

    # ==========================================================================
    # 平仓方法
    # ==========================================================================
    def close_position(
        self,
        position_id: str,
        price: float,
        quantity: Optional[float] = None,
        order_type: str = "market",
        timestamp: int = 0
    ) -> bool:
        """
        平仓（全仓或部分平仓）

        支持部分平仓：
        - quantity=None 或 quantity=持仓数量：全仓平仓
        - quantity<持仓数量：部分平仓，剩余持仓继续持有

        平仓盈亏计算：
        - 多仓：pnl = (close_price - entry_price) * quantity
        - 空仓：pnl = (entry_price - close_price) * quantity

        Args:
            position_id: 持仓 ID
            price: 平仓价格
            quantity: 平仓数量 (None=全仓，默认全仓)
            order_type: 订单类型 "market" / "limit" / "stop"
            timestamp: 时间戳

        Returns:
            bool: 平仓成功返回 True，失败返回 False

        边界条件:
            - position_id 不存在：返回 False
            - price <= 0: 返回 False
            - quantity <= 0: 返回 False
            - quantity > 持仓数量：返回 False
        """
        # ========== 检查持仓是否存在 ==========
        if position_id not in self.positions:
            self._log_rejection(position_id, "CLOSE", "持仓 ID 不存在", timestamp)
            logger.warning(f"持仓 ID 不存在：{position_id}")
            return False

        position = self.positions[position_id]

        # ========== 参数校验 ==========
        if price <= 0:
            self._log_rejection(position_id, "CLOSE", "price 必须 > 0", timestamp)
            logger.warning(f"[{position.symbol}] 平仓价格无效：{price}")
            return False

        # 确定平仓数量
        close_qty = quantity if quantity is not None else position.quantity

        if close_qty <= 0:
            self._log_rejection(position_id, "CLOSE", "quantity 必须 > 0", timestamp)
            logger.warning(f"[{position.symbol}] 平仓数量无效：{close_qty}")
            return False

        if close_qty > position.quantity:
            self._log_rejection(
                position_id, "CLOSE",
                f"平仓数量 {close_qty} 超过持仓数量 {position.quantity}",
                timestamp
            )
            logger.warning(f"[{position.symbol}] 平仓数量超过持仓：{close_qty} > {position.quantity}")
            return False

        # ========== 计算平仓盈亏 ==========
        if position.direction == "LONG":
            # 多仓盈亏 = (平仓价 - 开仓价) * 数量
            realized_pnl = (price - position.entry_price) * close_qty
        else:
            # 空仓盈亏 = (开仓价 - 平仓价) * 数量
            realized_pnl = (position.entry_price - price) * close_qty

        # ========== 计算平仓手续费 ==========
        close_position_value = close_qty * price
        fee_rate = self._get_fee_rate(order_type)
        close_fee = close_position_value * fee_rate

        # ========== 更新余额（实现盈亏 - 手续费） ==========
        self.balance += realized_pnl
        self.balance -= close_fee
        self.cumulative_fees += close_fee

        # ========== 记录成交 ==========
        self._trade_counter += 1
        trade = TradeRecord(
            id=f"trade_{self._trade_counter}",
            position_id=position_id,
            symbol=position.symbol,
            action="CLOSE",
            direction=position.direction,
            quantity=close_qty,
            price=price,
            order_type=order_type,
            fee=close_fee,
            fee_rate=fee_rate,
            pnl=realized_pnl,
            timestamp=timestamp
        )
        self.trade_records.append(trade)

        # ========== 更新或移除持仓 ==========
        if close_qty >= position.quantity:
            # 全仓平仓：移除持仓
            logger.info(f"[{position.symbol}] 全仓平仓：{position.direction} {close_qty} @ {price}, "
                       f"实现盈亏={realized_pnl:.4f}, 手续费={close_fee:.4f}")
            del self.positions[position_id]
        else:
            # 部分平仓：更新持仓
            remaining_qty = position.quantity - close_qty

            # 按比例减少保证金和仓位价值
            ratio = remaining_qty / position.quantity
            position.quantity = remaining_qty
            position.position_value *= ratio
            position.margin_used *= ratio

            logger.info(f"[{position.symbol}] 部分平仓：{close_qty}/{position.quantity + close_qty} "
                       f"@ {price}, 剩余={remaining_qty}, 实现盈亏={realized_pnl:.4f}")

        return True

    # ==========================================================================
    # 权益更新方法
    # ==========================================================================
    def update_equity(self, current_prices: Dict[str, float], timestamp: int):
        """
        更新权益曲线快照（每根 K 线调用）

        根据当前市场价格更新所有持仓的未实现盈亏，并记录权益快照。
        快照用于：
        1. 绘制权益曲线
        2. 计算最大回撤 (MDD)
        3. 计算夏普比率

        Args:
            current_prices: 当前价格字典 {symbol: price}
            timestamp: 时间戳

        边界条件:
            - 没有持仓时：只记录余额快照，unrealized_pnl=0
            - 某个 symbol 没有价格：该持仓 unrealized_pnl 保持上一快照值
        """
        # ========== 计算总未实现盈亏 ==========
        total_unrealized_pnl = 0.0
        total_margin_used = 0.0

        for position in self.positions.values():
            if position.symbol not in current_prices:
                # 没有当前价格，保持之前的 unrealized_pnl
                total_unrealized_pnl += position.unrealized_pnl
                total_margin_used += position.margin_used
                continue

            current_price = current_prices[position.symbol]

            # 更新持仓的未实现盈亏
            if position.direction == "LONG":
                # 多仓：(当前价 - 开仓价) * 数量
                position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
            else:
                # 空仓：(开仓价 - 当前价) * 数量
                position.unrealized_pnl = (position.entry_price - current_price) * position.quantity

            total_unrealized_pnl += position.unrealized_pnl
            total_margin_used += position.margin_used

        # ========== 计算总权益 ==========
        # 总权益 = 余额 + 未实现盈亏
        total_equity = self.balance + total_unrealized_pnl

        # 可用保证金 = 余额 - 占用保证金
        free_margin = self.balance - total_margin_used

        # ========== 记录快照 ==========
        snapshot = EquitySnapshot(
            timestamp=timestamp,
            balance=self.balance,
            unrealized_pnl=total_unrealized_pnl,
            total_equity=total_equity,
            margin_used=total_margin_used,
            free_margin=free_margin
        )
        self.equity_curve.append(snapshot)

    # ==========================================================================
    # 止损检查方法
    # ==========================================================================
    def check_stop_loss(self, prices: Dict[str, float], timestamp: int) -> List[str]:
        """
        检查止损

        遍历所有持仓，检查是否触及止损价格，自动平仓。

        Args:
            prices: 当前价格快照 {symbol: price}
            timestamp: 时间戳

        Returns:
            List[str]: 被止损平仓的 symbol 列表
        """
        closed_symbols = []

        for position in list(self.positions.values()):
            if position.stop_loss_price is None:
                continue

            current_price = prices.get(position.symbol)
            if current_price is None:
                continue

            # 检查是否触及止损
            should_close = False
            if position.direction == "LONG" and current_price <= position.stop_loss_price:
                should_close = True
            elif position.direction == "SHORT" and current_price >= position.stop_loss_price:
                should_close = True

            if should_close:
                logger.info(f"[{position.symbol}] 触及止损价 {position.stop_loss_price:.4f}, "
                           f"当前价 {current_price:.4f}")
                if self.close_position(position.id, current_price, timestamp=timestamp):
                    closed_symbols.append(position.symbol)

        return closed_symbols

    # ==========================================================================
    # 统计指标计算方法
    # ==========================================================================
    def get_stats(self) -> Dict[str, Any]:
        """
        获取回测统计指标

        返回字典包含：
        - total_return_pct: 总收益率 (%)
        - total_pnl: 总盈亏 (Quote 资产)
        - total_fees: 累计手续费
        - max_drawdown_pct: 最大回撤 (%)
        - sharpe_ratio: 夏普比率 (年化)
        - win_rate: 胜率 (%)
        - profit_factor: 盈亏比
        - total_trades: 总交易次数
        - win_count: 盈利次数
        - loss_count: 亏损次数

        Returns:
            Dict: 统计指标字典

        计算说明:
            - max_drawdown_pct: 从 equity_curve 逐点遍历，维护历史峰值
            - sharpe_ratio: 先将 equity_curve 聚合为日收益率，再 ×√252 / 样本标准差
        """
        stats = {}

        # ========== 基础指标 ==========
        stats['total_fees'] = self.cumulative_fees

        # 总盈亏 = 最终余额 - 初始余额
        total_pnl = self.balance - self.initial_balance
        stats['total_pnl'] = total_pnl

        # 总收益率
        if self.initial_balance > 0:
            stats['total_return_pct'] = (total_pnl / self.initial_balance) * 100
        else:
            stats['total_return_pct'] = 0.0

        # ========== 交易统计 ==========
        # 只统计 CLOSE 记录
        close_trades = [t for t in self.trade_records if t.action == "CLOSE"]
        stats['total_trades'] = len(close_trades)

        # 盈亏统计
        profits = [t.pnl for t in close_trades if t.pnl > 0]
        losses = [t.pnl for t in close_trades if t.pnl < 0]

        stats['win_count'] = len(profits)
        stats['loss_count'] = len(losses)

        # 胜率
        total_closed = stats['win_count'] + stats['loss_count']
        if total_closed > 0:
            stats['win_rate'] = (stats['win_count'] / total_closed) * 100
        else:
            stats['win_rate'] = 0.0

        # 盈亏比
        gross_profit = sum(profits)
        gross_loss = abs(sum(losses))
        if gross_loss > 0:
            stats['profit_factor'] = gross_profit / gross_loss
        else:
            stats['profit_factor'] = float('inf') if gross_profit > 0 else 0.0

        # ========== 最大回撤 (从权益曲线逐点计算) ==========
        stats['max_drawdown_pct'] = self._calculate_max_drawdown()

        # ========== 夏普比率 ==========
        stats['sharpe_ratio'] = self._calculate_sharpe_ratio()

        return stats

    def _calculate_max_drawdown(self) -> float:
        """
        计算最大回撤 (Maximum Drawdown)

        从 equity_curve 逐点遍历，维护历史峰值，计算最大回撤百分比。

        MDD = max((peak - trough) / peak) for all points

        Returns:
            float: 最大回撤百分比 (如 0.15 表示 15% 回撤)

        边界条件:
            - equity_curve 为空：返回 0.0
            - equity_curve 只有一个点：返回 0.0
        """
        if len(self.equity_curve) < 2:
            return 0.0

        max_drawdown = 0.0
        peak = self.equity_curve[0].total_equity

        for snapshot in self.equity_curve:
            equity = snapshot.total_equity

            # 更新峰值
            if equity > peak:
                peak = equity

            # 计算当前回撤
            if peak > 0:
                drawdown = (peak - equity) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        return max_drawdown

    def _calculate_sharpe_ratio(self) -> float:
        """
        计算夏普比率 (Sharpe Ratio)

        计算步骤：
        1. 将 equity_curve 按日期聚合，取每日最后一个点的 total_equity
        2. 计算日收益率序列：daily_return[i] = (equity[i] - equity[i-1]) / equity[i-1]
        3. 计算年化：sharpe = mean(daily_returns) * √252 / std(daily_returns)

        Returns:
            float: 年化夏普比率

        边界条件:
            - equity_curve 为空或只有一个点：返回 0.0
            - 日收益率标准差为 0：返回 0.0
            - 不足 2 个交易日：返回 0.0
        """
        if len(self.equity_curve) < 2:
            return 0.0

        # ========== 步骤 1: 按日期聚合权益 ==========
        # 将时间戳转换为日期，取每日最后一个权益值
        daily_equity: Dict[str, float] = {}

        for snapshot in self.equity_curve:
            # 毫秒时间戳转日期字符串 (YYYY-MM-DD)
            dt = datetime.fromtimestamp(snapshot.timestamp / 1000)
            date_str = dt.strftime("%Y-%m-%d")
            # 覆盖写入，保证是当日最后一个点
            daily_equity[date_str] = snapshot.total_equity

        # 转换为有序列表
        equity_values = list(daily_equity.values())

        if len(equity_values) < 2:
            return 0.0

        # ========== 步骤 2: 计算日收益率 ==========
        daily_returns = []
        for i in range(1, len(equity_values)):
            prev_equity = equity_values[i - 1]
            curr_equity = equity_values[i]

            if prev_equity > 0:
                daily_return = (curr_equity - prev_equity) / prev_equity
                daily_returns.append(daily_return)

        if len(daily_returns) < 2:
            return 0.0

        # ========== 步骤 3: 计算均值和标准差 ==========
        n = len(daily_returns)
        mean_return = sum(daily_returns) / n

        # 样本标准差 (N-1)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / (n - 1)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return 0.0

        # ========== 步骤 4: 年化夏普比率 ==========
        # Sharpe = (mean_daily_return * √252) / (std_dev * √252) = mean / std * √252
        sharpe = (mean_return / std_dev) * math.sqrt(252)

        return sharpe

    # ==========================================================================
    # 辅助方法
    # ==========================================================================
    def get_available_margin(self) -> float:
        """
        计算可用保证金（公开方法，Worker 层直接调用）

        available_margin = balance - sum(margin_used)

        Returns:
            float: 可用保证金（可能为负数，表示爆仓风险）
        """
        total_margin_used = sum(p.margin_used for p in self.positions.values())
        return self.balance - total_margin_used

    # 内部别名，保持向下兼容
    _get_available_margin = get_available_margin

    def _get_fee_rate(self, order_type: str) -> float:
        """
        根据订单类型获取手续费率

        - order_type='limit': maker 费率
        - order_type='market'/'stop': taker 费率

        Args:
            order_type: 订单类型

        Returns:
            float: 手续费率
        """
        if order_type == "limit":
            return self.fee_maker
        else:
            # 'market', 'stop', 或其他类型都用 taker 费率
            return self.fee_taker

    def _get_position_by_symbol(self, symbol: str) -> Optional[Position]:
        """
        根据 symbol 获取持仓（返回第一个匹配的持仓）

        Args:
            symbol: 交易对

        Returns:
            Optional[Position]: 持仓对象，不存在返回 None
        """
        for position in self.positions.values():
            if position.symbol == symbol:
                return position
        return None

    def _log_rejection(self, target_id: str, action: str, reason: str, timestamp: int):
        """
        记录拒绝原因

        Args:
            target_id: 目标 ID (持仓 ID 或 symbol)
            action: 动作 "OPEN" 或 "CLOSE"
            reason: 拒绝原因
            timestamp: 时间戳
        """
        self.rejection_log.append({
            "timestamp": timestamp,
            "target_id": target_id,
            "action": action,
            "reason": reason
        })

    def get_position(self, position_id: str) -> Optional[Position]:
        """
        获取指定持仓

        Args:
            position_id: 持仓 ID

        Returns:
            Optional[Position]: 持仓对象，不存在返回 None
        """
        return self.positions.get(position_id)

    def get_all_positions(self) -> List[Position]:
        """
        获取所有活跃持仓

        Returns:
            List[Position]: 持仓列表
        """
        return list(self.positions.values())

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """
        获取权益曲线（序列化为字典列表，可直接 JSON 化）

        【关键】Worker 将此结果直接注入到 CustomMetrics 中，Parser 层用 .get() 读取，
        必须返回 dict 而非 dataclass 对象，否则 Parser 中的 point.get("total_equity") 会报 AttributeError。

        Returns:
            List[Dict]: 权益快照字典列表，每条包含：
                timestamp, balance, unrealized_pnl, total_equity, margin_used, free_margin
        """
        from dataclasses import asdict
        return [asdict(snap) for snap in self.equity_curve]

    def get_trade_records(self) -> List[TradeRecord]:
        """
        获取所有成交记录（返回 dataclass 对象，调用方自行 asdict）

        Returns:
            List[TradeRecord]: 成交记录列表
        """
        return self.trade_records

    def get_rejection_log(self) -> List[Dict]:
        """
        获取拒绝日志

        Returns:
            List[Dict]: 拒绝原因列表
        """
        return self.rejection_log
