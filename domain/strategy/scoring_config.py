"""
打分配置实体模块

纯领域层，仅使用标准库，提供 ScoringConfig 数据载体。
"""
from dataclasses import dataclass
from typing import Literal


@dataclass
class ScoringConfig:
    """
    打分配置实体 - 支持多模式

    所有参数可通过 /api/config/scoring 接口热配置，
    并持久化到 SQLite 数据库。

    约束：
    - w_shape + w_trend + w_vol = 1.0
    - 所有参数边界验证由 API 层 Pydantic 模型保证
    """

    # ================================
    # 模式选择
    # ================================
    mode: Literal["classic", "progressive", "custom"] = "classic"

    # ================================
    # 经典模式参数
    # ================================
    # 影线比例：0.6→0 分，0.9→100 分
    classic_shadow_min: float = 0.6
    classic_shadow_max: float = 0.9

    # 实体比例：0.1→100 分，0.5→0 分
    classic_body_good: float = 0.1
    classic_body_bad: float = 0.5

    # 波动率：1.2x→0 分，3.0x→100 分
    classic_vol_min: float = 1.2
    classic_vol_max: float = 3.0

    # 趋势距离：0%→100 分，3%→0 分
    classic_trend_max_dist: float = 0.03

    # ================================
    # 累进模式参数
    # ================================
    # 基础分上限（每个维度）
    progressive_base_cap: float = 30.0

    # 影线奖励：超过 0.6 后每 +0.1 奖励 2 分
    progressive_shadow_threshold: float = 0.6
    progressive_shadow_bonus_rate: float = 20.0

    # 实体奖励：<10% 时每 -0.01 奖励 1 分
    progressive_body_bonus_threshold: float = 0.1
    progressive_body_bonus_rate: float = 100.0

    # 十字星固定奖励
    progressive_doji_bonus: float = 5.0

    # 影线/实体比奖励：超过 3 倍后每 +1 奖励 2 分
    progressive_shadow_body_ratio_threshold: float = 3.0
    progressive_shadow_body_ratio_bonus: float = 2.0

    # 波动率奖励：超过 2x 后每 +0.1 奖励 1.5 分
    progressive_vol_threshold: float = 2.0
    progressive_vol_bonus_rate: float = 15.0

    # 极端波动奖励：超过 3x 额外奖励
    progressive_extreme_vol_threshold: float = 3.0
    progressive_extreme_vol_bonus: float = 10.0

    # 趋势穿透奖励
    progressive_penetration_rate: float = 30.0

    # ================================
    # 权重配置 (所有模式通用)
    # ================================
    w_shape: float = 0.4
    w_trend: float = 0.3
    w_vol: float = 0.3

    def __post_init__(self):
        """
        验证权重和必须等于 1.0

        :raises ValueError: 当权重总和不等于 1.0 时
        """
        total = round(self.w_shape + self.w_trend + self.w_vol, 4)
        if abs(total - 1.0) > 0.0001:
            raise ValueError(f"权重总和必须等于 1.0，当前为：{total}")
