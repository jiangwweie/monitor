"""
策略引擎模块 - Pinbar 形态决策
遵循纯净的领域驱动设计 (DDD)，严格隔离外部依赖，仅包含数学与业务规则计算。
所有外部数据及配置由调用者显式传入，保证无状态及 Testable。

【优化版本 v2.0】
- 方案一：软性过滤 (Soft Filter) - 级联拒绝改为评分累积
- 方案二：分级信号质量 (Signal Tiers) - A/B/C 三级分类
"""
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum

from core.entities import Bar, Signal, ScoringWeights, PinbarConfig
from .indicators import calculate_ema, calculate_atr
from .scoring import calculate_dynamic_score
from .scoring_config import ScoringConfig


class SignalTier(str, Enum):
    """信号质量分级"""
    A_CLASS = "A"  # 精品信号：各项指标优秀，推送 + 高亮
    B_CLASS = "B"  # 普通信号：达到基准要求，正常推送
    C_CLASS = "C"  # 观察信号：边缘但可记录，仅入库不推送
    REJECTED = "REJECTED"  # 拒绝：完全不满足条件


@dataclass
class ShapeMetrics:
    """形态度量结果"""
    body_length: float
    total_length: float
    body_ratio: float
    lower_shadow: float
    upper_shadow: float
    is_doji: bool
    effective_shadow_ratio: float
    valid_long_shape: bool
    valid_short_shape: bool
    is_long: Optional[bool]  # True=做多，False=做空，None=无明确方向


@dataclass
class FilterResults:
    """各层过滤结果"""
    shape_metrics: Optional[ShapeMetrics]
    shape_score: float  # 形态分 0-100
    trend_score: float  # 趋势分 0-100
    vol_score: float  # 波动分 0-100
    risk_penalty: float  # 风险扣分
    is_divergent: bool  # 形态 - 趋势背离
    is_contrarian: bool  # MTF 逆势
    sl_distance_pct: float
    actual_sl_distance: float
    quality_tier: SignalTier


class PinbarStrategy:
    """
    Pinbar + EMA60 结合 ATR 波幅过滤策略引擎。
    零执行 (Zero Execution)、零网络请求、零数据库读取的纯领域模型。

    优化特性：
    1. 十字星边界处理 - 识别 Doji 形态并放宽影线要求
    2. MTF 趋势过滤优化 - 软模式下降分而非直接拒绝
    3. 动态止损阈值 - 基于 ATR 波动率自适应调整
    4. 【新增】软性过滤 - 级联拒绝改为评分累积
    5. 【新增】信号分级 - A/B/C 三级质量分类
    """

    # 硬性拒绝的阈值（只有这些情况才直接返回 None）
    HARD_REJECT_BODY_RATIO = 0.50  # 实体超过 50% 直接拒绝
    HARD_REJECT_MIN_SCORE = 20  # 总分低于 20 直接拒绝

    def __init__(self, ema_period: int = 60, atr_period: int = 14):
        self.ema_period = ema_period
        self.atr_period = atr_period

    def evaluate(
        self,
        current_bar: Bar,
        history_bars: List[Bar],
        max_sl_dist: float,
        weights: ScoringWeights = None,
        higher_trend: Optional[str] = None,
        pinbar_config: PinbarConfig = None,
        scoring_config: ScoringConfig = None
    ) -> Optional[Signal]:
        """
        验证当前 K 线是否满足 Pinbar 交易策略要求。

        :param current_bar: 当前刚刚闭合的 K 线 (必须为 is_closed=True)
        :param history_bars: 截止到上一次的历史 K 线序列（不含 current_bar）
        :param max_sl_dist: 系统最大允许的止损距离百分比边界（进行天地针熔断）
        :param weights: 评分权重配置（Shape, Trend, Vol）- 向后兼容参数
        :param higher_trend: MTF 大级别趋势
        :param pinbar_config: Pinbar 形态识别动态参数 (若为 None 则使用默认值)
        :param scoring_config: 打分配置实体（v2.0 新增，若为 None 则使用 weights 经典模式）
        :return: 若符合买卖条件返回实例化后的 Signal 对象，否则返回 None。
        """
        if pinbar_config is None:
            pinbar_config = PinbarConfig()
        if not current_bar.is_closed:
            return None

        # 将历史与当前组装成完整序列以供计算连续指标
        all_bars = history_bars + [current_bar]

        # 验证是否有足够数据支持 EMA 和 ATR 计算
        if len(all_bars) < max(self.ema_period, self.atr_period + 1):
            return None

        closes = [b.close for b in all_bars]
        highs = [b.high for b in all_bars]
        lows = [b.low for b in all_bars]

        # 核心算力：获取到基于 current_bar 计算处的最终指标数值
        ema60 = calculate_ema(closes, self.ema_period)
        atr14 = calculate_atr(highs, lows, closes, self.atr_period)

        # ==========================================
        # 1. 形态识别 (Pinbar shape filter) - 改为评分式
        # ==========================================
        shape_metrics = self._evaluate_shape(current_bar, pinbar_config)

        # 硬性拒绝：实体过大，完全不像 Pinbar
        if shape_metrics.body_ratio > self.HARD_REJECT_BODY_RATIO:
            return None

        # 无明确方向的 K 线（上下影线都不满足最低要求）
        if not shape_metrics.valid_long_shape and not shape_metrics.valid_short_shape:
            # 检查是否接近临界点（允许边缘信号）
            if (shape_metrics.lower_shadow < shape_metrics.body_length * 0.5 and
                shape_metrics.upper_shadow < shape_metrics.body_length * 0.5):
                return None
            # 否则继续，让评分系统处理

        # 确定方向
        if shape_metrics.valid_long_shape and not shape_metrics.valid_short_shape:
            is_long = True
        elif shape_metrics.valid_short_shape and not shape_metrics.valid_long_shape:
            is_long = False
        elif shape_metrics.valid_long_shape and shape_metrics.valid_short_shape:
            # 如果上下影线都满足条件，取影线更长的一方为形态方向
            is_long = shape_metrics.lower_shadow > shape_metrics.upper_shadow
        else:
            # 边缘情况：尝试从微弱优势中确定方向
            if shape_metrics.lower_shadow > shape_metrics.upper_shadow:
                is_long = True
            elif shape_metrics.upper_shadow > shape_metrics.lower_shadow:
                is_long = False
            else:
                return None

        # 计算形态基础分
        shape_score = self._calculate_shape_score(shape_metrics, is_long)

        # ==========================================
        # 2. 趋势背离检测 (Trend filter) - 改为 soft 模式
        # ==========================================
        trend_score, is_divergent, is_contrarian = self._evaluate_trend(
            current_bar=current_bar,
            ema60=ema60,
            is_long=is_long,
            higher_trend=higher_trend,
            pinbar_config=pinbar_config
        )

        direction_str = "LONG" if is_long else "SHORT"

        # ==========================================
        # 3. 波动率与防守过滤 (Volatility filter) - 改为评分式
        # ==========================================
        vol_score = self._evaluate_volatility(
            total_length=shape_metrics.total_length,
            atr14=atr14,
            volatility_atr_multiplier=pinbar_config.volatility_atr_multiplier
        )

        # ==========================================
        # 4. 止损距离风控 (Risk filter) - 改为扣分式
        # ==========================================
        entry_price = current_bar.close
        stop_loss = current_bar.low if is_long else current_bar.high
        actual_sl_distance = abs(entry_price - stop_loss)
        sl_distance_pct = actual_sl_distance / entry_price if entry_price > 0 else 0

        # 动态止损阈值
        effective_max_sl_dist = self._calculate_dynamic_sl_threshold(
            atr14=atr14,
            entry_price=entry_price,
            base_max_sl_dist=max_sl_dist,
            config=pinbar_config
        )

        # 计算风险扣分（而非直接拒绝）
        risk_penalty = self._calculate_risk_penalty(
            sl_distance_pct=sl_distance_pct,
            effective_max_sl_dist=effective_max_sl_dist
        )

        # 硬性拒绝：止损距离过于极端（超过动态阈值的 2 倍）
        if sl_distance_pct > effective_max_sl_dist * 2:
            return None

        # ==========================================
        # 5. 止盈计算 (1.5R 盈亏比)
        # ==========================================
        if is_long:
            tp1 = entry_price + actual_sl_distance * 1.5
        else:
            tp1 = entry_price - actual_sl_distance * 1.5

        # ==========================================
        # 6. 动态评分计算 (Dynamic Scoring)
        # ==========================================
        score = 0
        details = {}
        if weights or scoring_config:
            score, details = calculate_dynamic_score(
                current_bar,
                ema60,
                atr14,
                is_long,
                weights=weights if weights else ScoringWeights(w_shape=0.4, w_trend=0.3, w_vol=0.3),
                config=scoring_config
            )

            # 形态背离扣分（使用配置中的值）
            if is_divergent:
                score -= pinbar_config.shape_divergence_penalty

            # MTF 逆势降分处理
            if is_contrarian:
                score -= 15

            score = max(0, int(round(score)))

        # ==========================================
        # 7. 信号质量分级 (Signal Tier Classification)
        # ==========================================
        quality_tier = self._determine_signal_tier(
            shape_metrics=shape_metrics,
            shape_score=shape_score,
            trend_score=trend_score,
            vol_score=vol_score,
            risk_penalty=risk_penalty,
            total_score=score,
            is_contrarian=is_contrarian,
            sl_distance_pct=sl_distance_pct
        )

        # 硬性拒绝：质量太差
        if quality_tier == SignalTier.REJECTED or score < self.HARD_REJECT_MIN_SCORE:
            return None

        # ==========================================
        # 8. 附加指标计算 (Additional Metrics)
        # ==========================================
        # shadow_ratio: 影线占比
        if shape_metrics.body_length == 0:
            shadow_ratio = 999.0
        else:
            if is_long:
                shadow_ratio = round((shape_metrics.lower_shadow / shape_metrics.body_length), 2)
            else:
                shadow_ratio = round((shape_metrics.upper_shadow / shape_metrics.body_length), 2)

        # ema_distance: 价格与 EMA60 的偏离比率 (%)
        if ema60 == 0:
            ema_distance = 0.0
        else:
            ema_distance = round((abs(entry_price - ema60) / ema60) * 100, 2)

        # volatility_atr: 当前 K 线总波幅 / 当期 ATR 倍数
        if atr14 == 0:
            volatility_atr = 0.0
        else:
            volatility_atr = round(shape_metrics.total_length / atr14, 2)

        # ==========================================
        # 9. 生成 Signal 对象
        # ==========================================
        return Signal(
            symbol=current_bar.symbol,
            interval=current_bar.interval,
            direction=direction_str,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            timestamp=current_bar.timestamp,
            reason="Pinbar+EMA60",
            sl_distance_pct=sl_distance_pct,
            score=score,
            score_details={
                **details,
                "quality_tier": quality_tier.value,
                "risk_penalty": round(risk_penalty, 2)
            },
            shadow_ratio=shadow_ratio,
            ema_distance=ema_distance,
            volatility_atr=volatility_atr,
            source="realtime",
            is_contrarian=is_contrarian,
            is_shape_divergent=is_divergent
        )

    def _evaluate_shape(self, current_bar: Bar, pinbar_config: PinbarConfig) -> ShapeMetrics:
        """
        评估 K 线形态，返回详细的形态度量数据。
        不再直接拒绝，而是收集所有度量数据供后续评分使用。
        """
        body_length = abs(current_bar.open - current_bar.close)
        total_length = current_bar.high - current_bar.low

        if total_length == 0:
            return ShapeMetrics(
                body_length=0, total_length=0, body_ratio=1.0,
                lower_shadow=0, upper_shadow=0, is_doji=False,
                effective_shadow_ratio=pinbar_config.shadow_min_ratio,
                valid_long_shape=False, valid_short_shape=False, is_long=None
            )

        body_ratio = body_length / total_length

        # Doji 判定
        is_doji = body_ratio < pinbar_config.doji_threshold

        # 影线比例放宽
        effective_shadow_ratio = (
            pinbar_config.shadow_min_ratio * pinbar_config.doji_shadow_bonus
            if is_doji
            else pinbar_config.shadow_min_ratio
        )

        lower_shadow = min(current_bar.open, current_bar.close) - current_bar.low
        upper_shadow = current_bar.high - max(current_bar.open, current_bar.close)

        # 放宽验证阈值，允许边缘信号进入评分系统
        relaxed_ratio = effective_shadow_ratio * 0.6  # 放宽到 60%
        valid_long_shape = lower_shadow >= body_length * relaxed_ratio
        valid_short_shape = upper_shadow >= body_length * relaxed_ratio

        return ShapeMetrics(
            body_length=body_length,
            total_length=total_length,
            body_ratio=body_ratio,
            lower_shadow=lower_shadow,
            upper_shadow=upper_shadow,
            is_doji=is_doji,
            effective_shadow_ratio=effective_shadow_ratio,
            valid_long_shape=valid_long_shape,
            valid_short_shape=valid_short_shape,
            is_long=None  # 由 evaluate 主函数确定
        )

    def _calculate_shape_score(
        self,
        metrics: ShapeMetrics,
        is_long: bool
    ) -> float:
        """
        计算形态完美分 (0-100)

        评估维度：
        1. 实体大小：越小分越高
        2. 影线长度：越长分越高
        3. 影线/总长比：越高形态越标准
        """
        if metrics.total_length == 0:
            return 0.0

        # 有效影线长度
        shadow_length = metrics.lower_shadow if is_long else metrics.upper_shadow

        # 影线/总长比 (0.6→0 分，0.9→100 分)
        shadow_to_total = shadow_length / metrics.total_length
        s_shadow = min(100.0, max(0.0, (shadow_to_total - 0.6) / 0.3 * 100.0))

        # 实体/总长比 (越小越好：0.1→100 分，0.5→0 分)
        body_to_total = metrics.body_ratio
        s_body = min(100.0, max(0.0, (0.5 - body_to_total) / 0.4 * 100.0))

        # 影线/实体比 (越高越好)
        if metrics.body_length > 0:
            shadow_to_body = shadow_length / metrics.body_length
            s_ratio = min(100.0, max(0.0, (shadow_to_body - 1.5) / 2.5 * 100.0))
        else:
            s_ratio = 100.0  # 十字星给高分

        # 综合得分
        shape_score = s_shadow * 0.4 + s_body * 0.3 + s_ratio * 0.3

        return round(shape_score, 2)

    def _evaluate_trend(
        self,
        current_bar: Bar,
        ema60: float,
        is_long: bool,
        higher_trend: Optional[str],
        pinbar_config: PinbarConfig
    ) -> Tuple[float, bool, bool]:
        """
        评估趋势维度，返回 (趋势分，是否形态背离，是否 MTF 逆势)

        改为 soft 模式：即使逆势也不直接拒绝，只是扣分
        """
        # 形态方向与 EMA 趋势的关系
        ema_trend_is_long = current_bar.close > ema60
        ema_trend_is_short = current_bar.close < ema60

        is_divergent = False
        if is_long and ema_trend_is_short:
            is_divergent = True
        elif (not is_long) and ema_trend_is_long:
            is_divergent = True
        elif current_bar.close == ema60:
            is_divergent = True

        # MTF 逆势检测
        direction_str = "LONG" if is_long else "SHORT"
        is_contrarian = False
        if higher_trend and direction_str != higher_trend:
            if pinbar_config.mtf_trend_filter_mode == "hard":
                # hard 模式下，逆势直接拒绝（保持原有行为）
                return 0.0, is_divergent, True
            else:
                # soft 模式：标记为逆势，后续扣分
                is_contrarian = True

        # 计算趋势分
        dist_to_ema = abs(current_bar.close - ema60) / ema60 if ema60 > 0 else 0

        # 顺势高分，逆势低分
        base_trend_score = min(100.0, max(0.0, (0.03 - dist_to_ema) / 0.025 * 100.0))

        # 背离扣分
        if is_divergent:
            base_trend_score -= 20

        # MTF 逆势扣分
        if is_contrarian:
            base_trend_score -= 15

        return max(0.0, base_trend_score), is_divergent, is_contrarian

    def _evaluate_volatility(
        self,
        total_length: float,
        atr14: float,
        volatility_atr_multiplier: float
    ) -> float:
        """
        评估波动率维度，返回波动分 (0-100)

        改为：不直接拒绝，而是给低分
        """
        if atr14 <= 0 or total_length <= 0:
            return 0.0

        vol_ratio = total_length / atr14

        # 1.2x→0 分，3.0x→100 分
        base_vol_score = min(100.0, max(0.0, (vol_ratio - 1.2) / 1.8 * 100.0))

        # 如果低于阈值，给予惩罚性低分，但不拒绝
        if vol_ratio < volatility_atr_multiplier:
            base_vol_score *= 0.3  # 压缩到 30%

        return round(base_vol_score, 2)

    def _calculate_risk_penalty(
        self,
        sl_distance_pct: float,
        effective_max_sl_dist: float
    ) -> float:
        """
        计算风险扣分

        止损距离超出阈值时，给予惩罚性扣分
        """
        if sl_distance_pct <= effective_max_sl_dist:
            return 0.0  # 在安全范围内，不扣分

        # 超出部分计算扣分
        excess_ratio = sl_distance_pct / effective_max_sl_dist
        if excess_ratio <= 1.2:
            return (excess_ratio - 1.0) * 50  # 超出 0-20%，扣 0-10 分
        elif excess_ratio <= 1.5:
            return 10 + (excess_ratio - 1.2) * 100  # 超出 20-50%，扣 10-40 分
        else:
            return 40 + (excess_ratio - 1.5) * 120  # 超出 50% 以上，额外重罚

    def _calculate_dynamic_sl_threshold(
        self,
        atr14: float,
        entry_price: float,
        base_max_sl_dist: float,
        config: PinbarConfig
    ) -> float:
        """
        【优化 3】计算动态止损阈值

        公式：dynamic_sl = base_sl + (atr14 / entry_price) * atr_multiplier

        :param atr14: 当前 ATR(14) 值
        :param entry_price: 入场价格
        :param base_max_sl_dist: 基础最大止损距离 (如 3.5%)
        :param config: Pinbar 配置
        :return: 动态调整后的止损阈值
        """
        if not config.dynamic_sl_enabled:
            return base_max_sl_dist

        if entry_price == 0 or atr14 == 0:
            return base_max_sl_dist

        # ATR 引起的波动率贡献
        atr_volatility = atr14 / entry_price

        # 动态调整：基础值 + ATR 波动率贡献
        # 高波动时放大止损阈值，低波动时收紧
        dynamic_sl = config.dynamic_sl_base + (atr_volatility * config.dynamic_sl_atr_multiplier)

        # 使用 base_max_sl_dist 作为上限保护
        return min(dynamic_sl, base_max_sl_dist * 1.5)  # 最多放宽到 1.5 倍

    def _determine_signal_tier(
        self,
        shape_metrics: ShapeMetrics,
        shape_score: float,
        trend_score: float,
        vol_score: float,
        risk_penalty: float,
        total_score: int,
        is_contrarian: bool,
        sl_distance_pct: float
    ) -> SignalTier:
        """
        根据各项指标决定信号等级

        A 级：精品信号 - 各项指标优秀，值得推送 + 高亮
        B 级：普通信号 - 达到基准要求，正常推送
        C 级：观察信号 - 边缘但可记录，仅入库不推送
        """
        # C 级最低要求
        if (shape_metrics.body_ratio <= 0.40 and
            shape_score >= 30 and
            total_score >= 30 and
            risk_penalty <= 20):

            # B 级要求
            if (shape_metrics.body_ratio <= 0.30 and
                shape_score >= 50 and
                trend_score >= 40 and
                vol_score >= 40 and
                risk_penalty <= 10 and
                not is_contrarian):

                # A 级要求
                if (shape_metrics.body_ratio <= 0.20 and
                    shape_score >= 70 and
                    trend_score >= 60 and
                    vol_score >= 60 and
                    total_score >= 70 and
                    risk_penalty == 0 and
                    not is_contrarian):
                    return SignalTier.A_CLASS

                return SignalTier.B_CLASS

            return SignalTier.C_CLASS

        return SignalTier.REJECTED
