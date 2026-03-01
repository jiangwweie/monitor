"""
策略引擎模块 - Pinbar 形态决策
遵循纯净的领域驱动设计 (DDD)，严格隔离外部依赖，仅包含数学与业务规则计算。
所有外部数据及配置由调用者显式传入，保证无状态及 Testable。
"""
from typing import List, Optional

from core.entities import Bar, Signal, ScoringWeights, PinbarConfig
from .indicators import calculate_ema, calculate_atr
from .scoring import calculate_dynamic_score

class PinbarStrategy:
    """
    Pinbar + EMA60 结合 ATR 波幅过滤策略引擎。
    零执行 (Zero Execution)、零网络请求、零数据库读取的纯领域模型。
    """
    def __init__(self, ema_period: int = 60, atr_period: int = 14):
        self.ema_period = ema_period
        self.atr_period = atr_period

    def evaluate(self, current_bar: Bar, history_bars: List[Bar], max_sl_dist: float, weights: ScoringWeights = None, higher_trend: Optional[str] = None, pinbar_config: PinbarConfig = None) -> Optional[Signal]:
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
        # 1. 趋势过滤 (Trend filter)
        # ==========================================
        is_long = current_bar.close > ema60
        is_short = current_bar.close < ema60
        
        # 收盘价等于 EMA60 时不构成有效单向顺势，过滤
        if not (is_long or is_short):
            return None
            
        direction_str = "LONG" if is_long else "SHORT"

        # [MTF 约束]: 假如引擎传入了高级别趋势 (higher_trend)，则当前信号的方向必须顺应高级别趋势。
        # 否则该信号直接因逆势结构被滤除。
        if higher_trend and direction_str != higher_trend:
            return None

        # ==========================================
        # 2. 形态识别 (Pinbar shape filter)
        # 核心逻辑：K线实体必须极小，而一侧的影线必须极长，形成对该方向的强力“拒绝”信号。
        # ==========================================
        body_length = abs(current_bar.open - current_bar.close)
        total_length = current_bar.high - current_bar.low

        if total_length == 0:
            return None

        # 实体比例限制：K线实体长度 <= K线总长度的设定比例 (默认 25%)
        if body_length > total_length * pinbar_config.body_max_ratio:
            return None

        # 影线比例要求：长影线代表了价格在该区域遭到了强烈的买盘或卖盘狙击。
        # 具体要求：有效影线长度必须 >= 实体长度的设定倍数 (默认 2.5 倍)
        if is_long:
            # 顺势看多：看下影线的支撑衰竭度
            lower_shadow = min(current_bar.open, current_bar.close) - current_bar.low
            if lower_shadow < body_length * pinbar_config.shadow_min_ratio:
                return None
        else:
            # 顺势看空：看上影线的阻力拒绝度
            upper_shadow = current_bar.high - max(current_bar.open, current_bar.close)
            if upper_shadow < body_length * pinbar_config.shadow_min_ratio:
                return None

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
        # 比近似估算 (High-Low) 更加精确
        actual_sl_distance = abs(entry_price - stop_loss)
        sl_distance_pct = actual_sl_distance / entry_price

        # 天地针熔断：判定止损距离是不是超过了系统的安全风险承受底线
        if sl_distance_pct > max_sl_dist:
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

        # ==========================================
        # 6. 附加指标计算 (Additional Metrics)
        # 这部分指标主要用于前端界面的展示和分析，并不一定直接决定买卖。
        # ==========================================
        # shadow_ratio: 影线占比 (主交易方向上的影线长度 / 实体长度)
        # 当实体越小，影线越长，该比例越大，形态越“完美”。必须防备分母为 0 的情况。
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
            volatility_atr=volatility_atr
        )
