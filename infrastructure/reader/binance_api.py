"""
 Binance 交易所 HTTP 账户信息读取探针 (Infrastructure 层)
 提供账户余额与持仓等维度的数据快照以供风控算仓大脑参考。
 【绝对红线】：严禁包含任何下单和操作的方法。纯 Read-Only 客户端。
"""
import time
import hmac
import hashlib
import json
import logging
from urllib.parse import urlencode

import httpx

from core.entities import AccountBalance, Position, PositionDetail
from core.interfaces import IAccountReader

logger = logging.getLogger(__name__)

class BinanceAccountReader(IAccountReader):
    """
    只读的 Binance HTTP 服务适配器。
    用于发起 HMAC SHA256 签名的纯读取请求获取账户持仓。
    """
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://fapi.binance.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.server_time_offset: int = 0  # 服务器时间偏移量（毫秒）
        self._time_synced: bool = False

    def _generate_signature(self, query_string: str) -> str:
        """生成 Binance HMAC SHA256 跨域通信需要的签名"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _sync_server_time(self) -> None:
        """同步服务器时间，计算本地与 Binance 服务器的时间偏移量"""
        try:
            async with httpx.AsyncClient() as client:
                # 获取服务器时间（公开接口，无需签名）
                response = await client.get(f"{self.base_url}/fapi/v1/time", timeout=5.0)
                response.raise_for_status()
                data = response.json()
                server_time = data.get("serverTime", 0)
                local_time = int(time.time() * 1000)
                self.server_time_offset = server_time - local_time
                self._time_synced = True
                logger.debug(f"时间同步完成：本地={local_time}, 服务器={server_time}, 偏移量={self.server_time_offset}ms")
        except Exception as e:
            logger.warning(f"时间同步失败：{e}，将使用本地时间戳")
            self.server_time_offset = 0

    def _get_timestamp(self) -> int:
        """获取校正后的时间戳（毫秒）"""
        return int(time.time() * 1000) + self.server_time_offset

    async def fetch_account_balance(self) -> AccountBalance:
        """
        发送 GET 请求到 /fapi/v2/account 取回账户详细持仓。
        绝对红线：此处使用 httpx.AsyncClient 执行 GET，决不能包含 POST 逻辑。
        """
        endpoint = "/fapi/v2/account"

        # 首次调用时同步服务器时间
        if not self._time_synced:
            await self._sync_server_time()

        # 使用校正后的时间戳
        timestamp = self._get_timestamp()
        params = {"timestamp": timestamp}
        query_string = urlencode(params)
        signature = self._generate_signature(query_string)

        url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"

        headers = {
            "X-MBX-APIKEY": self.api_key
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)

                # 如果是时间戳错误，尝试重新同步后重试一次
                if response.status_code == 400:
                    error_data = response.json() if response.content else {}
                    error_code = error_data.get("code", 0)
                    if error_code == -1021:  # Timestamp outside recvWindow
                        logger.warning("检测到时间戳错误，重新同步服务器时间后重试...")
                        await self._sync_server_time()

                        # 使用新时间戳重试
                        timestamp = self._get_timestamp()
                        params = {"timestamp": timestamp}
                        query_string = urlencode(params)
                        signature = self._generate_signature(query_string)
                        url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"

                        response = await client.get(url, headers=headers, timeout=10.0)

                response.raise_for_status()
                data = response.json()
                
                # U本位下，取得 'totalWalletBalance', 'availableBalance' 以及其他新增字段
                total_wallet_balance = float(data.get("totalWalletBalance", 0.0))
                available_balance = float(data.get("availableBalance", 0.0))
                total_unrealized_pnl = float(data.get("totalUnrealizedProfit", 0.0))
                total_margin_balance = float(data.get("totalMarginBalance", total_wallet_balance + total_unrealized_pnl))
                
                # 统计当前实际真实持仓的笔数
                # Binance 返回的持仓包含所有的交易对列表，只有当 positionAmt != '0' 且不等于 0 时，才算真实持有该币种
                positions = data.get("positions", [])
                current_positions_count = 0
                position_list = []
                for pos in positions:
                    amt_str = pos.get("positionAmt", "0")
                    # 忽略浮点数转换错误或者本身没有任何数量的空槽位
                    try:
                        amt = float(amt_str)
                        if abs(amt) > 0:
                            current_positions_count += 1
                            entry_price = float(pos.get("entryPrice", 0.0))
                            quantity = abs(amt)
                            # 根据 positionAmt 的正负判断方向
                            direction = "LONG" if amt > 0 else "SHORT"
                            position_list.append(Position(
                                symbol=pos.get("symbol", ""),
                                quantity=quantity,
                                entry_price=entry_price,
                                leverage=int(pos.get("leverage", 1)),
                                unrealized_pnl=float(pos.get("unrealizedProfit", pos.get("unRealizedProfit", 0.0))),
                                position_value=quantity * entry_price,
                                risk_amount=0.0,  # 开仓时由 PositionSizer 计算，此处默认为 0
                                direction=direction
                            ))
                    except ValueError:
                        pass

                return AccountBalance(
                    total_wallet_balance=total_wallet_balance,
                    available_balance=available_balance,
                    total_balance=total_wallet_balance, # 为了兼容前端字段名，总资金等同于钱包余额
                    available_margin=available_balance, # 可用保证金等同于 available_balance
                    total_unrealized_pnl=total_unrealized_pnl,
                    current_positions_count=current_positions_count,
                    positions=position_list
                )

            except httpx.HTTPStatusError as e:
                logger.error(f"Binance Account API 获取异常，HTTP 状态码: {e.response.status_code}, 内容: {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Binance Account API 网络请求失败：{type(e).__name__} - {str(e)}")
                raise
            except Exception as e:
                logger.error(f"获取账户数据时发生未知错误：{type(e).__name__} - {str(e)}")
                raise

    async def fetch_position_detail(self, symbol: str) -> PositionDetail:
        """
        获取指定交易对的实盘持仓详情及止盈止损挂单。
        并发请求 /fapi/v2/positionRisk 和 /fapi/v1/openOrders。
        """
        import asyncio

        # 首次调用时同步服务器时间
        if not self._time_synced:
            await self._sync_server_time()

        async with httpx.AsyncClient() as client:
            async def _signed_get(endpoint: str, **kwargs):
                timestamp = self._get_timestamp()
                params_obj = {"timestamp": timestamp, **kwargs}
                query_string = urlencode(params_obj)
                signature = self._generate_signature(query_string)
                url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
                headers = {"X-MBX-APIKEY": self.api_key}
                response = await client.get(url, headers=headers, timeout=10.0)

                # 时间戳错误时重试一次
                if response.status_code == 400:
                    error_data = response.json() if response.content else {}
                    if error_data.get("code") == -1021:
                        logger.warning(f"时间戳错误，重新同步后重试：{endpoint}")
                        await self._sync_server_time()
                        timestamp = self._get_timestamp()
                        params_obj = {"timestamp": timestamp, **kwargs}
                        query_string = urlencode(params_obj)
                        signature = self._generate_signature(query_string)
                        url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
                        response = await client.get(url, headers=headers, timeout=10.0)

                response.raise_for_status()
                return response.json()

            try:
                # 1. 并发拉取
                risk_task = _signed_get("/fapi/v2/positionRisk", symbol=symbol)
                orders_task = _signed_get("/fapi/v1/openOrders", symbol=symbol)
                
                risk_data_list, orders_data = await asyncio.gather(risk_task, orders_task)
                
                # 2. 解析 positionRisk
                pos = None
                for p in risk_data_list:
                    if p.get("symbol") == symbol:
                        pos = p
                        break
                        
                if not pos:
                    # 如果没有数据，返回默认空状态
                    return PositionDetail(
                        symbol=symbol, direction="LONG", leverage=1.0, quantity=0.0,
                        entry_price=0.0, position_value=0.0, unrealized_pnl=0.0,
                        open_time=int(time.time() * 1000), status="CLOSED"
                    )
                    
                position_amt = float(pos.get("positionAmt", 0))
                direction = "LONG" if position_amt >= 0 else "SHORT"
                quantity = abs(position_amt)
                leverage = float(pos.get("leverage", 1.0))
                entry_price = float(pos.get("entryPrice", 0.0))
                unrealized_pnl = float(pos.get("unRealizedProfit", 0.0))
                position_value = quantity * entry_price
                open_time = int(pos.get("updateTime", time.time() * 1000))
                
                status = "OPEN" if quantity > 0 else "CLOSED"
                
                # 3. 解析 openOrders
                tp_price = None
                tp_order_id = None
                sl_price = None
                sl_order_id = None
                
                for order in orders_data:
                    order_type = order.get("origType", order.get("type", ""))
                    # Binance 的止损市价通常是 STOP_MARKET，止盈 TAKE_PROFIT_MARKET
                    if order_type in ("STOP_MARKET", "STOP"):
                        sl_price = float(order.get("stopPrice", 0.0))
                        sl_order_id = str(order.get("orderId", ""))
                    elif order_type in ("TAKE_PROFIT_MARKET", "TAKE_PROFIT"):
                        tp_price = float(order.get("stopPrice", 0.0))
                        tp_order_id = str(order.get("orderId", ""))
                        
                return PositionDetail(
                    symbol=symbol,
                    direction=direction,
                    leverage=leverage,
                    quantity=quantity,
                    entry_price=entry_price,
                    position_value=position_value,
                    unrealized_pnl=unrealized_pnl,
                    open_time=open_time,
                    status=status,
                    take_profit_price=tp_price,
                    take_profit_order_id=tp_order_id,
                    stop_loss_price=sl_price,
                    stop_loss_order_id=sl_order_id
                )
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Binance fetch_position_detail HTTP 异常：{e.response.status_code} - {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Binance fetch_position_detail 网络请求失败：{type(e).__name__} - {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Binance fetch_position_detail 未知错误：{type(e).__name__} - {str(e)}")
                raise
