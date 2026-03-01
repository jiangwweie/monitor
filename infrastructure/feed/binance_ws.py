"""
 Binance WebSocket 行情源适配器 (Infrastructure 层)
 纯粹监听来自币安 U本位合约的 K 线数据并转换成实体。
 无实际执行权限，只能读取并筛选已闭合的数据。
"""
import json
import logging
import asyncio
from typing import AsyncIterator, List

import websockets
from websockets.exceptions import ConnectionClosed

from core.entities import Bar
from core.interfaces import IDataFeed

logger = logging.getLogger(__name__)

class BinanceWSFeed(IDataFeed):
    """
    币安 WebSocket K 线数据源实现。
    由于长连接的不稳定性，实现了异常重连机制以达到 7x24 监听的需求。
    """
    def __init__(self, ws_url: str = "wss://fstream.binance.com/ws"):
        self.ws_url = ws_url

    async def subscribe_klines(self, symbols: List[str], intervals: List[str]) -> AsyncIterator[Bar]:
        """
        连接并订阅并返回 K 线流。
        自动处理断线重连。
        为支持多币种和多时间维度，采用 Binance Combined Streams 方式订阅所有组合。
        注意: 现在会 yield 所有 K 线（包括未闭合的）以作为连接心跳。
        """
        streams = []
        for sym in symbols:
            for ivl in intervals:
                streams.append(f"{sym.lower()}@kline_{ivl}")
        streams_path = "/".join(streams)
        
        # 组装 Combined Streams URL
        url = f"wss://fstream.binance.com/stream?streams={streams_path}"

        while True:
            try:
                logger.info(f"正在连接 Binance WebSocket (组合流): {url}")
                async with websockets.connect(url) as ws:
                    logger.info(f"已成功建立组合 websocket 连接: {streams_path}")

                    # 循环接收数据
                    async for msg in ws:
                        data = json.loads(msg)

                        # 组合流的 payload 含有 'stream' 和 'data' 外壳
                        if 'data' in data:
                            payload = data['data']
                            # 过滤并确认如果是事件推送 (e: event type) 为 kline，且包含了 k 字典 (K 线内容)才处理
                            if 'e' in payload and payload['e'] == 'kline' and 'k' in payload:
                                k_data = payload['k']
                                # 'x' 字段代表了这根 K 线在当前的周期(如1h)内是否已经走完并收盘。
                                # True 代表收盘(也就是一小时走完了)，这种数据才会触发核心策略运算
                                is_closed = k_data.get('x', False)

                                # 转换并装配成我们本地的实体 K 线对象，供外层的 Monitor Engine 消费
                                # 注意：这里既会返回闭合的，也会返回所有中间产生的心跳(即 x=False) K 线。
                                bar = Bar(
                                    symbol=k_data.get('s', ''),
                                    interval=k_data.get('i', ''), # 挂载从 payload 取出的 K 线级别
                                    timestamp=int(k_data.get('T', 0)),  # 闭合时间戳
                                    open=float(k_data.get('o', 0.0)),
                                    high=float(k_data.get('h', 0.0)),
                                    low=float(k_data.get('l', 0.0)),
                                    close=float(k_data.get('c', 0.0)),
                                    volume=float(k_data.get('v', 0.0)),
                                    is_closed=is_closed
                                )
                                yield bar
            except ConnectionClosed as e:
                logger.warning(f"Binance WebSocket 连接断开: {e}，将在 5 秒后重试...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Binance WebSocket 遇到未处理异常: {e}，将在 5 秒后重试...")
                await asyncio.sleep(5)
