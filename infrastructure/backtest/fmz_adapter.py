"""
FMZ 数据适配器模块

提供 FMZ 框架与 Monitor 系统之间的数据格式转换。
FMZ GetRecords() 返回的字典数组 <-> Monitor Bar 实体数组
"""
from typing import List, Dict
from core.entities import Bar


def fmz_records_to_bars(
    records: List[Dict],
    symbol: str,
    interval: str,
    is_closed: bool = True
) -> List[Bar]:
    """
    将 FMZ GetRecords() 返回的数据转换为 Bar 实体列表

    :param records: FMZ K 线数据列表，每个元素为字典：
                    {'Time': int, 'Open': float, 'High': float, 'Low': float, 'Close': float, 'Volume': float}
    :param symbol: 交易对 (如 "BTCUSDT")
    :param interval: 时间级别 (如 "1h", "15m")
    :param is_closed: K 线是否已闭合 (历史 K 线默认为 True)
    :return: Bar 实体列表
    """
    if not records:
        return []

    return [
        Bar(
            symbol=symbol,
            interval=interval,
            timestamp=r['Time'],
            open=r['Open'],
            high=r['High'],
            low=r['Low'],
            close=r['Close'],
            volume=r.get('Volume', 0.0),
            is_closed=is_closed
        )
        for r in records
    ]


def bar_to_fmz_record(bar: Bar) -> Dict:
    """
    将单个 Bar 实体转换为 FMZ 格式字典

    :param bar: Bar 实体
    :return: FMZ 格式字典 {'Time': int, 'Open': float, ...}
    """
    return {
        'Time': bar.timestamp,
        'Open': bar.open,
        'High': bar.high,
        'Low': bar.low,
        'Close': bar.close,
        'Volume': bar.volume
    }


def bars_to_fmz_records(bars: List[Bar]) -> List[Dict]:
    """
    将 Bar 实体列表转换为 FMZ 格式字典列表

    :param bars: Bar 实体列表
    :return: FMZ 格式字典列表
    """
    return [bar_to_fmz_record(bar) for bar in bars]
