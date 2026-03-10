"""
应用层：持仓查询服务
职责：编排账户读取器和仓储，提供持仓相关用例
"""
from typing import List, Dict, Any, Optional
from core.interfaces import IAccountReader, IRepository
from core.entities import AccountBalance


class PositionService:
    """持仓应用服务"""

    def __init__(self, account_reader: IAccountReader, repo: IRepository):
        self.account_reader = account_reader
        self.repo = repo

    async def get_full_account_data(self) -> Optional[AccountBalance]:
        """
        获取完整账户数据（一次 API 调用）
        返回原始的 AccountBalance 对象，包含所有字段

        :return: AccountBalance 对象或 None（如果失败）
        """
        return await self.account_reader.fetch_account_balance()

    async def refresh_positions(self) -> List[Dict[str, Any]]:
        """
        实时刷新持仓
        从币安 API 获取最新持仓数据

        :return: 持仓列表，每个持仓是一个字典（驼峰命名）
        """
        # 调用账户读取器获取实时持仓
        account = await self.account_reader.fetch_account_balance()
        # 确保返回空列表而非 None
        positions = account.positions if account.positions else []

        # 将 dataclass 转换为字典，并转换为驼峰命名以适配前端
        return [
            {
                "symbol": p.symbol,
                "positionAmt": p.quantity * (1 if p.direction == "LONG" else -1),  # 带符号的持仓数量
                "entryPrice": p.entry_price,
                "unrealized_pnl": p.unrealized_pnl,
                "leverage": p.leverage,
            }
            for p in positions
        ]

    async def get_wallet_balance(self) -> float:
        """
        获取钱包余额（初始保证金）
        """
        account = await self.account_reader.fetch_account_balance()
        return account.total_wallet_balance

    async def get_unrealized_pnl(self) -> float:
        """
        获取总计未实现盈亏
        """
        account = await self.account_reader.fetch_account_balance()
        return account.total_unrealized_pnl

    async def get_margin_balance(self, wallet_balance: float, unrealized_pnl: float) -> float:
        """
        计算保证金余额 = 钱包余额 + 未实现盈亏
        """
        return wallet_balance + unrealized_pnl
