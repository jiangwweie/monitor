"""
动态加权评分引擎 (Dynamic Scoring Engine)
用于计算 Pinbar 信号的完美度得分（0-100）。
此模块为纯领域层，仅负责纯数学逻辑运算，无任何副作用。

【v2.0 重构版本】
- 改为使用 ScoringStrategyFactory 调用策略实例
- 支持经典模式、累进模式、自定义模式
- 向后兼容：保留原有函数签名，内部委托给策略类
"""
from typing import Tuple, Dict
from core.entities import Bar, ScoringWeights
from .scoring_config import ScoringConfig
from .scoring_factory import ScoringStrategyFactory


def _convert_weights_to_config(
    weights: ScoringWeights,
    mode: str = "classic"
) -> ScoringConfig:
    """
    将旧的 ScoringWeights 转换为新的 ScoringConfig

    :param weights: 旧的权重实体
    :param mode: 打分模式
    :return: 新的 ScoringConfig 实例
    """
    return ScoringConfig(
        mode=mode,
        w_shape=weights.w_shape,
        w_trend=weights.w_trend,
        w_vol=weights.w_vol
    )


def calculate_dynamic_score(
    current_bar: Bar,
    ema60: float,
    atr14: float,
    is_long: bool,
    weights: ScoringWeights,
    config: ScoringConfig = None
) -> Tuple[int, Dict[str, float]]:
    """
    计算动态得分（支持多模式）

    向后兼容接口：保持原有函数签名，内部委托给策略工厂。
    如果传入了 ScoringConfig，则使用 config.mode 指定的策略。

    :param current_bar: 当前触发信号的 K 线
    :param ema60: 计算到该 K 线 为止的 EMA60
    :param atr14: 计算到该 K 线 为止的 ATR14
    :param is_long: 是否为做多方向
    :param weights: 打分权重实体 (包含 w_shape, w_trend, w_vol，和应为 1.0)
    :param config: 打分配置实体（可选，若为 None 则使用经典模式）
    :return: (总分 0-100, {各维度明细分 0-100})
    """
    # 确定使用哪个配置
    if config is None:
        config = _convert_weights_to_config(weights, mode="classic")
    else:
        # 如果传入了 config，使用 config 的权重覆盖
        pass

    # 通过工厂获取对应策略
    strategy = ScoringStrategyFactory.get_strategy(config.mode)

    # 调用策略计算分数
    return strategy.calculate(
        current_bar=current_bar,
        ema60=ema60,
        atr14=atr14,
        is_long=is_long,
        config=config
    )


def calculate_score_with_mode(
    current_bar: Bar,
    ema60: float,
    atr14: float,
    is_long: bool,
    config: ScoringConfig
) -> Tuple[int, Dict[str, float]]:
    """
    使用指定配置计算得分（推荐接口）

    这是新的推荐接口，显式传入 ScoringConfig 配置。

    :param current_bar: 当前触发信号的 K 线
    :param ema60: 计算到该 K 线 为止的 EMA60
    :param atr14: 计算到该 K 线 为止的 ATR14
    :param is_long: 是否为做多方向
    :param config: 打分配置实体
    :return: (总分 0-100, {各维度明细分 0-100})
    """
    strategy = ScoringStrategyFactory.get_strategy(config.mode)
    return strategy.calculate(
        current_bar=current_bar,
        ema60=ema60,
        atr14=atr14,
        is_long=is_long,
        config=config
    )
