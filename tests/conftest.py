"""
pytest 夹具模块
提供测试用的共享 fixtures
"""
import pytest
from decimal import Decimal

from core.entities import (
    Signal,
    AccountBalance,
    Position,
    RiskConfig,
    ScoringWeights,
    PinbarConfig
)
from domain.risk.sizer import PositionSizer
from domain.risk.portfolio_risk import PortfolioRiskService, PortfolioRiskMetrics


@pytest.fixture
def default_risk_config():
    """默认风控配置"""
    return RiskConfig(
        risk_pct=0.02,          # 2% 单笔风险
        max_sl_dist=0.035,      # 3.5% 最大止损
        max_leverage=20.0,      # 20x 最大杠杆
        max_positions=4,        # 最多 4 个持仓
        max_position_value_ratio=20.0  # 仓位价值比例上限 20 倍
    )


@pytest.fixture
def default_account():
    """默认账户状态"""
    return AccountBalance(
        total_wallet_balance=10000.0,  # 10000 USDT
        available_balance=10000.0,
        current_positions_count=0,
        positions=[]
    )


@pytest.fixture
def account_with_positions():
    """有持仓的账户状态"""
    return AccountBalance(
        total_wallet_balance=10000.0,
        available_balance=7000.0,  # 已有 3000 被占用
        current_positions_count=3,  # 已有 3 个持仓
        positions=[
            Position(symbol="BTCUSDT", quantity=0.1, entry_price=50000, leverage=10, risk_amount=200),
            Position(symbol="ETHUSDT", quantity=1.0, entry_price=3000, leverage=10, risk_amount=200),
            Position(symbol="SOLUSDT", quantity=10.0, entry_price=100, leverage=10, risk_amount=200),
        ]
    )


@pytest.fixture
def bullish_signal():
    """标准看涨信号"""
    return Signal(
        symbol="BTCUSDT",
        interval="1h",
        direction="LONG",
        entry_price=50000.0,
        stop_loss=48500.0,  # 3% 止损
        take_profit_1=52250.0,
        timestamp=1709900000000,
        reason="看涨 Pinbar",
        sl_distance_pct=0.03,  # 3% 止损距离
        score=75,
        quality_tier="B"
    )


@pytest.fixture
def tight_stop_signal():
    """小止损信号（止损距离很小）"""
    return Signal(
        symbol="BTCUSDT",
        interval="15m",
        direction="LONG",
        entry_price=50000.0,
        stop_loss=49750.0,  # 0.5% 止损
        take_profit_1=50750.0,
        timestamp=1709900000000,
        reason=" tight Pinbar",
        sl_distance_pct=0.005,  # 0.5% 止损距离
        score=80,
        quality_tier="A"
    )


@pytest.fixture
def risk_sizer():
    """风控算仓器实例"""
    return PositionSizer()


@pytest.fixture
def portfolio_risk_service():
    """组合风险服务实例"""
    return PortfolioRiskService()
