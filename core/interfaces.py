"""
核心抽象接口模块
本模块定义了系统的外部接口规范。严格遵循六边形架构，所有外部 I/O 及副作用均被抽象为接口。
严格遵守 Zero Execution 的安全底线。
"""
from abc import ABC, abstractmethod
from typing import List, AsyncIterator, Tuple, Optional

from .entities import Bar, AccountBalance, Signal, PositionSizing, RiskConfig, SignalFilter, PositionDetail

class IDataFeed(ABC):
    """实时行情源订阅接口
    用于通过 WebSocket 流式获取市场最新闭合 K 线。
    """
    @abstractmethod
    async def subscribe_klines(self, symbols: List[str], intervals: List[str]) -> AsyncIterator[Bar]:
        """订阅流式K线，yield 已经闭合的 Bar 对象"""
        pass

class IAccountReader(ABC):
    """交易所只读账户适配器接口
    拉取钱包余额等静态数据。禁止任何发单操作。
    """
    @abstractmethod
    async def fetch_account_balance(self) -> AccountBalance:
        """获取真实的钱包余额与当前持仓笔数"""
        pass

    @abstractmethod
    async def fetch_position_detail(self, symbol: str) -> PositionDetail:
        """获取指定交易对的实盘持仓详情及止盈止损挂单"""
        pass

class IExchangeAPI(ABC):
    """交易所读取适配器接口
    此接口被严格限制为只读请求，绝无任何下单、撤单、改单或平仓功能。
    """
    
    @abstractmethod
    async def fetch_klines(self, symbol: str, interval: str, limit: int) -> List[Bar]:
        """拉取指定交易对的K线数据 (如 GET /fapi/v1/klines)"""
        pass

    @abstractmethod
    async def fetch_account_balance(self) -> AccountBalance:
        """获取真实的钱包余额与当前持仓笔数 (如 GET /fapi/v2/account)"""
        pass

    @abstractmethod
    async def fetch_position_detail(self, symbol: str) -> PositionDetail:
        """获取指定交易对的实盘持仓详情及止盈止损挂单 (如 GET /fapi/v2/positionRisk & /fapi/v1/openOrders)"""
        pass

class IRepository(ABC):
    """持久化仓储接口
    用于持久化算仓快照和系统信号，这仅用于审计、回测与日志记录。
    """
    
    @abstractmethod
    async def save_signal(self, signal: Signal) -> None:
        """异步持久化验证成功的信号"""
        pass

    @abstractmethod
    async def save_position_sizing(self, sizing: PositionSizing) -> None:
        """异步持久化算仓推荐快照"""
        pass

    @abstractmethod
    async def get_signals(self, filter_params: SignalFilter, page: int = 1, size: int = 50) -> Tuple[int, List[Signal]]:
        """按过滤条件分页查询历史信号"""
        pass

    @abstractmethod
    async def delete_signals(self, ids: List[int]) -> int:
        """根据内部ID列表批量删除信号，返回删除成功条数"""
        pass

    @abstractmethod
    async def cleanup_old_signals(self, days: int = 7) -> int:
        """一键清理 N 天前数据记录"""
        pass

class IConfigProvider(ABC):
    """配置加载接口
    支持从数据源加载开关控制与其他参数。
    """
    
    @abstractmethod
    async def get_risk_config(self) -> RiskConfig:
        """获取最新风控算仓参数"""
        pass

    @abstractmethod
    async def is_system_enabled(self) -> bool:
        """拉取系统级运行开关与熔断状态"""
        pass

class INotifier(ABC):
    """通知推送接口
    将决策与建议作为输出返回的契约，严禁通过此接口发送真实订单。
    """
    
    @abstractmethod
    async def send_markdown(self, formatted_message: str) -> None:
        """发送 Markdown 富文本格式的交易监控决策推送"""
        pass
