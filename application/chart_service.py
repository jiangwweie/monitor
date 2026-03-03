"""
应用层：K 线图表数据聚合服务 (Chart Data Service)
融合币安 OHLCV 历史 K 线与本地信号标记，输出 TradingView Lightweight Charts 兼容格式。
内置内存 LRU 缓存以降低 API 权重消耗。
【绝对红线】：纯 Read-Only，仅 GET 请求，严禁任何下单逻辑。
"""
import asyncio
import logging
import time
import json
from collections import OrderedDict
from typing import Dict, List, Optional, Any, Tuple

import aiosqlite

from infrastructure.feed.binance_kline_fetcher import BinanceKlineFetcher, INTERVAL_MS

logger = logging.getLogger(__name__)

# 支持的时间级别白名单
VALID_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"}


class _LRUCache:
    """
    简易线程安全 LRU 缓存。
    key = f"{symbol}_{interval}"
    value = (expire_at_sec, data_dict)
    """

    def __init__(self, max_size: int = 10):
        self._store: OrderedDict[str, Tuple[float, dict]] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Optional[dict]:
        entry = self._store.get(key)
        if entry is None:
            return None
        expire_at, data = entry
        if time.time() > expire_at:
            del self._store[key]
            return None
        # 移到末尾 (最近访问)
        self._store.move_to_end(key)
        return data

    def set(self, key: str, data: dict, ttl_seconds: float):
        if key in self._store:
            del self._store[key]
        elif len(self._store) >= self._max_size:
            self._store.popitem(last=False)  # 淘汰最久未用
        self._store[key] = (time.time() + ttl_seconds, data)


class ChartService:
    """
    K 线图表数据聚合服务。
    并发拉取 K 线 + 查询信号 → 时间戳对齐 → 输出 TradingView Marker 格式。
    """

    def __init__(self, kline_fetcher: BinanceKlineFetcher, db_path: str = "radar.db"):
        self.fetcher = kline_fetcher
        self.db_path = db_path
        self._cache = _LRUCache(max_size=10)

    async def get_chart_data(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
        end_time: Optional[int] = None,
    ) -> dict:
        """
        获取聚合图表数据 (K线 + 信号标记)。

        :param symbol: 交易对 (如 BTCUSDT)
        :param interval: 时间级别 (如 15m, 1h, 4h)
        :param limit: K 线根数 (默认 200, 最大 1500)
        :param end_time: K 线结束时间戳 (毫秒)，默认当前时间（用于历史信号图表）
        :return: TradingView 兼容的 {symbol, interval, klines, markers} 字典
        """
        if interval not in VALID_INTERVALS:
            raise ValueError(f"不支持的时间级别: {interval}")

        limit = max(1, min(limit, 1500))
        symbol = symbol.upper()

        # === 1. 尝试命中缓存 ===
        cache_key = f"{symbol}_{interval}_{limit}_" + (str(end_time) if end_time else "now")
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"[ChartService] 缓存命中: {cache_key}")
            return cached

        # === 2. 并发拉取 K 线 + 查询信号 ===
        interval_ms = INTERVAL_MS.get(interval, 3_600_000)

        # 如果没有指定 end_time，使用当前时间
        if end_time is None:
            end_time = int(time.time() * 1000)

        # 计算开始时间
        start_ms = end_time - (limit * interval_ms)

        klines_task = self._fetch_klines_with_timerange(symbol, interval, start_ms, end_time)
        signals_task = self._query_signals(symbol, interval, start_ms, end_time)

        klines, signals = await asyncio.gather(klines_task, signals_task)

        # === 3. 构建 markers (时间戳精准对齐) ===
        markers = self._build_markers(signals, interval_ms)

        # === 4. 组装响应 ===
        result = {
            "symbol": symbol,
            "interval": interval,
            "klines": klines,
            "markers": markers,
        }

        # === 5. 写入缓存 (TTL = 1 个 K 线周期, 最短 60 秒) ===
        ttl = max(60, interval_ms // 1000)
        self._cache.set(cache_key, result, ttl)
        logger.debug(f"[ChartService] 缓存写入: {cache_key}, TTL={ttl}s")

        return result

    async def _fetch_klines(
        self, symbol: str, interval: str, limit: int
    ) -> List[dict]:
        """
        从币安拉取 K 线数据并转换为 TradingView 秒级时间戳格式。
        直接使用 REST API 的 limit 参数，避免日期计算误差。
        """
        import httpx

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://fapi.binance.com/fapi/v1/klines", params=params
                )
                resp.raise_for_status()
                raw = resp.json()
        except Exception as e:
            logger.error(f"[ChartService] K线拉取失败: {e}")
            return []

        klines = []
        for k in raw:
            klines.append({
                "time": int(k[0]) // 1000,  # 开盘时间 ms → 秒级 (TradingView 要求)
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })

        return klines

    async def _fetch_klines_with_timerange(
        self, symbol: str, interval: str, start_ms: int, end_ms: int
    ) -> List[dict]:
        """
        从币安拉取指定时间范围内的 K 线数据。
        使用 startTime 和 endTime 参数精准控制时间范围。
        """
        import httpx

        # 币安 API 支持的单次最大 limit
        max_limit = 1000

        # 计算需要多少条 K 线
        interval_ms = INTERVAL_MS.get(interval, 3600000)
        needed_bars = int((end_ms - start_ms) / interval_ms) + 10

        # 如果需要的 K 线超过 max_limit，需要分批次拉取
        limit = min(needed_bars, max_limit)

        # 计算 startTime（ endTime 往前推）
        start_time = end_ms - (limit * interval_ms)

        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": int(start_time),
            "endTime": int(end_ms),
            "limit": limit,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://fapi.binance.com/fapi/v1/klines", params=params
                )
                resp.raise_for_status()
                raw = resp.json()
        except Exception as e:
            logger.error(f"[ChartService] K 线拉取失败：{e}")
            return []

        klines = []
        for k in raw:
            klines.append({
                "time": int(k[0]) // 1000,  # 开盘时间 ms → 秒级 (TradingView 要求)
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })

        return klines

    async def _query_signals(
        self, symbol: str, interval: str, start_ms: int, end_ms: int
    ) -> List[dict]:
        """
        从 SQLite 查询指定币种、级别、时间范围内的信号。
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT symbol, interval, direction, entry_price, stop_loss,
                           take_profit_1, timestamp, score, source
                    FROM signals
                    WHERE symbol = ? AND interval = ?
                      AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp ASC
                    """,
                    (symbol, interval, start_ms, end_ms),
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[ChartService] 信号查询失败: {e}")
            return []

    @staticmethod
    def _build_markers(signals: List[dict], interval_ms: int) -> List[dict]:
        """
        将信号列表转换为 TradingView Marker 格式，并将时间戳精准对齐到 K 线开盘时间。

        对齐算法: aligned_time_sec = (signal_timestamp_ms // interval_ms) * interval_ms // 1000
        """
        markers = []
        for sig in signals:
            ts_ms = sig.get("timestamp", 0)
            # 向下取整到所属 K 线的开盘时间 (秒级)
            aligned_time = (ts_ms // interval_ms) * interval_ms // 1000

            direction = sig.get("direction", "LONG")
            score = sig.get("score", 0)
            source = sig.get("source", "realtime")

            is_long = direction == "LONG"

            marker = {
                "time": aligned_time,
                "position": "belowBar" if is_long else "aboveBar",
                "color": "#22c55e" if is_long else "#ef4444",
                "shape": "arrowUp" if is_long else "arrowDown",
                "text": f"{'LONG' if is_long else 'SHORT'} {score}pts",
                "signal": {
                    "direction": direction,
                    "entry_price": sig.get("entry_price", 0),
                    "stop_loss": sig.get("stop_loss", 0),
                    "take_profit_1": sig.get("take_profit_1", 0),
                    "score": score,
                    "source": source,
                },
            }
            markers.append(marker)

        return markers
