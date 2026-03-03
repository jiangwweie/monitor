"""
打分策略工厂

纯领域层，提供 ScoringStrategyFactory 用于根据模式获取对应的策略实例。
"""
from typing import Dict, Type
from .scoring_strategy import (
    IScoreStrategy,
    ClassicScoreStrategy,
    ProgressiveScoreStrategy,
    CustomScoreStrategy
)


class ScoringStrategyFactory:
    """
    打分策略工厂类

    根据配置的模式返回对应的打分策略实例。
    支持动态注册新的策略。

    使用示例:
        strategy = ScoringStrategyFactory.get_strategy("classic")
        score, details = strategy.calculate(bar, ema60, atr14, is_long, config)
    """

    _strategies: Dict[str, Type[IScoreStrategy]] = {
        "classic": ClassicScoreStrategy,
        "progressive": ProgressiveScoreStrategy,
        "custom": CustomScoreStrategy,
    }

    @classmethod
    def get_strategy(cls, mode: str) -> IScoreStrategy:
        """
        根据模式获取对应的打分策略实例

        :param mode: 打分模式 ("classic" | "progressive" | "custom")
        :return: 策略实例
        :raises ValueError: 当模式不存在时
        """
        strategy_class = cls._strategies.get(mode.lower())
        if not strategy_class:
            available_modes = list(cls._strategies.keys())
            raise ValueError(
                f"未知的打分模式：{mode}，可用模式：{available_modes}"
            )
        return strategy_class()

    @classmethod
    def register_strategy(cls, mode: str, strategy_class: Type[IScoreStrategy]):
        """
        注册新的打分策略（供未来扩展）

        :param mode: 模式名称
        :param strategy_class: 策略类
        """
        cls._strategies[mode.lower()] = strategy_class

    @classmethod
    def get_available_modes(cls) -> list:
        """
        获取所有可用的打分模式

        :return: 模式列表
        """
        return list(cls._strategies.keys())
