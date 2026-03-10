"""
模拟交易执行器 - 用于回测系统中的持仓管理和资金费率结算
"""
from typing import Dict


class Position:
    """持仓对象"""

    def __init__(self, symbol: str, qty: float, entry_price: float, direction: str):
        self.symbol = symbol
        self.qty = qty
        self.entry_price = entry_price
        self.direction = direction  # 'long' or 'short'


class SimulatedExecutor:
    """
    模拟交易执行器

    用于回测系统中管理虚拟持仓、余额和资金费率结算
    """

    FUNDING_RATE_TIMESTAMPS_MOD = 8 * 3600 * 1000  # 8 小时毫秒数

    def __init__(self, initial_balance: float = 10000.0):
        self._balance = initial_balance
        self._positions: Dict[str, Position] = {}

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def positions(self) -> Dict[str, Position]:
        return self._positions

    def _settle_funding_rate(self, timestamp: int, funding_rate: float,
                             current_prices: Dict[str, float]) -> None:
        """
        检查当前时间戳是否到达资金费率结算点（UTC 0/8/16 整点），
        若是则按持仓名义价值结算资金费。

        funding_rate > 0: 多头付给空头
        funding_rate < 0: 空头付给多头

        Args:
            timestamp: 当前时间戳（毫秒）
            funding_rate: 资金费率
            current_prices: 当前价格字典 {symbol: price}
        """
        # 判断是否在结算窗口内（精确到小时）
        hour_ts = (timestamp // 1000) % (24 * 3600)
        if hour_ts not in [0, 8 * 3600, 16 * 3600]:
            return

        for symbol, pos in self._positions.items():
            notional = pos.qty * current_prices.get(symbol, pos.entry_price)
            fee = notional * funding_rate
            if pos.direction == 'long':
                self._balance -= fee   # 多头在费率为正时付费
            else:
                self._balance += fee   # 空头在费率为正时收费

    def open_position(self, symbol: str, qty: float, price: float, direction: str) -> None:
        """开仓"""
        self._positions[symbol] = Position(symbol, qty, price, direction)
        self._balance -= qty * price  # 简单起见，全额扣除保证金

    def close_position(self, symbol: str, price: float) -> float:
        """平仓，返回盈亏"""
        if symbol not in self._positions:
            return 0.0

        pos = self._positions.pop(symbol)
        pnl = pos.qty * (price - pos.entry_price)
        if pos.direction == 'short':
            pnl = -pnl

        self._balance += pos.qty * pos.entry_price  # 返还保证金
        self._balance += pnl  # 加上盈亏
        return pnl
