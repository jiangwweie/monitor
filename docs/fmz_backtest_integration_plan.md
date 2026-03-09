# FMZ 回测框架集成方案

## 文档信息

- **版本**: v1.0
- **创建日期**: 2026-03-09
- **作者**: System Architect
- **状态**: 草案

---

## 1. 执行摘要

### 1.1 项目背景

本项目旨在将现有的加密货币信号监测系统（monitor）与 FMZ 回测框架进行深度集成，使系统具备：
1. **历史策略回测**能力 - 验证 Pinbar 策略在不同市场阶段的表现
2. **参数优化**能力 - 自动寻找最优策略参数组合
3. **模拟交易**能力 - 在实盘前进行纸面推演

### 1.2 核心价值

| 当前能力 | 集成后新增能力 |
|---------|---------------|
| 实时信号监测 | 历史策略回测 |
| 信号入库记录 | 绩效统计分析 |
| 手动参数调整 | 自动化参数优化 |
| 只读信号推送 | 模拟交易验证 |

### 1.3 集成策略

采用**适配器模式** + **策略抽象层**的双层隔离设计：
- **不修改**现有实时监控引擎的核心逻辑
- **复用**现有的 PinbarStrategy 领域代码
- **新增**回测引擎适配层和 FMZ 执行引擎

---

## 2. 架构对比分析

### 2.1 现有系统架构 (monitor)

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Web Server                      │
├─────────────────────────────────────────────────────────────┤
│                     Application Layer                        │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ MonitorEngine    │  │ HistoryScanner  │  │ChartService │ │
│  └──────────────────┘  └─────────────────┘  └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                      Domain Layer                            │
│  ┌──────────────────┐  ┌─────────────────┐                  │
│  │ PinbarStrategy   │  │ PositionSizer   │                  │
│  │ (评分 + 形态识别)  │  │ (风控算仓)       │                  │
│  └──────────────────┘  └─────────────────┘                  │
├─────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                       │
│  ┌────────────┐  ┌────────────┐  ┌────────┐  ┌───────────┐ │
│  │BinanceWS   │  │BinanceAPI  │  │SQLite  │  │Feishu/Wecom│ │
│  └────────────┘  └────────────┘  └────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 FMZ 回测框架架构

```
┌─────────────────────────────────────────────────────────────┐
│                    FMZ Backtest Engine                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   VCtx (虚拟上下文)                     │ │
│  │  - 加载.so 动态库                                        │ │
│  │  - 注册全局变量 (exchanges, TA, Log)                    │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Exchange 模拟类                       │ │
│  │  - GetRecords()  - 获取 K 线                             │ │
│  │  - Buy()/Sell()  - 模拟下单                             │ │
│  │  - GetAccount()  - 模拟账户                             │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   绩效统计引擎                          │ │
│  │  - 权益曲线计算                                         │ │
│  │  - 胜率/盈亏比统计                                      │ │
│  │  - 交易明细导出                                         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 架构差异对比

| 维度 | monitor 系统 | FMZ 回测框架 |
|------|-------------|-------------|
| **数据源** | Binance WebSocket 实时流 | 历史 K 线数据 |
| **执行模式** | 事件驱动异步循环 | 同步回测引擎 |
| **订单处理** | 只读 (Zero Execution) | 模拟下单 + 成交撮合 |
| **账户状态** | 真实 API 读取 | 模拟账户 |
| **时间处理** | 实时时间流 | 虚拟时间轴 |
| **策略接口** | `evaluate()` 返回 Signal | `main()` 函数内交易逻辑 |

---

## 3. 集成方案设计

### 3.1 总体集成架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                         Web UI / API                             │
│         Dashboard | SignalRadar | BacktestLab | OptimizeLab      │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                      FastAPI Routes (/api/*)                     │
│  /api/backtest/run    /api/backtest/optimize   /api/strategy/*   │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Application Layer (新增)                       │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐   │
│  │   BacktestService   │  │  ParameterOptimizer (可选)      │   │
│  │  - 运行回测任务       │  │  - 网格搜索                     │   │
│  │  - 管理回测历史      │  │  - 遗传算法                     │   │
│  └─────────────────────┘  └─────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Adapter Layer (新增核心层)                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              FMZAdapter / MonitorAdapter                    │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐ │ │
│  │  │ ExchangeProxy │  │ DataFeedProxy │  │ AccountSimulator│ │ │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Domain Layer (复用现有)                        │
│  ┌─────────────────────┐  ┌─────────────────┐                   │
│  │  PinbarStrategy     │  │  PositionSizer  │                   │
│  │  (完全复用)          │  │  (完全复用)      │                   │
│  └─────────────────────┘  └─────────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer (扩展)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ FMZ Backtest │  │ BinanceKline │  │ BacktestResultRepo     │ │
│  │ Engine (.so) │  │ Fetcher(复用) │  │ (SQLite 扩展表)        │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

### 3.2 核心适配器设计

#### 3.2.1 ExchangeProxy - 交易所代理

```python
"""
FMZ Exchange 接口代理
将 FMZ 的 exchange.GetRecords()/Buy()/Sell() 调用
适配到 monitor 系统的 PinbarStrategy 和 AccountSimulator
"""

class ExchangeProxy:
    """
    模拟 FMZ Exchange 类的接口
    在回测模式下，所有数据来自历史 K 线，所有订单进入模拟撮合
    """

    def __init__(
        self,
        kline_fetcher: BinanceKlineFetcher,
        account_sim: AccountSimulator,
        symbol: str,
        interval: str
    ):
        self.kline_fetcher = kline_fetcher
        self.account_sim = account_sim
        self.symbol = symbol
        self.interval = interval
        self._current_bar_index = 0
        self._records_cache: List[Bar] = []

    def GetRecords(self, period: str = None, limit: int = 100) -> List[dict]:
        """
        获取 K 线数据（FMZ 风格）
        返回格式兼容 FMZ: [{'Time':..., 'Open':..., 'High':..., 'Low':..., 'Close':..., 'Volume':...}]
        """
        # 从缓存中返回当前时间点之前的 K 线
        # 在回测中，不能"看到未来"的数据
        current_time = self._records_cache[self._current_bar_index].timestamp
        visible_bars = [b for b in self._records_cache if b.timestamp <= current_time]
        return self._to_fmz_format(visible_bars[-limit:])

    def GetAccount(self) -> dict:
        """获取模拟账户状态"""
        return self.account_sim.get_account_state()

    def GetPositions(self) -> List[dict]:
        """获取当前持仓"""
        return self.account_sim.get_positions()

    def Buy(self, price: float, amount: float) -> int:
        """
        模拟买入（开多）
        返回订单 ID，订单进入模拟撮合引擎
        """
        return self.account_sim.place_order(
            symbol=self.symbol,
            side="BUY",
            price=price,
            amount=amount,
            offset="OPEN"
        )

    def Sell(self, price: float, amount: float) -> int:
        """
        模拟卖出（平多/开空）
        """
        return self.account_sim.place_order(
            symbol=self.symbol,
            side="SELL",
            price=price,
            amount=amount,
            offset="CLOSE" if self.account_sim.has_long_position() else "OPEN"
        )

    def _to_fmz_format(self, bars: List[Bar]) -> List[dict]:
        """转换 Bar 为 FMZ 格式"""
        return [{
            'Time': bar.timestamp,
            'Open': bar.open,
            'High': bar.high,
            'Low': bar.low,
            'Close': bar.close,
            'Volume': bar.volume
        } for bar in bars]
```

#### 3.2.2 AccountSimulator - 账户模拟器

```python
"""
模拟账户引擎
负责订单撮合、持仓管理、盈亏计算
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

class OrderStatus(Enum):
    PENDING = "PENDING"      # 挂单等待
    FILLED = "FILLED"        # 已成交
    CANCELLED = "CANCELLED"  # 已撤销
    REJECTED = "REJECTED"    # 已拒绝

@dataclass
class Order:
    order_id: int
    symbol: str
    side: str          # "BUY" / "SELL"
    offset: str        # "OPEN" / "CLOSE"
    price: float
    amount: float
    status: OrderStatus
    timestamp: int
    filled_price: Optional[float] = None
    filled_amount: Optional[float] = None

@dataclass
class Position:
    symbol: str
    direction: str     # "LONG" / "SHORT"
    amount: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: float = 1.0

class AccountSimulator:
    """
    模拟账户撮合引擎

    核心功能：
    1. 订单撮合 - 在回测时间轴上，当 K 线到达时撮合挂单
    2. 持仓管理 - 跟踪多空持仓
    3. 盈亏计算 - 实时计算浮动盈亏
    4. 手续费计算 - 按交易所费率计算交易成本
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        fee_rate: float = 0.0005,  # 默认万分之五
        leverage: int = 1
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.fee_rate = fee_rate
        self.leverage = leverage

        self._orders: Dict[int, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._trades: List[dict] = []
        self._order_counter = 0
        self._current_bar: Optional[Bar] = None

    def set_current_bar(self, bar: Bar):
        """设置当前 K 线（用于模拟时间推进）"""
        self._current_bar = bar
        self._update_positions(bar)

    def place_order(
        self,
        symbol: str,
        side: str,
        price: float,
        amount: float,
        offset: str = "OPEN"
    ) -> int:
        """
        下达订单

        回测模式假设：
        - 所有市价单立即以当前 K 线收盘价成交
        - 不考虑滑点（可选扩展）
        """
        self._order_counter += 1
        order_id = self._order_counter

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            offset=offset,
            price=price,
            amount=amount,
            status=OrderStatus.PENDING,
            timestamp=self._current_bar.timestamp if self._current_bar else 0
        )

        # 回测简化：假设立即成交
        self._fill_order(order)
        self._orders[order_id] = order
        return order_id

    def _fill_order(self, order: Order):
        """
        撮合订单

        简化逻辑：
        - 以订单价格成交
        - 扣除手续费
        - 更新持仓
        """
        if self._current_bar is None:
            order.status = OrderStatus.REJECTED
            return

        # 使用当前 K 线收盘价作为成交价
        fill_price = self._current_bar.close
        fill_amount = order.amount
        fee = fill_price * fill_amount * self.fee_rate

        # 处理持仓逻辑
        if order.offset == "OPEN":
            self._open_position(order, fill_price, fill_amount, fee)
        else:
            self._close_position(order, fill_price, fill_amount, fee)

        order.status = OrderStatus.FILLED
        order.filled_price = fill_price
        order.filled_amount = fill_amount

        # 记录成交
        self._trades.append({
            'time': self._current_bar.timestamp,
            'symbol': order.symbol,
            'side': order.side,
            'price': fill_price,
            'amount': fill_amount,
            'fee': fee
        })

    def _open_position(
        self,
        order: Order,
        fill_price: float,
        amount: float,
        fee: float
    ):
        """开仓逻辑"""
        symbol = order.symbol

        if symbol not in self._positions:
            # 新建仓位
            self._positions[symbol] = Position(
                symbol=symbol,
                direction="LONG" if order.side == "BUY" else "SHORT",
                amount=amount,
                entry_price=fill_price,
                current_price=fill_price,
                unrealized_pnl=0.0,
                leverage=self.leverage
            )
        else:
            # 加仓逻辑（简化：同方向才允许）
            pos = self._positions[symbol]
            if (order.side == "BUY" and pos.direction == "LONG") or \
               (order.side == "SELL" and pos.direction == "SHORT"):
                # 平均成本法加仓
                total_value = pos.entry_price * pos.amount + fill_price * amount
                pos.amount += amount
                pos.entry_price = total_value / pos.amount

        # 扣除手续费
        self.balance -= fee

    def _close_position(
        self,
        order: Order,
        fill_price: float,
        amount: float,
        fee: float
    ):
        """平仓逻辑"""
        symbol = order.symbol
        if symbol not in self._positions:
            order.status = OrderStatus.REJECTED
            return

        pos = self._positions[symbol]

        # 计算盈亏
        if pos.direction == "LONG":
            pnl = (fill_price - pos.entry_price) * amount
        else:
            pnl = (pos.entry_price - fill_price) * amount

        # 更新余额
        self.balance += pnl - fee

        # 减少或清除持仓
        pos.amount -= amount
        if pos.amount <= 0:
            del self._positions[symbol]

    def _update_positions(self, current_bar: Bar):
        """更新持仓的未实现盈亏"""
        for pos in self._positions.values():
            if pos.symbol == current_bar.symbol:
                pos.current_price = current_bar.close
                if pos.direction == "LONG":
                    pos.unrealized_pnl = (
                        (current_bar.close - pos.entry_price) * pos.amount
                    )
                else:
                    pos.unrealized_pnl = (
                        (pos.entry_price - current_bar.close) * pos.amount
                    )

    def get_account_state(self) -> dict:
        """获取账户状态（FMZ 风格）"""
        total_unrealized_pnl = sum(
            p.unrealized_pnl for p in self._positions.values()
        )
        return {
            'Balance': self.balance,
            'Frozen': 0.0,  # 简化：不考虑冻结资金
            'Profit': total_unrealized_pnl,
            'Info': {
                'positions_count': len(self._positions),
                'total_trades': len(self._trades)
            }
        }

    def get_positions(self) -> List[dict]:
        """获取持仓列表"""
        return [
            {
                'Symbol': pos.symbol,
                'Type': 0 if pos.direction == "LONG" else 1,
                'Amount': pos.amount,
                'Price': pos.entry_price,
                'Profit': pos.unrealized_pnl,
                'Margin': pos.entry_price * pos.amount / pos.leverage
            }
            for pos in self._positions.values()
        ]

    def get_equity_curve(self) -> List[dict]:
        """
        获取权益曲线数据
        用于回测结果可视化
        """
        return [
            {
                'time': trade['time'],
                'balance': self.balance,
                'profit': trade.get('pnl', 0)
            }
            for trade in self._trades
        ]
```

---

### 3.3 回测服务层设计

```python
"""
Application 层：回测服务
负责管理回测任务的生命周期
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import uuid

from domain.strategy.pinbar import PinbarStrategy
from domain.strategy.scoring_config import ScoringConfig
from infrastructure.feed.binance_kline_fetcher import BinanceKlineFetcher

logger = logging.getLogger(__name__)

@dataclass
class BacktestTask:
    """回测任务状态容器"""
    task_id: str
    status: str = "pending"  # pending | running | completed | failed
    progress: int = 0        # 0-100
    config: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error_message: str = ""
    created_at: float = field(default_factory=datetime.now().timestamp)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

class BacktestService:
    """
    回测服务

    核心职责：
    1. 接收回测配置参数
    2. 异步执行回测任务
    3. 管理任务队列和状态
    4. 持久化回测结果
    """

    def __init__(
        self,
        kline_fetcher: BinanceKlineFetcher,
        strategy: PinbarStrategy,
        db_path: str
    ):
        self.kline_fetcher = kline_fetcher
        self.strategy = strategy
        self.db_path = db_path

        # 内存任务注册表（后续可扩展为 Redis/SQLite 持久化）
        self._tasks: Dict[str, BacktestTask] = {}
        self._async_tasks: Dict[str, asyncio.Task] = {}

    def create_backtest_task(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        initial_balance: float = 10000.0,
        leverage: int = 1,
        fee_rate: float = 0.0005,
        risk_pct: float = 0.02,
        max_sl_dist: float = 0.035,
        pinbar_config: dict = None,
        scoring_weights: dict = None
    ) -> str:
        """
        创建回测任务

        :return: task_id
        """
        task_id = f"backtest-{uuid.uuid4().hex[:12]}"

        task = BacktestTask(
            task_id=task_id,
            status="pending",
            config={
                "symbol": symbol,
                "interval": interval,
                "start_date": start_date,
                "end_date": end_date,
                "initial_balance": initial_balance,
                "leverage": leverage,
                "fee_rate": fee_rate,
                "risk_pct": risk_pct,
                "max_sl_dist": max_sl_dist,
                "pinbar_config": pinbar_config or {},
                "scoring_weights": scoring_weights or {}
            }
        )

        self._tasks[task_id] = task

        # 启动异步回测
        async_task = asyncio.create_task(
            self._run_backtest(task_id)
        )
        self._async_tasks[task_id] = async_task

        logger.info(f"[BacktestService] 任务已创建：{task_id} | {symbol} {interval}")
        return task_id

    async def _run_backtest(self, task_id: str):
        """执行回测任务"""
        task = self._tasks[task_id]

        try:
            task.status = "running"
            task.started_at = datetime.now().timestamp()

            config = task.config

            # ============================
            # 1. 获取历史 K 线数据
            # ============================
            task.progress = 10
            task.message = "正在获取历史 K 线数据..."

            bars = await self.kline_fetcher.fetch_history_klines(
                symbol=config['symbol'],
                interval=config['interval'],
                start_date=config['start_date'],
                end_date=config['end_date']
            )

            if not bars:
                raise ValueError("未获取到任何 K 线数据")

            task.progress = 30
            task.message = f"已获取 {len(bars)} 根 K 线"

            # ============================
            # 2. 初始化回测环境
            # ============================
            from .backtest_adapter import FMZAdapter

            adapter = FMZAdapter(
                bars=bars,
                strategy=self.strategy,
                initial_balance=config['initial_balance'],
                leverage=config['leverage'],
                fee_rate=config['fee_rate'],
                risk_pct=config['risk_pct'],
                max_sl_dist=config['max_sl_dist'],
                pinbar_config=config.get('pinbar_config'),
                scoring_weights=config.get('scoring_weights')
            )

            task.progress = 40
            task.message = "正在执行策略回测..."

            # ============================
            # 3. 运行回测引擎
            # ============================
            result = await adapter.run(
                on_progress=lambda current, total: self._update_progress(
                    task, current, total
                )
            )

            # ============================
            # 4. 保存回测结果
            # ============================
            task.progress = 90
            task.message = "正在保存回测结果..."

            await self._save_backtest_result(task_id, result)

            # ============================
            # 5. 标记完成
            # ============================
            task.status = "completed"
            task.progress = 100
            task.completed_at = datetime.now().timestamp()
            task.result = result

            logger.info(
                f"[BacktestService] 回测完成：{task_id} | "
                f"总收益：result.get('total_return', 0):.2f}% | "
                f"胜率：result.get('win_rate', 0):.2f}%"
            )

        except Exception as e:
            import traceback
            task.status = "failed"
            task.progress = 100
            task.error_message = str(e)
            task.completed_at = datetime.now().timestamp()
            logger.error(
                f"[BacktestService] 回测失败：{task_id} | {e}\n"
                f"{traceback.format_exc()}"
            )

    def _update_progress(self, task: BacktestTask, current: int, total: int):
        """更新回测进度"""
        if total > 0:
            # 回测阶段占 40%-90%
            task.progress = 40 + int(current / total * 50)
            task.message = f"回测中：{current}/{total} 根 K 线"

    def get_task_status(self, task_id: str) -> Optional[BacktestTask]:
        """查询任务状态"""
        return self._tasks.get(task_id)

    async def _save_backtest_result(self, task_id: str, result: dict):
        """保存回测结果到数据库"""
        # TODO: 实现 SQLite 持久化
        pass
```

---

### 3.4 FMZ 适配器核心逻辑

```python
"""
回测适配器：将 monitor 策略适配到 FMZ 执行引擎
"""

from typing import List, Dict, Callable, Optional
from dataclasses import dataclass

from core.entities import Bar, Signal, ScoringWeights, PinbarConfig
from domain.strategy.pinbar import PinbarStrategy
from .account_simulator import AccountSimulator

@dataclass
class BacktestTrade:
    """回测成交记录"""
    time: int
    symbol: str
    side: str           # "BUY" / "SELL"
    offset: str         # "OPEN" / "CLOSE"
    price: float
    amount: float
    pnl: float = 0.0    # 盈亏（平仓时）
    fee: float = 0.0

class FMZAdapter:
    """
    FMZ 风格回测适配器

    核心逻辑：
    1. 遍历历史 K 线
    2. 在每根 K 线上调用 PinbarStrategy.evaluate()
    3. 根据信号执行模拟交易
    4. 记录所有成交和权益变化
    """

    def __init__(
        self,
        bars: List[Bar],
        strategy: PinbarStrategy,
        initial_balance: float = 10000.0,
        leverage: int = 1,
        fee_rate: float = 0.0005,
        risk_pct: float = 0.02,
        max_sl_dist: float = 0.035,
        pinbar_config: dict = None,
        scoring_weights: dict = None
    ):
        self.bars = bars
        self.strategy = strategy
        self.initial_balance = initial_balance

        # 初始化模拟器
        self.account_sim = AccountSimulator(
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            leverage=leverage
        )

        # 风控参数
        self.risk_pct = risk_pct
        self.max_sl_dist = max_sl_dist

        # 策略配置
        if pinbar_config:
            self.pinbar_config = PinbarConfig(**pinbar_config)
        else:
            self.pinbar_config = PinbarConfig()

        if scoring_weights:
            self.weights = ScoringWeights(**scoring_weights)
        else:
            self.weights = ScoringWeights(w_shape=0.4, w_trend=0.4, w_vol=0.2)

        # 回测统计
        self._trades: List[BacktestTrade] = []
        self._equity_curve: List[dict] = []
        self._signals: List[Signal] = []
        self._current_bar_index = 0
        self._history_bars: List[Bar] = []

    async def run(
        self,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> dict:
        """
        执行回测

        :return: 回测结果统计
        """
        total_bars = len(self.bars)

        for i, bar in enumerate(self.bars):
            # 更新进度
            if on_progress:
                on_progress(i, total_bars)

            # 设置当前 K 线到模拟器
            self.account_sim.set_current_bar(bar)
            self._current_bar_index = i

            # 如果有足够历史数据，执行策略评估
            if len(self._history_bars) >= 60:  # EMA60 需要至少 60 根历史
                signal = self.strategy.evaluate(
                    current_bar=bar,
                    history_bars=self._history_bars.copy(),
                    max_sl_dist=self.max_sl_dist,
                    weights=self.weights,
                    pinbar_config=self.pinbar_config
                )

                if signal:
                    self._signals.append(signal)
                    self._execute_signal(signal, bar)

            # 将当前 K 线加入历史
            self._history_bars.append(bar)
            if len(self._history_bars) > 100:
                self._history_bars.pop(0)

            # 记录权益曲线
            account_state = self.account_sim.get_account_state()
            self._equity_curve.append({
                'time': bar.timestamp,
                'balance': account_state['Balance'],
                'profit': account_state['Profit'],
                'price': bar.close
            })

        # 生成回测报告
        return self._generate_report()

    def _execute_signal(self, signal: Signal, bar: Bar):
        """
        执行交易信号

        简化逻辑：
        - 信号产生时立即以收盘价入场
        - 检查止损/止盈条件
        """
        # 检查是否有反向持仓，先平仓
        for pos in self.account_sim.get_positions():
            if pos['Symbol'] == signal.symbol:
                # 反向信号先平仓
                if (signal.direction == "LONG" and pos['Type'] == 1) or \
                   (signal.direction == "SHORT" and pos['Type'] == 0):
                    order_id = self.account_sim.place_order(
                        symbol=signal.symbol,
                        side="SELL" if pos['Type'] == 0 else "BUY",
                        price=bar.close,
                        amount=pos['Amount'],
                        offset="CLOSE"
                    )
                    self._trades.append(BacktestTrade(
                        time=bar.timestamp,
                        symbol=signal.symbol,
                        side="SELL" if pos['Type'] == 0 else "BUY",
                        offset="CLOSE",
                        price=bar.close,
                        amount=pos['Amount'],
                        pnl=pos['Profit']
                    ))

        # 开新仓
        # 简化：固定使用 10% 资金开仓
        position_value = self.initial_balance * 0.1
        amount = position_value / signal.entry_price

        order_id = self.account_sim.place_order(
            symbol=signal.symbol,
            side="BUY" if signal.direction == "LONG" else "SELL",
            price=signal.entry_price,
            amount=amount,
            offset="OPEN"
        )

        self._trades.append(BacktestTrade(
            time=bar.timestamp,
            symbol=signal.symbol,
            side="BUY" if signal.direction == "LONG" else "SELL",
            offset="OPEN",
            price=signal.entry_price,
            amount=amount
        ))

    def _generate_report(self) -> dict:
        """生成回测报告"""
        # 计算统计数据
        total_trades = len([t for t in self._trades if t.offset == "CLOSE"])
        winning_trades = len([t for t in self._trades if t.offset == "CLOSE" and t.pnl > 0])
        losing_trades = len([t for t in self._trades if t.offset == "CLOSE" and t.pnl < 0])

        win_rate = winning_trades / max(total_trades, 1) * 100

        total_pnl = sum(t.pnl for t in self._trades if t.offset == "CLOSE")
        total_fee = sum(t.fee for t in self._trades)

        final_balance = self.initial_balance + total_pnl - total_fee
        total_return = (final_balance - self.initial_balance) / self.initial_balance * 100

        # 最大回撤
        max_drawdown = self._calculate_max_drawdown()

        # 夏普比率（简化计算）
        sharpe_ratio = self._calculate_sharpe_ratio()

        return {
            'task_id': None,  # 由上层填充
            'summary': {
                'initial_balance': self.initial_balance,
                'final_balance': final_balance,
                'total_return': total_return,
                'total_pnl': total_pnl,
                'total_fee': total_fee,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'profit_factor': winning_trades / max(losing_trades, 1)
            },
            'trades': [
                {
                    'time': t.time,
                    'symbol': t.symbol,
                    'side': t.side,
                    'offset': t.offset,
                    'price': t.price,
                    'amount': t.amount,
                    'pnl': t.pnl,
                    'fee': t.fee
                }
                for t in self._trades
            ],
            'equity_curve': self._equity_curve,
            'signals': [
                {
                    'time': s.timestamp,
                    'symbol': s.symbol,
                    'direction': s.direction,
                    'score': s.score,
                    'entry_price': s.entry_price
                }
                for s in self._signals
            ]
        }

    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self._equity_curve:
            return 0.0

        peak = self.initial_balance
        max_dd = 0.0

        for point in self._equity_curve:
            equity = point['balance'] + point['profit']
            if equity > peak:
                peak = equity

            drawdown = (peak - equity) / peak * 100
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd

    def _calculate_sharpe_ratio(self) -> float:
        """计算夏普比率（简化版）"""
        if len(self._equity_curve) < 2:
            return 0.0

        # 计算收益率序列
        returns = []
        for i in range(1, len(self._equity_curve)):
            prev = self._equity_curve[i-1]
            curr = self._equity_curve[i]

            prev_equity = prev['balance'] + prev['profit']
            curr_equity = curr['balance'] + curr['profit']

            if prev_equity > 0:
                ret = (curr_equity - prev_equity) / prev_equity
                returns.append(ret)

        if not returns:
            return 0.0

        # 简化：假设无风险利率为 0
        import statistics
        if len(returns) < 2:
            return 0.0

        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)

        if std_return == 0:
            return 0.0

        # 年化夏普比率（假设日频数据）
        sharpe = (avg_return / std_return) * (252 ** 0.5)
        return sharpe
```

---

## 4. API 接口设计

### 4.1 RESTful API 新增端点

```yaml
# 回测相关 API

POST /api/backtest/run
  description: 创建并启动回测任务
  request:
    symbol: string        # "BTCUSDT"
    interval: string      # "15m" | "1h" | "4h"
    start_date: string    # "2024-01-01"
    end_date: string      # "2024-12-31"
    initial_balance: number
    leverage: number
    risk_pct: number
    pinbar_config: object
    scoring_weights: object
  response:
    task_id: string
    status: string

GET /api/backtest/tasks
  description: 获取所有回测任务列表
  response:
    tasks: [{task_id, status, progress, created_at, ...}]

GET /api/backtest/task/{task_id}
  description: 获取单个任务状态和结果
  response:
    task_id: string
    status: string
    progress: number
    result: object | null
    error_message: string

POST /api/backtest/task/{task_id}/cancel
  description: 取消运行中的任务

DELETE /api/backtest/task/{task_id}
  description: 删除已完成的任务

GET /api/backtest/task/{task_id}/result
  description: 获取回测结果详情
  response:
    summary: {total_return, win_rate, max_drawdown, ...}
    trades: [...]
    equity_curve: [...]

POST /api/backtest/optimize
  description: 启动参数优化任务（异步）
  request:
    symbol: string
    interval: string
    start_date: string
    end_date: string
    optimize_params: string[]  # ["risk_pct", "pinbar_config.shadow_min_ratio"]
    ranges: object           # 参数范围配置
  response:
    optimization_id: string

GET /api/backtest/optimize/{optimization_id}
  description: 获取参数优化进度和结果
```

### 4.2 WebSocket 实时推送

```python
# WebSocket 端点：/ws/backtest/{task_id}
# 用于实时推送回测进度

async def backtest_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()

    while True:
        task = backtest_service.get_task_status(task_id)
        if task:
            await websocket.send_json({
                'task_id': task.task_id,
                'status': task.status,
                'progress': task.progress,
                'message': task.message
            })

        if task.status in ['completed', 'failed']:
            break

        await asyncio.sleep(1)
```

---

## 5. 数据库设计扩展

### 5.1 新增表结构

```sql
-- 回测任务表
CREATE TABLE IF NOT EXISTS backtest_tasks (
    task_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    config_json TEXT,          -- JSON 格式存储完整配置
    result_json TEXT,          -- JSON 格式存储结果
    progress INTEGER DEFAULT 0,
    error_message TEXT,
    created_at INTEGER NOT NULL,
    started_at INTEGER,
    completed_at INTEGER
);

-- 回测交易记录表
CREATE TABLE IF NOT EXISTS backtest_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    time INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    offset TEXT NOT NULL,
    price REAL NOT NULL,
    amount REAL NOT NULL,
    pnl REAL DEFAULT 0,
    fee REAL DEFAULT 0,
    FOREIGN KEY (task_id) REFERENCES backtest_tasks(task_id)
);

-- 参数优化任务表
CREATE TABLE IF NOT EXISTS optimization_tasks (
    optimization_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    base_config_json TEXT,
    optimize_params_json TEXT,
    results_json TEXT,         -- 多组参数对比结果
    progress INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL,
    completed_at INTEGER
);
```

---

## 6. 前端 UI 扩展

### 6.1 新增页面组件

```
web_ui/
├── App.tsx                      # 添加"回测实验室"Tab
├── BacktestLab.tsx              # 新增：回测配置和结果展示
│   ├── BacktestConfigForm.tsx   # 回测参数配置表单
│   ├── BacktestTaskList.tsx     # 任务列表面板
│   ├── BacktestProgress.tsx     # 进度条和实时日志
│   └── BacktestResult.tsx       # 结果展示组件
│       ├── SummaryCards.tsx     # 关键指标卡片
│       ├── EquityChart.tsx      # 权益曲线图
│       ├── TradeList.tsx        # 成交明细表
│       └── SignalAnalysis.tsx   # 信号统计分析
└── OptimizeLab.tsx              # 新增：参数优化实验室
    ├── OptimizeConfigForm.tsx   # 优化参数范围配置
    ├── OptimizeProgress.tsx     # 优化进度（热力图）
    └── OptimizeResult.tsx       # 最优参数组合展示
```

### 6.2 回测结果可视化

使用 `lightweight-charts v5`（已用于 SignalChartModal）扩展：

1. **权益曲线图** - 展示账户余额变化
2. **回撤曲线图** - 展示最大回撤发生时段
3. **月度收益热力图** - 展示各月收益分布
4. **信号分布散点图** - 展示信号在时间轴上的分布

---

## 7. 参数优化方案

### 7.1 网格搜索实现

```python
from itertools import product
from typing import Dict, List

class GridSearchOptimizer:
    """
    网格搜索参数优化器

    暴力枚举所有参数组合，找到最优配置
    """

    def __init__(self, param_grid: Dict[str, List[float]]):
        """
        :param param_grid: 参数范围配置
        示例：
        {
            "risk_pct": [0.01, 0.02, 0.03],
            "max_sl_dist": [0.025, 0.035, 0.05],
            "pinbar_config.shadow_min_ratio": [2.0, 2.5, 3.0]
        }
        """
        self.param_grid = param_grid

    def get_all_combinations(self) -> List[Dict[str, float]]:
        """生成所有参数组合"""
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())

        combinations = []
        for combination in product(*values):
            param_set = dict(zip(keys, combination))
            combinations.append(param_set)

        return combinations

    async def run(
        self,
        base_config: dict,
        backtest_service: BacktestService,
        metric: str = "total_return"  # 优化目标：total_return | win_rate | sharpe_ratio
    ) -> List[dict]:
        """
        运行网格搜索

        :return: 按目标指标排序的结果列表
        """
        all_combinations = self.get_all_combinations()
        results = []

        for i, params in enumerate(all_combinations):
            # 合并基础配置和当前参数组合
            config = base_config.copy()
            self._apply_params(config, params)

            # 创建回测任务
            task_id = backtest_service.create_backtest_task(**config)

            # 等待任务完成
            while True:
                task = backtest_service.get_task_status(task_id)
                if task.status in ['completed', 'failed']:
                    break
                await asyncio.sleep(1)

            if task.status == 'completed':
                result = task.result
                result['params'] = params
                results.append(result)

        # 按目标指标排序
        results.sort(
            key=lambda x: x['summary'].get(metric, 0),
            reverse=True
        )

        return results

    def _apply_params(self, config: dict, params: dict):
        """将参数组合应用到配置中"""
        for key, value in params.items():
            keys = key.split('.')
            target = config
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value
```

### 7.2 遗传算法优化（可选扩展）

```python
"""
遗传算法参数优化器

适用于参数空间较大时的智能搜索
"""

import random
from typing import Dict, List

class GeneticOptimizer:
    """
    遗传算法参数优化

    核心步骤：
    1. 初始化种群 - 随机生成 N 组参数
    2. 适应度评估 - 运行回测计算收益
    3. 选择 - 保留表现最好的参数组
    4. 交叉 - 组合优秀参数组的基因
    5. 变异 - 随机扰动部分参数
    6. 重复 2-5 直到收敛
    """

    def __init__(
        self,
        param_ranges: Dict[str, tuple],  # {"risk_pct": (0.01, 0.05)}
        population_size: int = 20,
        generations: int = 10,
        mutation_rate: float = 0.1
    ):
        self.param_ranges = param_ranges
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate

    def _create_individual(self) -> Dict[str, float]:
        """创建随机个体"""
        return {
            key: random.uniform(min_val, max_val)
            for key, (min_val, max_val) in self.param_ranges.items()
        }

    def _crossover(
        self,
        parent1: Dict[str, float],
        parent2: Dict[str, float]
    ) -> Dict[str, float]:
        """交叉操作"""
        child = {}
        for key in self.param_ranges.keys():
            if random.random() < 0.5:
                child[key] = parent1[key]
            else:
                child[key] = parent2[key]
        return child

    def _mutate(self, individual: Dict[str, float]) -> Dict[str, float]:
        """变异操作"""
        mutated = individual.copy()
        for key in mutated:
            if random.random() < self.mutation_rate:
                min_val, max_val = self.param_ranges[key]
                mutated[key] = random.uniform(min_val, max_val)
        return mutated

    async def run(
        self,
        backtest_service: BacktestService,
        base_config: dict
    ) -> Dict[str, float]:
        """运行遗传优化"""
        # 1. 初始化种群
        population = [self._create_individual() for _ in range(self.population_size)]

        best_params = None
        best_fitness = float('-inf')

        for generation in range(self.generations):
            # 2. 评估适应度
            fitness_scores = []
            for individual in population:
                # 创建回测任务
                config = base_config.copy()
                self._apply_params(config, individual)
                task_id = backtest_service.create_backtest_task(**config)

                # 等待完成
                while True:
                    task = backtest_service.get_task_status(task_id)
                    if task.status in ['completed', 'failed']:
                        break
                    await asyncio.sleep(1)

                if task.status == 'completed':
                    fitness = task.result['summary']['total_return']
                else:
                    fitness = float('-inf')

                fitness_scores.append(fitness)

                if fitness > best_fitness:
                    best_fitness = fitness
                    best_params = individual

            # 3. 选择（锦标赛选择法）
            selected = self._tournament_select(population, fitness_scores)

            # 4. 交叉和变异生成新一代
            new_population = []
            while len(new_population) < self.population_size:
                parent1, parent2 = random.sample(selected, 2)
                child = self._crossover(parent1, parent2)
                child = self._mutate(child)
                new_population.append(child)

            population = new_population

        return best_params
```

---

## 8. 实施计划

### 8.1 阶段划分

| 阶段 | 内容 | 预计工时 | 优先级 |
|-----|------|---------|-------|
| **Phase 1** | 核心适配器开发 | 3 天 | P0 |
| - AccountSimulator 账户模拟器 |  |  |  |
| - FMZAdapter 回测适配器 |  |  |  |
| - 基础回测流程打通 |  |  |  |
| **Phase 2** | 回测服务层 | 2 天 | P0 |
| - BacktestService 服务类 |  |  |  |
| - SQLite 结果持久化 |  |  |  |
| - RESTful API 端点 |  |  |  |
| **Phase 3** | 前端 UI | 3 天 | P1 |
| - BacktestLab 页面 |  |  |  |
| - 结果可视化图表 |  |  |  |
| - WebSocket 进度推送 |  |  |  |
| **Phase 4** | 参数优化 | 2 天 | P2 |
| - GridSearchOptimizer |  |  |  |
| - OptimizeLab 页面 |  |  |  |
| **Phase 5** | 扩展功能 | 2 天 | P3 |
| - 多币种批量回测 |  |  |  |
| - 遗传算法优化 |  |  |  |
| - 回测报告导出 |  |  |  |

### 8.2 关键里程碑

1. **MVP 完成** (Phase 1+2): 能够运行单次回测并返回结果
2. **UI 集成** (Phase 3): 用户可通过界面配置和执行回测
3. **完整功能** (Phase 4+5): 参数优化和批量回测

---

## 9. 风险和挑战

### 9.1 技术风险

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| FMZ .so 库依赖 | 需要额外下载安装 | 采用纯 Python 适配器，不依赖 FMZ 动态库 |
| 回测速度 | 大量 K 线时耗时 | 异步执行 + 进度推送，支持取消 |
| 内存消耗 | 历史 K 线占用 | 流式处理，分批加载 |

### 9.2 业务风险

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 过度拟合 | 参数优化结果在实盘失效 | 提供样本外验证功能 |
| 回测假设过于理想 | 实际成交有滑点 | 添加滑点参数配置 |
| 幸存者偏差 | 仅回测当前主流币种 | 添加退市币种警告 |

---

## 10. 测试策略

### 10.1 单元测试

```python
# tests/test_backtest_adapter.py

def test_account_simulator_basic_order():
    """测试基本下单和成交"""
    sim = AccountSimulator(initial_balance=10000, fee_rate=0.0005)
    sim.set_current_bar(mock_bar)

    order_id = sim.place_order("BTCUSDT", "BUY", 50000, 0.1, "OPEN")

    assert order_id == 1
    account = sim.get_account_state()
    assert account['Balance'] < 10000  # 扣除了手续费

def test_fmz_adapter_full_cycle():
    """测试完整回测流程"""
    adapter = FMZAdapter(
        bars=mock_bars_100,
        strategy=mock_strategy,
        initial_balance=10000
    )

    result = await adapter.run()

    assert 'summary' in result
    assert 'trades' in result
    assert 'equity_curve' in result
```

### 10.2 集成测试

```python
# tests/test_backtest_service.py

async def test_backtest_service_create_and_run():
    """测试回测服务创建任务和运行"""
    service = BacktestService(...)

    task_id = service.create_backtest_task(
        symbol="BTCUSDT",
        interval="1h",
        start_date="2024-01-01",
        end_date="2024-01-31"
    )

    # 等待任务完成
    await asyncio.sleep(10)

    task = service.get_task_status(task_id)
    assert task.status == "completed"
    assert task.result is not None
```

---

## 11. 总结

### 11.1 核心优势

1. **复用现有代码** - PinbarStrategy 无需修改，直接用于回测
2. **零执行风险** - 回测环境完全隔离，不影响实时监测
3. **渐进式实现** - 从基础回测到参数优化，可分阶段交付
4. **纯 Python 实现** - 不依赖 FMZ 动态库，降低部署复杂度

### 11.2 预期效果

集成完成后，系统将具备：
- **策略验证** - 在实盘前验证策略有效性
- **参数调优** - 找到最优策略参数
- **绩效分析** - 全面评估策略表现
- **风险控制** - 避免在不利市场条件下开仓

### 11.3 后续扩展

1. **多策略支持** - 除 Pinbar 外，支持其他策略类型
2. **实盘对接** - 将回测结果信号推送给执行系统（需额外授权）
3. **机器学习** - 使用 ML 模型预测信号胜率

---

*文档结束*
