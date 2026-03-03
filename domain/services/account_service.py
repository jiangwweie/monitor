"""
账户服务模块
提供账户余额、持仓等数据的读取功能。
"""
import logging
from typing import Dict, Any, List, Optional

from infrastructure.reader.binance_api import BinanceAccountReader
from core.entities import AccountBalance, PositionDetail

logger = logging.getLogger(__name__)


class AccountService:
    """
    账户服务类
    统一管理账户数据读取操作，封装 BinanceAccountReader 的访问逻辑。
    """

    def __init__(self, account_reader: Optional[BinanceAccountReader] = None):
        """
        初始化账户服务

        :param account_reader: BinanceAccountReader 实例，用于获取账户数据
        """
        self.account_reader = account_reader

    def set_account_reader(self, account_reader: BinanceAccountReader):
        """
        设置或更新账户读取器

        :param account_reader: BinanceAccountReader 实例
        """
        self.account_reader = account_reader

    async def get_balance(self) -> Dict[str, Any]:
        """
        获取账户余额信息

        :return: 包含余额信息的字典
        :raises: HTTPException 当 API 密钥未配置或请求失败时
        """
        if not self.account_reader:
            raise ValueError("BinanceAccountReader 未初始化")

        balance: AccountBalance = await self.account_reader.fetch_account_balance()

        return {
            "total_wallet_balance": balance.total_wallet_balance,
            "available_balance": balance.available_balance,
            "total_balance": balance.total_balance,
            "available_margin": balance.available_margin,
            "total_unrealized_pnl": balance.total_unrealized_pnl,
            "current_positions_count": balance.current_positions_count,
            "positions": balance.positions,
        }

    async def get_positions(self) -> Dict[str, Any]:
        """
        获取账户持仓列表

        :return: 包含持仓列表的字典
        :raises: HTTPException 当 API 密钥未配置或请求失败时
        """
        if not self.account_reader:
            raise ValueError("BinanceAccountReader 未初始化")

        balance: AccountBalance = await self.account_reader.fetch_account_balance()

        return {
            "total_wallet_balance": balance.total_wallet_balance,
            "available_balance": balance.available_balance,
            "total_unrealized_pnl": balance.total_unrealized_pnl,
            "current_positions_count": balance.current_positions_count,
            "positions": balance.positions,
        }

    async def get_position_detail(self, symbol: str) -> Dict[str, Any]:
        """
        获取指定交易对的持仓详情

        :param symbol: 交易对符号，如 "BTCUSDT"
        :return: 包含持仓详情的字典
        :raises: HTTPException 当 API 密钥未配置或请求失败时
        """
        if not self.account_reader:
            raise ValueError("BinanceAccountReader 未初始化")

        detail: PositionDetail = await self.account_reader.fetch_position_detail(symbol)

        from dataclasses import asdict
        return asdict(detail)

    async def get_dashboard(self) -> Dict[str, Any]:
        """
        获取账户仪表盘数据（聚合余额和持仓）

        :return: 包含完整账户信息的字典
        :raises: HTTPException 当 API 密钥未配置或请求失败时
        """
        if not self.account_reader:
            raise ValueError("BinanceAccountReader 未初始化")

        balance: AccountBalance = await self.account_reader.fetch_account_balance()

        return {
            "total_wallet_balance": balance.total_wallet_balance,
            "available_balance": balance.available_balance,
            "total_balance": balance.total_balance,
            "available_margin": balance.available_margin,
            "total_unrealized_pnl": balance.total_unrealized_pnl,
            "current_positions_count": balance.current_positions_count,
            "positions": balance.positions,
        }

    async def check_api_keys_configured(self, repo) -> bool:
        """
        检查 API 密钥是否已配置

        :param repo: SQLiteRepo 实例，用于检查密钥配置
        :return: 如果密钥已配置返回 True，否则返回 False
        """
        api_key = await repo.get_secret("binance_api_key")
        api_secret = await repo.get_secret("binance_api_secret")
        return bool(api_key and api_secret)

    async def update_api_keys(self, repo, api_key: str, api_secret: str) -> bool:
        """
        更新 API 密钥配置

        :param repo: SQLiteRepo 实例
        :param api_key: 新的 API 密钥
        :param api_secret: 新的 API 密钥密钥
        :return: 更新是否成功
        """
        if api_key:
            await repo.set_secret("binance_api_key", api_key)
        if api_secret:
            await repo.set_secret("binance_api_secret", api_secret)

        # 更新内部 reader 的密钥
        if self.account_reader:
            if api_key:
                self.account_reader.api_key = api_key
            if api_secret:
                self.account_reader.api_secret = api_secret

        return True
