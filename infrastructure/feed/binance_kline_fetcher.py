"""
基础设施层：Binance 历史 K 线分片采集器
通过公开接口 GET /fapi/v1/klines 按日期分片拉取历史 K 线数据。
【绝对红线】：纯 Read-Only，仅使用 GET 请求，严禁任何下单逻辑。
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Callable, Optional

import httpx

from core.entities import Bar

logger = logging.getLogger(__name__)

# Binance 期货 klines 每次最多返回 1500 根
MAX_KLINES_PER_REQUEST = 1500

# 时间框架到毫秒的映射
INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
}

# 请求间隔 (秒)，避免瞬时高并发导致 API 权重报警
# 每个 klines 请求权重 = 5，Binance 限制 2400/分钟
# 0.2 秒间隔 → 每分钟 300 次 → 权重 1500，留有安全余量
REQUEST_DELAY_SECONDS = 0.2


class BinanceKlineFetcher:
    """
    高性能历史 K 线分片采集器。
    使用 Binance 公开 Futures API (无需签名) 按时间范围自动分批拉取。
    """

    def __init__(self, base_url: str = "https://fapi.binance.com"):
        self.base_url = base_url

    @staticmethod
    def _date_to_ms(date_str: str) -> int:
        """日期字符串 (YYYY-MM-DD) 转 UTC 毫秒时间戳"""
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    @staticmethod
    def _estimate_bar_count(start_ms: int, end_ms: int, interval: str) -> int:
        """根据时间范围和周期估算 K 线根数"""
        interval_ms = INTERVAL_MS.get(interval, 3_600_000)
        return max(1, (end_ms - start_ms) // interval_ms)

    async def fetch_history_klines(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> List[Bar]:
        """
        分片拉取指定日期范围内的历史 K 线。

        :param symbol: 交易对 (如 BTCUSDT)
        :param interval: 时间级别 (如 15m, 1h, 4h)
        :param start_date: 开始日期 YYYY-MM-DD
        :param end_date: 结束日期 YYYY-MM-DD (包含该日的 23:59)
        :param on_progress: 进度回调 (已拉取根数, 预估总根数)
        :return: Bar 列表 (按时间正序)
        """
        start_ms = self._date_to_ms(start_date)
        # end_date 包含当天全部 K 线，取次日 00:00 作为终止点
        end_ms = self._date_to_ms(end_date) + 86_400_000 - 1

        estimated_total = self._estimate_bar_count(start_ms, end_ms, interval)
        logger.info(
            f"[KlineFetcher] 开始分片拉取 {symbol} {interval} "
            f"from {start_date} to {end_date}, 预估 {estimated_total} 根K线"
        )

        all_bars: List[Bar] = []
        current_start = start_ms
        batch_count = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while current_start < end_ms:
                batch_count += 1

                params = {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "startTime": current_start,
                    "endTime": end_ms,
                    "limit": MAX_KLINES_PER_REQUEST,
                }

                try:
                    response = await client.get(
                        f"{self.base_url}/fapi/v1/klines", params=params
                    )
                    response.raise_for_status()
                    raw_klines = response.json()
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"[KlineFetcher] Binance API HTTP 错误 (batch {batch_count}): "
                        f"{e.response.status_code} - {e.response.text}"
                    )
                    raise
                except Exception as e:
                    logger.error(
                        f"[KlineFetcher] 网络请求失败 (batch {batch_count}): {e}"
                    )
                    raise

                if not raw_klines:
                    break

                for k in raw_klines:
                    # Binance klines 返回格式:
                    # [open_time, open, high, low, close, volume, close_time, ...]
                    bar = Bar(
                        symbol=symbol.upper(),
                        interval=interval,
                        timestamp=int(k[0]),
                        open=float(k[1]),
                        high=float(k[2]),
                        low=float(k[3]),
                        close=float(k[4]),
                        volume=float(k[5]),
                        is_closed=True,  # 历史 K 线全部已闭合
                    )
                    all_bars.append(bar)

                logger.debug(
                    f"[KlineFetcher] batch {batch_count}: 拉取到 {len(raw_klines)} 根, "
                    f"累计 {len(all_bars)} 根"
                )

                # 进度回调
                if on_progress:
                    on_progress(len(all_bars), estimated_total)

                # 移动到下一批的起始时间 (最后一根 K 线的开盘时间 + 1个周期)
                last_open_time = int(raw_klines[-1][0])
                interval_ms = INTERVAL_MS.get(interval, 3_600_000)
                current_start = last_open_time + interval_ms

                # 如果本批不足 MAX，说明已经是最后一批
                if len(raw_klines) < MAX_KLINES_PER_REQUEST:
                    break

                # 权重平衡延迟，防止瞬时并发超限
                await asyncio.sleep(REQUEST_DELAY_SECONDS)

        logger.info(
            f"[KlineFetcher] 采集完成: {symbol} {interval} "
            f"共 {len(all_bars)} 根K线, {batch_count} 个批次"
        )
        return all_bars
