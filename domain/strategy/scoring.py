"""
动态加权评分引擎 (Dynamic Scoring Engine)
用于计算 Pinbar 信号的完美度得分（0-100）。
此模块为纯领域层，仅负责纯数学逻辑运算，无任何副作用。
"""
from core.entities import Bar, ScoringWeights
from typing import Tuple, Dict

def calculate_dynamic_score(
    current_bar: Bar,
    ema60: float,
    atr14: float,
    is_long: bool,
    weights: ScoringWeights
) -> Tuple[int, Dict[str, float]]:
    """
    计算动态得分
    
    :param current_bar: 当前触发信号的 K 线
    :param ema60: 计算到该 K线 为止的 EMA60
    :param atr14: 计算到该 K线 为止的 ATR14
    :param is_long: 是否为做多方向
    :param weights: 打分权重实体 (包含 w_shape, w_trend, w_vol，和应为 1.0)
    :return: (总分 0-100, {各维度明细分 0-100})
    """
    body_length = abs(current_bar.open - current_bar.close)
    total_length = current_bar.high - current_bar.low

    if total_length == 0:
        return 0, {"shape": 0.0, "trend": 0.0, "vol": 0.0}

    # 1. 形态完美分 (S_shape): 0 ~ 100
    # 核心依据：有效影线占比越大，实体占比越小，形态越完美。
    if is_long:
        shadow_length = min(current_bar.open, current_bar.close) - current_bar.low
    else:
        shadow_length = current_bar.high - max(current_bar.open, current_bar.close)
        
    # 影线/总长 比例 (极大值接近1，极小值不低于约0.6根据策略前置过滤条件)
    # 将 0.6 作为及格线(0分)，0.9+ 作为满分(100分)
    shadow_ratio = shadow_length / total_length
    s_shape = min(100.0, max(0.0, (shadow_ratio - 0.6) / 0.3 * 100.0))

    # 2. 趋势回归分 (S_trend): 0 ~ 100
    # 核心依据：价格回调测试了 EMA60 但收盘被拒绝 (即收盘价离 EMA60 越近，或影线刺穿了 EMA60，得分越高)
    # 这里我们定义：收盘价距离 EMA60 刚好在 0.5% ~ 2% 之间最为健康，过远则趋于 0，刺穿反弹得分高。
    # 简单实现：极值点到 EMA60 的距离占比。如果极值点穿透了 EMA60 并且收回，给予高分。
    dist_to_ema = abs(current_bar.close - ema60) / ema60
    # 距离太远（>3%）得分低，距离极近（<0.5%）得分高
    s_trend = min(100.0, max(0.0, (0.03 - dist_to_ema) / 0.025 * 100.0))

    # 3. 波动爆发分 (S_vol): 0 ~ 100
    # 核心依据：当前波幅对比 ATR(14) 的健康度。倍数越高越表明发生了剧烈拒绝。
    # 策略前置条件是 > 1.2 * ATR。我们将 1.2 映射为 0 分，3.0 映射为 100 分。
    if atr14 > 0:
        vol_ratio = total_length / atr14
    else:
        vol_ratio = 1.2
    s_vol = min(100.0, max(0.0, (vol_ratio - 1.2) / 1.8 * 100.0))

    # 计算加权总分
    score_float = (
        s_shape * weights.w_shape +
        s_trend * weights.w_trend +
        s_vol * weights.w_vol
    )
    
    score = int(round(min(100, max(0, score_float))))
    
    details = {
        "shape": round(s_shape, 2),
        "trend": round(s_trend, 2),
        "vol": round(s_vol, 2)
    }

    return score, details
