"""
应用层：持仓查询服务
职责：编排账户读取器和仓储，提供持仓相关用例
"""
from typing import List, Dict, Any
from core.interfaces import IAccountReader, IRepository


class PositionService:
    """持仓应用服务"""

    def __init__(self, account_reader: IAccountReader, repo: IRepository):
        self.account_reader = account_reader
        self.repo = repo

    async def refresh_positions(self) -> List[Dict[str, Any]]:
        """
        实时刷新持仓
        从币安 API 获取最新持仓数据

        :return: 持仓列表，每个持仓是一个字典
        """
        # 调用账户读取器获取实时持仓
        account = await self.account_reader.fetch_account_balance()
        # 确保返回空列表而非 None
        return account.positions if account.positions else []

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
