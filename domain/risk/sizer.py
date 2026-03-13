"""
风控算仓大脑模块 (Domain 层)
严格按照 PRD 计算风险敞口、分配开仓本金并推算安全杠杆与开仓数量。
此模块为纯数学运算，没有任何网络请求或实际下单动作！
"""
from decimal import Decimal, ROUND_HALF_UP
from core.entities import Signal, AccountBalance, PositionSizing, RiskConfig
from core.exceptions import RiskLimitExceeded

# 常量：仓位价值比例上限（名义价值不超过账户总额的倍数）
# 已迁移至 RiskConfig.max_position_value_ratio，此常量保留作为向后兼容的 fallback
DEFAULT_MAX_POSITION_VALUE_RATIO = Decimal("20.0")


class PositionSizer:
    """风控仓位计算器
    严格遵守 Zero Execution 的红线规则。仅用于推算开仓建议，保护本金安全。
    """

    def calculate(
        self,
        signal: Signal,
        account: AccountBalance,
        risk_config: RiskConfig
    ) -> PositionSizing:
        """
        根据当前账户快照和风控配置对有效信号进行杠杆和算仓建议计算。

        :param signal: 策略引擎生成的有效信号快照
        :param account: 从交易所实时只读获取到的账户余额与持仓笔数
        :param risk_config: 风控配置参数
        :return: 推算出的包含杠杆及数量的 PositionSizing 实体。
        :raises RiskLimitExceeded: 在前置拦截条件不满足时抛出异常。
        """

        # ==========================================
        # 0. 参数有效性校验 (Input Validation)
        # ==========================================
        # 校验风险比例是否在合理范围内 (0, 10%]
        if not (0 < risk_config.risk_pct <= 0.1):
            raise RiskLimitExceeded(
                "单笔风险比例必须在 (0, 10%] 范围内",
                error_code="INVALID_RISK_PCT",
                context={"risk_pct": risk_config.risk_pct}
            )

        # 校验杠杆倍数是否在合理范围内 [1, 125]
        if not (1 <= risk_config.max_leverage <= 125):
            raise RiskLimitExceeded(
                "杠杆倍数必须在 [1, 125] 范围内",
                error_code="INVALID_LEVERAGE",
                context={"max_leverage": risk_config.max_leverage}
            )

        # ==========================================
        # 1. 前置拦截规则 (Pre-flight checks)
        # ==========================================
        # 拦截：当前持仓笔数 >= max_positions 时，不可再开新仓
        if account.current_positions_count >= risk_config.max_positions:
            raise RiskLimitExceeded(
                f"当前持仓笔数已达上限 ({account.current_positions_count}>={risk_config.max_positions})，禁止新开仓",
                error_code="POSITION_LIMIT_EXCEEDED",
                context={
                    "current_positions": account.current_positions_count,
                    "max_positions": risk_config.max_positions
                }
            )

        # 为了避免全仓余额被零除，做一道基本安全拦截
        if account.total_wallet_balance <= 0 or account.available_balance <= 0:
            raise RiskLimitExceeded(
                "账户余额不足或已穿仓",
                error_code="INSUFFICIENT_BALANCE",
                context={
                    "total_wallet_balance": account.total_wallet_balance,
                    "available_balance": account.available_balance
                }
            )

        # ==========================================
        # 2. 本金分配计算 (Capital Allocation) - 使用 Decimal 保证精度
        # ==========================================
        wallet_balance = Decimal(str(account.total_wallet_balance))
        available_balance = Decimal(str(account.available_balance))
        entry_price = Decimal(str(signal.entry_price))
        sl_distance_pct = Decimal(str(signal.sl_distance_pct))
        risk_pct = Decimal(str(risk_config.risk_pct))
        max_leverage = Decimal(str(risk_config.max_leverage))

        # 固定比例分配：根据 max_positions 平均分配，每笔最多占用 1/max_positions 资金
        max_position_ratio = Decimal("1") / Decimal(str(risk_config.max_positions))
        max_investment = wallet_balance * max_position_ratio
        investment_amount = min(max_investment, available_balance)

        # ==========================================
        # 3. 风险及止损测算 (Risk Assessment) - 使用 Decimal 保证精度
        # ==========================================
        # 单笔允许承受的绝对风险金额 = 钱包总额 * 单笔配置风险比率
        original_risk_amount = wallet_balance * risk_pct

        # 校验：这笔信号传来的止损百分比是否正常
        if signal.sl_distance_pct <= 0:
            raise RiskLimitExceeded(
                "信号自带的止损百分比距离无效或小于零",
                error_code="INVALID_SL_DISTANCE",
                context={"sl_distance_pct": signal.sl_distance_pct}
            )

        # ==========================================
        # 4. 计算仓位与杠杆 (Position & Leverage Calculation) - 使用 Decimal 保证精度
        # ==========================================
        # 计算理论应开名义价值 (Notional Value) = 单笔风险金额 / 止损距离比例
        notional_value = original_risk_amount / sl_distance_pct

        # 仓位价值比例校验：名义价值不超过账户总额的 max_position_value_ratio 倍
        # 从 risk_config 读取配置，如果没有则使用默认 fallback 值
        max_position_value_ratio = Decimal(str(risk_config.max_position_value_ratio)) if hasattr(risk_config, 'max_position_value_ratio') and risk_config.max_position_value_ratio else DEFAULT_MAX_POSITION_VALUE_RATIO
        max_allowed_notional = wallet_balance * max_position_value_ratio
        if notional_value > max_allowed_notional:
            raise RiskLimitExceeded(
                f"仓位价值比例超限：名义价值 ({float(notional_value):.2f}) 超过账户总额 ({float(wallet_balance):.2f}) 的 {float(max_position_value_ratio)} 倍",
                error_code="POSITION_VALUE_RATIO_EXCEEDED",
                context={
                    "notional_value": float(notional_value),
                    "wallet_balance": float(wallet_balance),
                    "max_allowed_ratio": float(max_position_value_ratio)
                }
            )

        # 开仓数量 = 理论名义价值 / 当前价格
        suggested_quantity = notional_value / entry_price

        # 计算理论需要开出的杠杆：名义价值 / (可用投资本金额 * 安全垫系数)
        # 安全垫系数 1.15 表示预留 15% 的安全边际，防止维持保证金和强平平推穿仓费率导致没止损就爆了
        safety_cushion = Decimal("1.15")
        theoretical_leverage = notional_value / (investment_amount * safety_cushion)

        # ==========================================
        # 5. 杠杆熔断自适应 (Leverage Cap & Auto-Scaling)
        # ==========================================
        suggested_leverage = theoretical_leverage
        actual_risk_amount = original_risk_amount
        leverage_capped = False

        # 熔断截断：当算出来的危险推算杠杆大大超出熔断线的时候
        if suggested_leverage > max_leverage:
            # 标记已触发杠杆熔断
            leverage_capped = True

            # 强制压制为系统顶格杠杆
            suggested_leverage = max_leverage

            # 对应只能同比例压制仓位
            # 反推出被压缩后的理论开仓的实际价值（不再除以安全垫，因为杠杆已封顶）
            capped_notional_value = investment_amount * max_leverage

            # 使用这笔实际价值反推压缩后的开仓数量
            suggested_quantity = capped_notional_value / entry_price

            # 同时由于本金、杠杆都被压缩，这笔单子的理论风险敞口实际降低了
            # 实际风险额 = 压缩后的名义价值 * 止损距离
            actual_risk_amount = capped_notional_value * sl_distance_pct

        # ==========================================
        # 6. 生成安全算仓结果并返回 - 转换回 float 保持接口兼容
        # ==========================================
        # 保留 6 位小数精度
        def to_float(d: Decimal) -> float:
            return float(d.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))

        return PositionSizing(
            signal=signal,
            suggested_leverage=to_float(suggested_leverage),
            suggested_quantity=to_float(suggested_quantity),
            investment_amount=to_float(investment_amount),
            risk_amount=to_float(original_risk_amount),
            actual_risk_amount=to_float(actual_risk_amount),
            leverage_capped=leverage_capped
        )
