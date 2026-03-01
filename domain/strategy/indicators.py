"""
纯数学指标计算模块 (Domain 层)
包含指数移动平均 (EMA) 和真实波幅 (ATR) 的高效计算函数。
纯 Python 实现，无任何第三方包依赖。
"""
from typing import List

def calculate_ema(data: List[float], period: int) -> float:
    """
    计算指数移动平均 (EMA)
    
    :param data: 价格序列 (如收盘价)
    :param period: EMA 周期
    :return: 序列中最后一个时点对应的 EMA 值
    """
    if len(data) < period:
        return 0.0
    
    # 初始 EMA 设定为前 period 数据的 SMA (简单移动平均)
    ema = sum(data[:period]) / period
    multiplier = 2.0 / (period + 1.0)
    
    # 从第 period 个数据点开始迭代平滑计算 EMA
    for price in data[period:]:
        ema = (price - ema) * multiplier + ema
        
    return ema

def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """
    计算真实波幅 (ATR) - 遵循 Wilder's Smoothing Method (RMA)
    
    :param highs: 历史最高价序列
    :param lows: 历史最低价序列
    :param closes: 历史收盘价序列
    :param period: ATR 周期，默认 14
    :return: 序列中最后一个时点对应的 ATR 值
    """
    if len(highs) < period + 1:
        return 0.0
        
    true_ranges = []
    # 从索引 1 开始计算 TR
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        true_ranges.append(tr)
        
    # 首先使用前 period 周期的 SMA 作为 ATR 的初始值
    atr = sum(true_ranges[:period]) / period
    
    # 对之后的周期，运用类似 RMA (Running Moving Average) 的平滑进行迭代
    for i in range(period, len(true_ranges)):
        atr = (atr * (period - 1) + true_ranges[i]) / period
        
    return atr
