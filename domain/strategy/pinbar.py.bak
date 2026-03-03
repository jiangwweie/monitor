"""
策略引擎模块 - Pinbar 形态决策
遵循纯净的领域驱动设计 (DDD)，严格隔离外部依赖，仅包含数学与业务规则计算。
所有外部数据及配置由调用者显式传入，保证无状态及 Testable。
"""
from typing import List, Optional, Tuple

from core.entities import Bar, Signal, ScoringWeights, PinbarConfig
from .indicators import calculate_ema, calculate_atr
from .scoring import calculate_dynamic_score

class PinbarStrategy:
    """
    Pinbar + EMA60 结合 ATR 波幅过滤策略引擎。
    零执行 (Zero Execution)、零网络请求、零数据库读取的纯领域模型。

    优化特性：
    1. 十字星边界处理 - 识别 Doji 形态并放宽影线要求
    2. MTF 趋势过滤优化 - 软模式下降分而非直接拒绝
    3. 动态止损阈值 - 基于 ATR 波动率自适应调整
    """
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
        pinbar_config: PinbarConfig = None
    ) -> Optional[Signal]:
        """
        验证当前 K 线是否满足 Pinbar 交易策略要求。

        :param current_bar: 当前刚刚闭合的 K 线 (必须为 is_closed=True)
        :param history_bars: 截止到上一次的历史 K 线序列（不含 current_bar）
        :param max_sl_dist: 系统最大允许的止损距离百分比边界（进行天地针熔断）
        :param weights: 评分权重配置（Shape, Trend, Vol）
        :param higher_trend: MTF 大级别趋势
        :param pinbar_config: Pinbar 形态识别动态参数 (若为 None 则使用默认值)
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
        # 1. 形态识别 (Pinbar shape filter) - 将趋势与形态解耦
        # ==========================================
        body_length = abs(current_bar.open - current_bar.close)
        total_length = current_bar.high - current_bar.low

        if total_length == 0:
            return None

        # 实体比例限制：K 线实体长度 <= K 线总长度的设定比例 (默认 25%)
        if body_length > total_length * pinbar_config.body_max_ratio:
            return None

        # 【优化 1】十字星 (Doji) 边界处理
        # 当实体极小时 (实体/全长 < 5%)，视为十字星，放宽影线比例要求
        body_ratio = body_length / total_length if total_length > 0 else 1
        is_doji = body_ratio < pinbar_config.doji_threshold

        # 十字星享有影线比例放宽优惠 (2.5 倍 → 1.5 倍)
        effective_shadow_ratio = (
            pinbar_config.shadow_min_ratio * pinbar_config.doji_shadow_bonus
            if is_doji
            else pinbar_config.shadow_min_ratio
        )

        lower_shadow = min(current_bar.open, current_bar.close) - current_bar.low
        upper_shadow = current_bar.high - max(current_bar.open, current_bar.close)

        valid_long_shape = lower_shadow >= body_length * effective_shadow_ratio
        valid_short_shape = upper_shadow >= body_length * effective_shadow_ratio

        if valid_long_shape and not valid_short_shape:
            is_long = True
        elif valid_short_shape and not valid_long_shape:
            is_long = False
        elif valid_long_shape and valid_short_shape:
            # 如果上下影线都满足条件，取影线更长的一方为形态方向
            is_long = lower_shadow > upper_shadow
        else:
            return None

        # ==========================================
        # 2. 趋势背离检测 (Trend filter)
        # ==========================================
        ema_trend_is_long = current_bar.close > ema60
        ema_trend_is_short = current_bar.close < ema60

        is_shape_divergent = False
        if is_long and ema_trend_is_short:
            is_shape_divergent = True
        elif (not is_long) and ema_trend_is_long:
            is_shape_divergent = True
        elif current_bar.close == ema60:
            is_shape_divergent = True

        direction_str = "LONG" if is_long else "SHORT"

        # [MTF 约束优化]:
        # - hard 模式：逆势信号直接拒绝（原有逻辑）
        # - soft 模式：允许逆势信号，但会在评分时降分处理
        mtf_contrarian = False
        if higher_trend:
            if direction_str != higher_trend:
                if pinbar_config.mtf_trend_filter_mode == "hard":
                    return None
                else:
                    # soft 模式：标记为逆势，后续评分降分
                    mtf_contrarian = True

        # ==========================================
        # 3. 波动率与防守过滤 (Volatility filter)
        # ==========================================
        # 活跃度验证：避免在死水/震荡期识别出无意义的小级别 Pinbar
        if total_length <= pinbar_config.volatility_atr_multiplier * atr14:
            return None

        entry_price = current_bar.close

        # 点位计算：该 Pinbar 的极值点
        if is_long:
            stop_loss = current_bar.low
        else:
            stop_loss = current_bar.high

        if entry_price == 0:
            return None

        # 真实的止损距离及其百分比，用于精确风控与算仓
        actual_sl_distance = abs(entry_price - stop_loss)
        sl_distance_pct = actual_sl_distance / entry_price

        # 【优化 3】动态止损阈值 - 基于 ATR 波动率自适应调整
        effective_max_sl_dist = self._calculate_dynamic_sl_threshold(
            atr14=atr14,
            entry_price=entry_price,
            base_max_sl_dist=max_sl_dist,
            config=pinbar_config
        )

        # 天地针熔断：判定止损距离是不是超过了系统的安全风险承受底线
        if sl_distance_pct > effective_max_sl_dist:
            return None

        # ==========================================
        # 4. 止盈点拨计算 (Takes Profit)
        # ==========================================
        # 严格按照正盈亏比进行 1.5R 测算
        if is_long:
            tp1 = entry_price + actual_sl_distance * 1.5
        else:
            tp1 = entry_price - actual_sl_distance * 1.5

        # ==========================================
        # 5. 动态打分计算 (Dynamic Scoring)
        # ==========================================
        score = 0
        details = {}
        if weights:
            score, details = calculate_dynamic_score(
                current_bar,
                ema60,
                atr14,
                is_long,
                weights
            )

            # 形态背离扣分
            if is_shape_divergent:
                score -= pinbar_config.shape_divergence_penalty

            # [MTF 优化] 逆势信号降分处理 (扣 15 分)
            if mtf_contrarian:
                score -= 15

            score = max(0, score)

        # ==========================================
        # 6. 附加指标计算 (Additional Metrics)
        # ==========================================
        # shadow_ratio: 影线占比 (主交易方向上的影线长度 / 实体长度)
        if body_length == 0:
            shadow_ratio = 999.0
        else:
            if is_long:
                shadow_ratio = round(((min(current_bar.open, current_bar.close) - current_bar.low) / body_length), 2)
            else:
                shadow_ratio = round(((current_bar.high - max(current_bar.open, current_bar.close)) / body_length), 2)

        # ema_distance: 价格与 EMA60 的偏离比率 (%)
        if ema60 == 0:
            ema_distance = 0.0
        else:
            ema_distance = round((abs(entry_price - ema60) / ema60) * 100, 2)

        # volatility_atr: 当前 K 线总波幅 / 当期 ATR 倍数
        if atr14 == 0:
            volatility_atr = 0.0
        else:
            volatility_atr = round(total_length / atr14, 2)

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
            score_details=details,
            shadow_ratio=shadow_ratio,
            ema_distance=ema_distance,
            volatility_atr=volatility_atr,
            is_contrarian=mtf_contrarian,
            is_shape_divergent=is_shape_divergent
        )

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
