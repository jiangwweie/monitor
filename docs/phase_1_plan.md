# Phase 1: 脚手架与核心契约搭建设计文档

本文档定义了 `core/entities.py` 和 `core/interfaces.py` 的具体设计，严格遵守无第三方依赖、只读约束（纯监听与计算辅助）和领域驱动设计（DDD）规范。

## 1. 核心实体 (`core/entities.py`)

本文件仅允许引人标准库（如 `dataclasses`, `datetime`, `typing`），绝对禁止任何第三方框架（如 pydantic, SQLAlchemy 等）。提供纯粹的数据载体。

### 1.1 K线/基础数据实体 (`Bar`)
```python
from dataclasses import dataclass

@dataclass
class Bar:
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool  # 仅处理 is_closed=True 的K线
```

### 1.2 账户资产实体 (`AccountBalance`)
表示从交易所获取的真实账户只读状态。
```python
from dataclasses import dataclass

@dataclass
class AccountBalance:
    total_wallet_balance: float
    available_balance: float
    current_positions_count: int  # 现有的持仓笔数（n）
```

### 1.3 信号快照实体 (`Signal`)
策略引擎（Pinbar+EMA60）产生的有效信号快照。
```python
from dataclasses import dataclass

@dataclass
class Signal:
    symbol: str
    direction: str         # "LONG" 或 "SHORT"
    entry_price: float
    stop_loss: float
    take_profit_1: float
    timestamp: int
    reason: str            # 命中理由，例如 "Pinbar+EMA60"
    sl_distance_pct: float # 止损距离百分比
```

### 1.4 风控算仓建议实体 (`PositionSizing`)
基于风控参数和账户真实余额推算的只读建议，用于通知推送与日志记录。
```python
from dataclasses import dataclass

@dataclass
class PositionSizing:
    signal: Signal
    suggested_leverage: float  # 建议杠杆，受限于 max_leverage
    suggested_quantity: float  # 建议开仓数量
    investment_amount: float   # 最后分配的本金
    risk_amount: float         # 承担的固定风险额
```

### 1.5 风控配置实体 (`RiskConfig`)
处理 K 线前进行热加载的风控参数。
```python
from dataclasses import dataclass

@dataclass
class RiskConfig:
    risk_pct: float      # 单笔最大风险百分比，例如 0.02 (2%)
    max_sl_dist: float   # 天地针熔断最大止损距离，例如 0.035 (3.5%)
    max_leverage: float  # 杠杆熔断上限，例如 20.0
```

---

## 2. 核心抽象接口 (`core/interfaces.py`)

本文件仅包含使用 `abc.ABC` 和 `abc.abstractmethod` 定义的接口签名。严格遵循六边形架构，所有外部 I/O 及副作用全部被抽象为端口（Port）。同时，**严格遵守 "Zero Execution" 的安全底线**。

### 2.1 交易所读取适配器接口 (`IExchangeAPI`)
此接口被严格限制为**只读请求**，绝无任何下单或平仓功能。
```python
from abc import ABC, abstractmethod
from typing import List
from .entities import Bar, AccountBalance

class IExchangeAPI(ABC):
    @abstractmethod
    async def fetch_klines(self, symbol: str, interval: str, limit: int) -> List[Bar]:
        """拉取指定交易对的K线数据 (如 GET /fapi/v1/klines)"""
        pass

    @abstractmethod
    async def fetch_account_balance(self) -> AccountBalance:
        """获取真实的钱包余额与当前持仓笔数 (如 GET /fapi/v2/account)"""
        pass
```

### 2.2 持久化仓储接口 (`IRepository`)
用于使用 `aiosqlite` 异步持久化算仓快照和系统信号。
```python
from abc import ABC, abstractmethod
from .entities import Signal, PositionSizing

class IRepository(ABC):
    @abstractmethod
    async def save_signal(self, signal: Signal) -> None:
        """异步持久化验证成功的信号"""
        pass

    @abstractmethod
    async def save_position_sizing(self, sizing: PositionSizing) -> None:
        """异步持久化算仓推荐快照"""
        pass
```

### 2.3 配置加载接口 (`IConfigProvider`)
支持从本地数据库加载开关控制与其他参数。
```python
from abc import ABC, abstractmethod
from .entities import RiskConfig

class IConfigProvider(ABC):
    @abstractmethod
    async def get_risk_config(self) -> RiskConfig:
        """获取最新风控算仓参数"""
        pass

    @abstractmethod
    async def is_system_enabled(self) -> bool:
        """拉取系统级运行开关与熔断状态"""
        pass
```

### 2.4 通知推送接口 (`INotificationProvider`)
将结果并行推向 飞书/Telegram 等渠道的输出契约。
```python
from abc import ABC, abstractmethod
from .entities import PositionSizing

class INotificationProvider(ABC):
    @abstractmethod
    async def send_notification(self, formatted_message: str) -> None:
        """发送 Markdown 富文本格式的交易监控决策推送"""
        pass
```
