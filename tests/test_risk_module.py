"""
风控模块验收测试
验证所有 P0/P1/P2/P3 级别修复是否正确实施
"""
import pytest
from decimal import Decimal
from core.entities import Signal, AccountBalance, Position, RiskConfig
from core.exceptions import RiskLimitExceeded
from domain.risk.sizer import PositionSizer, MAX_POSITION_VALUE_RATIO
from domain.risk.portfolio_risk import PortfolioRiskService, PortfolioRiskMetrics


class TestP0_SafetyCushion:
    """P0-问题 3: 安全垫系数方向错误修复验证"""

    def test_safety_cushion_uses_division(self, risk_sizer, default_account, bullish_signal, default_risk_config):
        """验证安全垫使用除法而非乘法"""
        sizing = risk_sizer.calculate(
            signal=bullish_signal,
            account=default_account,
            risk_config=default_risk_config
        )

        # 名义价值 = 风险金额 / 止损距离 = 200 / 0.03 = 6666.67
        expected_notional = default_account.total_wallet_balance * default_risk_config.risk_pct / bullish_signal.sl_distance_pct

        # 理论杠杆 = 名义价值 / (投资金额 * 1.15)
        # 投资金额 = 10000 / 4 = 2500
        # 理论杠杆 = 6666.67 / (2500 * 1.15) = 6666.67 / 2875 = 2.32
        expected_leverage = expected_notional / (2500 * 1.15)

        # 验证杠杆计算正确（使用除法安全垫）
        assert abs(sizing.suggested_leverage - expected_leverage) < 0.1, \
            f"安全垫计算错误：期望{expected_leverage:.2f}, 实际{sizing.suggested_leverage:.2f}"

    def test_safety_cushion_factor_is_1_15(self, risk_sizer, default_account, bullish_signal, default_risk_config):
        """验证安全垫系数是 1.15 而非 1.05"""
        sizing = risk_sizer.calculate(
            signal=bullish_signal,
            account=default_account,
            risk_config=default_risk_config
        )

        # 通过计算反推安全垫系数
        investment = default_account.total_wallet_balance / default_risk_config.max_positions
        notional = default_account.total_wallet_balance * default_risk_config.risk_pct / bullish_signal.sl_distance_pct

        # 如果安全垫是 1.15，杠杆 = notional / (investment * 1.15)
        expected_leverage_with_1_15 = notional / (investment * 1.15)
        # 如果安全垫是 1.05，杠杆 = notional / (investment * 1.05)
        expected_leverage_with_1_05 = notional / (investment * 1.05)

        # 验证实际杠杆更接近 1.15 的计算结果
        diff_1_15 = abs(sizing.suggested_leverage - expected_leverage_with_1_15)
        diff_1_05 = abs(sizing.suggested_leverage - expected_leverage_with_1_05)

        assert diff_1_15 < diff_1_05, "安全垫系数不是 1.15"


class TestP0_RiskAmountAfterCap:
    """P0-问题 4: 杠杆熔断后风险金额计算修复验证"""

    def test_actual_risk_amount_preserved_when_capped(self, risk_sizer, default_account, default_risk_config):
        """验证杠杆熔断时 original_risk_amount 保持不变"""
        # 创建一个中等止损距离的信号 (2%)，不会触发仓位价值上限
        # 名义价值 = 200 / 0.02 = 10000，等于账户总额
        # 但投资金额只有 2500，理论杠杆 = 10000 / (2500 * 1.15) = 3.48
        # 设置 max_leverage=2.0 会触发熔断
        medium_signal = Signal(
            symbol="BTCUSDT",
            interval="1h",
            direction="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,  # 2% 止损
            take_profit_1=52000.0,
            timestamp=1709900000000,
            reason="中等 Pinbar",
            sl_distance_pct=0.02,  # 2% 止损距离
            score=75,
            quality_tier="B"
        )

        # 设置低杠杆上限强制触发熔断（但不触发仓位价值上限）
        low_leverage_config = RiskConfig(
            risk_pct=0.02,
            max_sl_dist=0.035,
            max_leverage=2.0,  # 很低的上限，理论杠杆 3.48 > 2.0
            max_positions=4
        )

        sizing = risk_sizer.calculate(
            signal=medium_signal,
            account=default_account,
            risk_config=low_leverage_config
        )

        # 验证杠杆被熔断
        assert sizing.leverage_capped is True, "杠杆应被熔断"
        assert sizing.suggested_leverage == 2.0, f"杠杆应被限制为 2.0, 实际{ sizing.suggested_leverage}"

        # 验证原始风险金额保持不变（200 USDT）
        expected_original_risk = default_account.total_wallet_balance * default_risk_config.risk_pct
        assert abs(sizing.risk_amount - expected_original_risk) < 0.01, \
            f"原始风险金额应保持不变：期望{expected_original_risk}, 实际{sizing.risk_amount}"

        # 验证实际风险金额被压缩
        assert sizing.actual_risk_amount < sizing.risk_amount, \
            "实际风险金额应小于原始风险金额（被压缩）"

    def test_no_cap_when_leverage_within_limit(self, risk_sizer, default_account, bullish_signal, default_risk_config):
        """验证未触发熔断时 actual_risk_amount 等于 risk_amount"""
        sizing = risk_sizer.calculate(
            signal=bullish_signal,
            account=default_account,
            risk_config=default_risk_config
        )

        # 验证未触发熔断
        assert sizing.leverage_capped is False

        # 验证两个风险金额相等
        assert abs(sizing.actual_risk_amount - sizing.risk_amount) < 0.01, \
            "未触发熔断时，实际风险金额应等于原始风险金额"


class TestP1_CapitalAllocation:
    """P1-问题 2: 资金分配逻辑修复验证"""

    def test_fixed_ratio_allocation(self, risk_sizer, default_account, bullish_signal, default_risk_config):
        """验证固定比例分配而非动态除数"""
        sizing = risk_sizer.calculate(
            signal=bullish_signal,
            account=default_account,
            risk_config=default_risk_config
        )

        # 固定比例分配：10000 / 4 = 2500
        expected_investment = default_account.total_wallet_balance / default_risk_config.max_positions

        assert abs(sizing.investment_amount - expected_investment) < 0.01, \
            f"投资金额应为{expected_investment}, 实际{sizing.investment_amount}"

    def test_allocation_respects_available_balance(self, risk_sizer, account_with_positions, bullish_signal, default_risk_config):
        """验证分配金额不超过可用余额"""
        # 账户有 3 个持仓，可用余额 7000
        # 固定比例分配：10000 / 4 = 2500，小于 7000，应取 2500
        sizing = risk_sizer.calculate(
            signal=bullish_signal,
            account=account_with_positions,
            risk_config=default_risk_config
        )

        expected_investment = min(
            account_with_positions.total_wallet_balance / default_risk_config.max_positions,
            account_with_positions.available_balance
        )

        assert abs(sizing.investment_amount - expected_investment) < 0.01

    def test_allocation_with_low_available_balance(self, risk_sizer, default_account, bullish_signal, default_risk_config):
        """验证当可用余额低于固定比例时，取可用余额"""
        # 修改账户可用余额低于固定比例
        low_balance_account = AccountBalance(
            total_wallet_balance=10000.0,
            available_balance=1000.0,  # 只有 1000 可用
            current_positions_count=0,
            positions=[]
        )

        sizing = risk_sizer.calculate(
            signal=bullish_signal,
            account=low_balance_account,
            risk_config=default_risk_config
        )

        # 应取 min(2500, 1000) = 1000
        assert abs(sizing.investment_amount - 1000.0) < 0.01, \
            "投资金额应取固定比例和可用余额的较小值"


class TestP1_ParameterValidation:
    """P1-问题 7: 参数有效性校验验证"""

    def test_risk_pct_upper_bound(self, risk_sizer, default_account, bullish_signal):
        """验证 risk_pct 上限 10%"""
        high_risk_config = RiskConfig(
            risk_pct=0.15,  # 15% 超限
            max_sl_dist=0.035,
            max_leverage=20.0,
            max_positions=4
        )

        with pytest.raises(RiskLimitExceeded) as exc_info:
            risk_sizer.calculate(
                signal=bullish_signal,
                account=default_account,
                risk_config=high_risk_config
            )

        assert "risk_pct" in str(exc_info.value).lower() or "风险比例" in str(exc_info.value)
        assert exc_info.value.error_code == "INVALID_RISK_PCT"

    def test_risk_pct_lower_bound(self, risk_sizer, default_account, bullish_signal):
        """验证 risk_pct 必须大于 0"""
        zero_risk_config = RiskConfig(
            risk_pct=0.0,  # 0 无效
            max_sl_dist=0.035,
            max_leverage=20.0,
            max_positions=4
        )

        with pytest.raises(RiskLimitExceeded):
            risk_sizer.calculate(
                signal=bullish_signal,
                account=default_account,
                risk_config=zero_risk_config
            )

    def test_leverage_upper_bound(self, risk_sizer, default_account, bullish_signal):
        """验证 max_leverage 上限 125"""
        high_leverage_config = RiskConfig(
            risk_pct=0.02,
            max_sl_dist=0.035,
            max_leverage=150.0,  # 超限
            max_positions=4
        )

        with pytest.raises(RiskLimitExceeded) as exc_info:
            risk_sizer.calculate(
                signal=bullish_signal,
                account=default_account,
                risk_config=high_leverage_config
            )

        assert "leverage" in str(exc_info.value).lower() or "杠杆" in str(exc_info.value)

    def test_leverage_lower_bound(self, risk_sizer, default_account, bullish_signal):
        """验证 max_leverage 下限 1"""
        low_leverage_config = RiskConfig(
            risk_pct=0.02,
            max_sl_dist=0.035,
            max_leverage=0.5,  # 低于 1
            max_positions=4
        )

        with pytest.raises(RiskLimitExceeded):
            risk_sizer.calculate(
                signal=bullish_signal,
                account=default_account,
                risk_config=low_leverage_config
            )


class TestP2_PositionLimit:
    """P2-问题 1: 配置化持仓上限验证"""

    def test_max_positions_from_config(self, risk_sizer, default_account, bullish_signal):
        """验证 max_positions 从配置读取"""
        # 创建只有 2 个持仓上限的配置
        custom_config = RiskConfig(
            risk_pct=0.02,
            max_sl_dist=0.035,
            max_leverage=20.0,
            max_positions=2  # 自定义上限
        )

        # 账户已有 2 个持仓
        account_at_limit = AccountBalance(
            total_wallet_balance=10000.0,
            available_balance=5000.0,
            current_positions_count=2,
            positions=[]
        )

        with pytest.raises(RiskLimitExceeded) as exc_info:
            risk_sizer.calculate(
                signal=bullish_signal,
                account=account_at_limit,
                risk_config=custom_config
            )

        assert "2" in str(exc_info.value), "错误信息应包含配置的 max_positions 值"

    def test_default_max_positions_is_4(self, default_risk_config):
        """验证默认 max_positions 为 4"""
        assert default_risk_config.max_positions == 4


class TestP2_PositionValueRatio:
    """P2-问题 5: 仓位价值比例校验验证"""

    def test_position_value_ratio_limit(self, risk_sizer, default_account, tight_stop_signal, default_risk_config):
        """验证仓位价值不超过账户总额的 3 倍"""
        # tight_stop_signal 止损距离 0.5%，名义价值 = 200/0.005 = 40000 (4 倍账户总额)
        # 应触发 3 倍上限拦截

        with pytest.raises(RiskLimitExceeded) as exc_info:
            risk_sizer.calculate(
                signal=tight_stop_signal,
                account=default_account,
                risk_config=default_risk_config
            )

        assert "仓位价值" in str(exc_info.value) or "POSITION_VALUE" in str(exc_info.value.error_code)

    def test_max_position_value_ratio_constant(self):
        """验证 MAX_POSITION_VALUE_RATIO 常数为 3.0"""
        assert MAX_POSITION_VALUE_RATIO == Decimal("3.0")


class TestP3_DecimalPrecision:
    """P3-问题 8: 浮点数精度验证"""

    def test_calculation_uses_decimal(self, risk_sizer, default_account, bullish_signal, default_risk_config):
        """验证关键计算使用 Decimal"""
        # 虽然无法直接验证内部实现，但可以通过结果精度间接验证
        sizing = risk_sizer.calculate(
            signal=bullish_signal,
            account=default_account,
            risk_config=default_risk_config
        )

        # 验证结果保留 6 位小数
        leverage_str = str(sizing.suggested_leverage)
        quantity_str = str(sizing.suggested_quantity)

        # 检查是否进行了精度处理（不会有过长的浮点尾数）
        assert len(leverage_str.split('.')[-1]) <= 6 if '.' in leverage_str else True
        assert len(quantity_str.split('.')[-1]) <= 6 if '.' in quantity_str else True


class TestP3_ExceptionStructure:
    """P3-问题 9: 异常结构化验证"""

    def test_risk_limit_exceeded_has_error_code(self):
        """验证 RiskLimitExceeded 包含 error_code"""
        exc = RiskLimitExceeded("测试错误", error_code="TEST_ERROR", context={"key": "value"})

        assert hasattr(exc, 'error_code')
        assert exc.error_code == "TEST_ERROR"
        assert exc.context == {"key": "value"}
        assert str(exc) == "测试错误"

    def test_exception_to_dict(self):
        """验证异常可序列化为字典"""
        exc = RiskLimitExceeded("测试错误", error_code="TEST_ERROR", context={"key": "value"})

        # 验证属性可直接访问
        assert exc.message == "测试错误"
        assert exc.error_code == "TEST_ERROR"
        assert exc.context == {"key": "value"}


class TestPortfolioRiskService:
    """P1-问题 12: 投资组合风险聚合服务验证"""

    def test_calculate_portfolio_risk_empty(self, portfolio_risk_service):
        """验证空持仓组合风险计算"""
        metrics = portfolio_risk_service.calculate_portfolio_risk(
            positions=[],
            total_wallet_balance=10000.0
        )

        assert metrics.total_risk_amount == 0.0
        assert metrics.total_risk_pct == 0.0
        assert metrics.max_single_loss_pct == 0.0
        assert metrics.position_count == 0

    def test_calculate_portfolio_risk_with_positions(self, portfolio_risk_service):
        """验证有持仓组合风险计算"""
        positions = [
            Position(symbol="BTCUSDT", quantity=0.1, entry_price=50000, leverage=10, risk_amount=200),
            Position(symbol="ETHUSDT", quantity=1.0, entry_price=3000, leverage=10, risk_amount=150),
            Position(symbol="SOLUSDT", quantity=10.0, entry_price=100, leverage=10, risk_amount=100),
        ]

        metrics = portfolio_risk_service.calculate_portfolio_risk(
            positions=positions,
            total_wallet_balance=10000.0
        )

        # 总风险 = 200 + 150 + 100 = 450
        assert metrics.total_risk_amount == 450.0

        # 总风险比例 = 450 / 10000 = 4.5%
        assert metrics.total_risk_pct == 0.045

        # 最大单笔风险 = 200
        assert metrics.max_single_loss_pct == 0.02

        # 持仓数量 = 3
        assert metrics.position_count == 3

    def test_check_portfolio_limit_pass(self, portfolio_risk_service):
        """验证组合风险未超限检查"""
        metrics = PortfolioRiskMetrics(
            total_risk_amount=400,
            total_risk_pct=0.04,  # 4%
            max_single_loss_pct=0.02,
            position_count=2
        )

        # 默认上限 8%，应通过
        assert portfolio_risk_service.check_portfolio_limit(metrics) is True

    def test_check_portfolio_limit_exceeded(self, portfolio_risk_service):
        """验证组合风险超限检查"""
        metrics = PortfolioRiskMetrics(
            total_risk_amount=1000,
            total_risk_pct=0.10,  # 10% 超限
            max_single_loss_pct=0.05,
            position_count=5
        )

        # 默认上限 8%，应超限
        assert portfolio_risk_service.check_portfolio_limit(metrics) is False

    def test_check_portfolio_limit_custom_threshold(self, portfolio_risk_service):
        """验证自定义风险上限"""
        metrics = PortfolioRiskMetrics(
            total_risk_amount=600,
            total_risk_pct=0.06,  # 6%
            max_single_loss_pct=0.03,
            position_count=3
        )

        # 默认 8% 通过
        assert portfolio_risk_service.check_portfolio_limit(metrics, 0.08) is True

        # 自定义 5% 超限
        assert portfolio_risk_service.check_portfolio_limit(metrics, 0.05) is False


class TestPositionEntity:
    """P3-问题 10: Position 强类型实体验证"""

    def test_position_has_risk_amount(self):
        """验证 Position 实体有 risk_amount 字段"""
        pos = Position(
            symbol="BTCUSDT",
            quantity=0.1,
            entry_price=50000,
            leverage=10,
            risk_amount=200.0
        )

        assert hasattr(pos, 'risk_amount')
        assert pos.risk_amount == 200.0

    def test_position_risk_amount_default(self):
        """验证 risk_amount 默认值为 0"""
        pos = Position(
            symbol="BTCUSDT",
            quantity=0.1,
            entry_price=50000,
            leverage=10
        )

        assert pos.risk_amount == 0.0

    def test_position_all_fields(self):
        """验证 Position 所有字段"""
        pos = Position(
            symbol="ETHUSDT",
            quantity=1.5,
            entry_price=3000.0,
            leverage=15,
            unrealized_pnl=150.0,
            position_value=4500.0,
            risk_amount=90.0
        )

        assert pos.symbol == "ETHUSDT"
        assert pos.quantity == 1.5
        assert pos.entry_price == 3000.0
        assert pos.leverage == 15
        assert pos.unrealized_pnl == 150.0
        assert pos.position_value == 4500.0
        assert pos.risk_amount == 90.0


class TestIntegration:
    """集成测试：验证完整流程"""

    def test_full_calculation_flow(self, risk_sizer, default_account, bullish_signal, default_risk_config):
        """验证完整计算流程"""
        sizing = risk_sizer.calculate(
            signal=bullish_signal,
            account=default_account,
            risk_config=default_risk_config
        )

        # 验证返回类型正确
        assert sizing.signal is bullish_signal
        assert isinstance(sizing.suggested_leverage, float)
        assert isinstance(sizing.suggested_quantity, float)
        assert isinstance(sizing.investment_amount, float)
        assert isinstance(sizing.risk_amount, float)
        assert isinstance(sizing.actual_risk_amount, float)
        assert isinstance(sizing.leverage_capped, bool)

        # 验证风险金额合理性
        assert sizing.risk_amount > 0
        assert sizing.actual_risk_amount > 0

        # 验证杠杆为正
        assert sizing.suggested_leverage > 0

        # 验证开仓数量为正
        assert sizing.suggested_quantity > 0

    def test_portfolio_risk_integration(self, portfolio_risk_service):
        """验证组合风险服务集成"""
        # 模拟实际场景：3 个持仓，总风险 4.5%
        positions = [
            Position(symbol="BTCUSDT", quantity=0.1, entry_price=50000, leverage=10, risk_amount=200),
            Position(symbol="ETHUSDT", quantity=1.0, entry_price=3000, leverage=10, risk_amount=150),
            Position(symbol="SOLUSDT", quantity=10.0, entry_price=100, leverage=10, risk_amount=100),
        ]

        metrics = portfolio_risk_service.calculate_portfolio_risk(
            positions=positions,
            total_wallet_balance=10000.0
        )

        # 验证检查逻辑
        assert portfolio_risk_service.check_portfolio_limit(metrics, 0.08) is True  # 4.5% < 8%
        assert portfolio_risk_service.check_portfolio_limit(metrics, 0.04) is False  # 4.5% > 4%
