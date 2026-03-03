"""
打分策略接口定义和实现

纯领域层，仅使用标准库，定义 IScoreStrategy 接口和三种策略实现。
"""
from abc import ABC, abstractmethod
from typing import Tuple, Dict
from core.entities import Bar


class IScoreStrategy(ABC):
    """
    打分策略接口

    所有打分策略必须实现此接口，提供统一的 calculate 方法。
    """

    @abstractmethod
    def calculate(
        self,
        current_bar: Bar,
        ema60: float,
        atr14: float,
        is_long: bool,
        config: "ScoringConfig"
    ) -> Tuple[int, Dict[str, float]]:
        """
        计算得分

        :param current_bar: 当前 K 线
        :param ema60: EMA60 值
        :param atr14: ATR14 值
        :param is_long: 是否为做多方向
        :param config: 打分配置
        :return: (总分 0-100, {shape: xx, trend: xx, vol: xx})
        """
        pass


class ClassicScoreStrategy(IScoreStrategy):
    """
    经典线性打分策略

    保持现有 calculate_dynamic_score 函数的逻辑，
    支持通过 ScoringConfig 动态配置参数。

    评分逻辑:
    1. 形态分：影线/总长比 (0.6→0, 0.9→100) + 实体/总长比 (0.1→100, 0.5→0)
    2. 趋势分：距离 EMA60 越近分越高 (0%→100, 3%→0)
    3. 波动分：K 线长度/ATR (1.2x→0, 3.0x→100)
    """

    def calculate(
        self,
        current_bar: Bar,
        ema60: float,
        atr14: float,
        is_long: bool,
        config: "ScoringConfig"
    ) -> Tuple[int, Dict[str, float]]:
        """
        经典模式打分实现

        :param current_bar: 当前 K 线
        :param ema60: EMA60 值
        :param atr14: ATR14 值
        :param is_long: 是否为做多方向
        :param config: 打分配置
        :return: (总分，各维度明细分)
        """
        body_length = abs(current_bar.open - current_bar.close)
        total_length = current_bar.high - current_bar.low

        if total_length == 0:
            return 0, {"shape": 0.0, "trend": 0.0, "vol": 0.0}

        # 有效影线长度
        if is_long:
            shadow_length = min(current_bar.open, current_bar.close) - current_bar.low
        else:
            shadow_length = current_bar.high - max(current_bar.open, current_bar.close)

        # === 1. 形态评分 ===
        shadow_ratio = shadow_length / total_length
        body_ratio = body_length / total_length

        # 影线/总长比 (config.classic_shadow_min→0, config.classic_shadow_max→100)
        s_shadow = min(100.0, max(0.0,
            (shadow_ratio - config.classic_shadow_min) /
            (config.classic_shadow_max - config.classic_shadow_min) * 100.0
        ))

        # 实体/总长比 (config.classic_body_good→100, config.classic_body_bad→0)
        s_body = min(100.0, max(0.0,
            (config.classic_body_bad - body_ratio) /
            (config.classic_body_bad - config.classic_body_good) * 100.0
        ))

        # 影线/实体比
        if body_length > 0:
            shadow_to_body = shadow_length / body_length
            s_ratio = min(100.0, max(0.0, (shadow_to_body - 1.5) / 2.5 * 100.0))
        else:
            s_ratio = 100.0  # 十字星给高分

        shape_score = s_shadow * 0.4 + s_body * 0.3 + s_ratio * 0.3

        # === 2. 趋势评分 ===
        dist_to_ema = abs(current_bar.close - ema60) / ema60 if ema60 > 0 else 0
        s_trend = min(100.0, max(0.0,
            (config.classic_trend_max_dist - dist_to_ema) /
            config.classic_trend_max_dist * 100.0
        ))

        # === 3. 波动评分 ===
        vol_ratio = total_length / atr14 if atr14 > 0 else config.classic_vol_min
        s_vol = min(100.0, max(0.0,
            (vol_ratio - config.classic_vol_min) /
            (config.classic_vol_max - config.classic_vol_min) * 100.0
        ))

        # === 4. 加权总分 ===
        score_float = (
            shape_score * config.w_shape +
            s_trend * config.w_trend +
            s_vol * config.w_vol
        )

        score = int(round(min(100, max(0, score_float))))

        details = {
            "shape": round(shape_score, 2),
            "trend": round(s_trend, 2),
            "vol": round(s_vol, 2)
        }

        return score, details


class ProgressiveScoreStrategy(IScoreStrategy):
    """
    累进加分策略

    评分逻辑：基础分 + 奖励分
    适用场景：需要区分信号质量，精品信号高亮

    每个维度:
    1. 基础分 (0-30): 满足基本条件即可获得
    2. 奖励分 (0-40): 根据优秀程度额外奖励
    """

    def calculate(
        self,
        current_bar: Bar,
        ema60: float,
        atr14: float,
        is_long: bool,
        config: "ScoringConfig"
    ) -> Tuple[int, Dict[str, float]]:
        """
        累进模式打分实现

        :param current_bar: 当前 K 线
        :param ema60: EMA60 值
        :param atr14: ATR14 值
        :param is_long: 是否为做多方向
        :param config: 打分配置
        :return: (总分，各维度明细分)
        """
        body_length = abs(current_bar.open - current_bar.close)
        total_length = current_bar.high - current_bar.low

        if total_length == 0:
            return 0, {"shape": 0.0, "trend": 0.0, "vol": 0.0}

        # 有效影线长度
        if is_long:
            shadow_length = min(current_bar.open, current_bar.close) - current_bar.low
        else:
            shadow_length = current_bar.high - max(current_bar.open, current_bar.close)

        body_ratio = body_length / total_length
        shadow_to_total = shadow_length / total_length

        # ================================
        # 1. 形态评分 (基础分 + 奖励分)
        # ================================

        # --- 基础分 (0-30) ---
        base_shape = 0.0

        # 实体占比 < config.classic_body_good 得满分
        if body_ratio < config.classic_body_good:
            base_shape += config.progressive_base_cap * 0.6
        else:
            base_shape += max(0, config.progressive_base_cap * 0.6 *
                (config.classic_body_bad - body_ratio) /
                (config.classic_body_bad - config.classic_body_good))

        # 影线占比 > config.progressive_shadow_threshold 得高分
        if shadow_to_total > config.progressive_shadow_threshold:
            base_shape += config.progressive_base_cap * 0.4
        else:
            base_shape += max(0, config.progressive_base_cap * 0.4 *
                shadow_to_total / config.progressive_shadow_threshold)

        base_shape = min(config.progressive_base_cap, base_shape)

        # --- 奖励分 (0-40) ---
        bonus_shape = 0.0

        # 影线长度奖励
        if shadow_to_total > config.progressive_shadow_threshold:
            bonus_shape += (shadow_to_total - config.progressive_shadow_threshold) * \
                config.progressive_shadow_bonus_rate

        # 实体极小奖励
        if body_ratio < config.progressive_body_bonus_threshold:
            bonus_shape += (config.progressive_body_bonus_threshold - body_ratio) * \
                config.progressive_body_bonus_rate

        # 十字星特别奖励
        if body_ratio < 0.05:
            bonus_shape += config.progressive_doji_bonus

        # 影线/实体比奖励
        if body_length > 0:
            shadow_to_body = shadow_length / body_length
            if shadow_to_body > config.progressive_shadow_body_ratio_threshold:
                bonus_shape += (shadow_to_body - config.progressive_shadow_body_ratio_threshold) * \
                    config.progressive_shadow_body_ratio_bonus

        shape_score = base_shape + min(40, bonus_shape)
        shape_score = min(100, shape_score)

        # ================================
        # 2. 趋势评分 (基础分 + 穿透奖励)
        # ================================

        dist_to_ema = abs(current_bar.close - ema60) / ema60 if ema60 > 0 else 0

        # --- 基础分 (0-30) ---
        base_trend = max(0, config.progressive_base_cap *
            (config.classic_trend_max_dist - dist_to_ema) /
            config.classic_trend_max_dist)
        base_trend = min(config.progressive_base_cap, base_trend)

        # --- 穿透奖励 (0-20) ---
        bonus_trend = 0.0

        if is_long:
            penetration = ema60 - current_bar.low
        else:
            penetration = current_bar.high - ema60

        if penetration > 0:
            penetration_ratio = penetration / total_length
            bonus_trend += penetration_ratio * config.progressive_penetration_rate
            bonus_trend = min(20, bonus_trend)

        trend_score = base_trend + bonus_trend
        trend_score = min(100, trend_score)

        # ================================
        # 3. 波动评分 (基础分 + 爆发奖励)
        # ================================

        vol_ratio = total_length / atr14 if atr14 > 0 else 0

        # --- 基础分 (0-30) ---
        base_vol = min(config.progressive_base_cap, max(0,
            config.progressive_base_cap *
            (vol_ratio - config.classic_vol_min) /
            (config.classic_vol_max - config.classic_vol_min)
        ))

        # --- 奖励分 (0-30) ---
        bonus_vol = 0.0

        if vol_ratio > config.progressive_vol_threshold:
            bonus_vol += (vol_ratio - config.progressive_vol_threshold) * \
                config.progressive_vol_bonus_rate

        if vol_ratio > config.progressive_extreme_vol_threshold:
            bonus_vol += config.progressive_extreme_vol_bonus

        # 低于阈值的惩罚
        if vol_ratio < config.classic_vol_min:
            base_vol *= 0.3

        vol_score = base_vol + min(30, bonus_vol)
        vol_score = min(100, vol_score)

        # ================================
        # 4. 加权总分
        # ================================
        score_float = (
            shape_score * config.w_shape +
            trend_score * config.w_trend +
            vol_score * config.w_vol
        )

        score = int(round(min(100, max(0, score_float))))

        details = {
            "shape": round(shape_score, 2),
            "trend": round(trend_score, 2),
            "vol": round(vol_score, 2)
        }

        return score, details


class CustomScoreStrategy(IScoreStrategy):
    """
    自定义公式策略（预留扩展点）

    当前版本暂时复用经典模式逻辑，未来可扩展为：
    - 用户自定义公式字符串解析执行
    - 机器学习模型打分
    """

    def calculate(
        self,
        current_bar: Bar,
        ema60: float,
        atr14: float,
        is_long: bool,
        config: "ScoringConfig"
    ) -> Tuple[int, Dict[str, float]]:
        """
        自定义模式打分实现（当前复用经典模式）

        :param current_bar: 当前 K 线
        :param ema60: EMA60 值
        :param atr14: ATR14 值
        :param is_long: 是否为做多方向
        :param config: 打分配置
        :return: (总分，各维度明细分)
        """
        # 暂时复用经典模式
        return ClassicScoreStrategy().calculate(
            current_bar, ema60, atr14, is_long, config
        )
