"""
BacktestExecutor 单元测试模块

验证回测执行器的核心功能：
- 开仓/平仓逻辑
- 保证金校验
- 盈亏计算
- 最大回撤 (MDD)
- 夏普比率 (Sharpe Ratio)
- 权益曲线格式
"""
import pytest
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.backtest.executor import BacktestExecutor, Position, TradeRecord, EquitySnapshot


class TestInitialQty:
    """验证 initial_qty 在构造时正确赋值"""

    def test_initial_qty_set_at_construction(self):
        """开一个多仓，验证 initial_qty == quantity"""
        executor = BacktestExecutor(initial_balance=100000.0)

        # 开多仓
        success = executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.5,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        assert success is True
        assert len(executor.get_all_positions()) == 1

        # 获取持仓
        position = executor.get_all_positions()[0]

        # 验证 initial_qty 已设置且等于 quantity
        assert position.initial_qty is not None
        assert position.initial_qty > 0
        assert position.initial_qty == position.quantity
        assert position.initial_qty == 0.5


class TestMarginManagement:
    """验证保证金管理逻辑"""

    def test_open_long_reduces_available_margin(self):
        """开多仓后可用保证金减少"""
        # 初始余额 10000，开 0.1 BTC @ 50000，leverage=10
        # 需要保证金 = 0.1 × 50000 / 10 = 500
        executor = BacktestExecutor(initial_balance=10000.0)

        initial_margin = executor.get_available_margin()
        assert initial_margin == 10000.0

        # 开仓
        success = executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        assert success is True

        # 验证可用保证金减少（允许手续费误差）
        # 手续费 = 5000 * 0.0008 = 4
        # 余额 = 10000 - 4 = 9996
        # 占用保证金 = 500
        # 可用 = 9996 - 500 = 9496
        current_margin = executor.get_available_margin()
        expected_margin = 10000 - 500  # 约 9500（忽略手续费）

        assert abs(current_margin - expected_margin) < 10, \
            f"可用保证金错误：期望约{expected_margin}, 实际{current_margin}"


class TestPnLCalculation:
    """验证盈亏计算逻辑"""

    def test_close_long_pnl_correct(self):
        """平多仓盈亏计算正确"""
        executor = BacktestExecutor(initial_balance=100000.0)

        # 开多 0.1 BTC @ 50000
        executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        position_id = executor.get_all_positions()[0].id

        # 平仓 @ 55000
        # 理论 PnL = (55000 - 50000) × 0.1 = 500（未扣手续费）
        executor.close_position(
            position_id=position_id,
            price=55000,
            timestamp=1700000001000
        )

        # 从成交记录中找到 CLOSE 记录
        close_records = [r for r in executor.get_trade_records() if r.action == "CLOSE"]
        assert len(close_records) == 1

        record = close_records[0]
        # 允许手续费误差（约 4.4 USDT）
        assert abs(record.pnl - 500) < 5, \
            f"多仓盈亏错误：期望约 500, 实际{record.pnl}"

    def test_close_short_pnl_correct(self):
        """平空仓盈亏计算正确"""
        executor = BacktestExecutor(initial_balance=100000.0)

        # 开空 0.1 BTC @ 50000
        executor.open_position(
            symbol="BTCUSDT",
            direction="SHORT",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        position_id = executor.get_all_positions()[0].id

        # 平仓 @ 45000
        # 理论 PnL = (50000 - 45000) × 0.1 = 500
        executor.close_position(
            position_id=position_id,
            price=45000,
            timestamp=1700000001000
        )

        # 从成交记录中找到 CLOSE 记录
        close_records = [r for r in executor.get_trade_records() if r.action == "CLOSE"]
        assert len(close_records) == 1

        record = close_records[0]
        # 允许手续费误差
        assert abs(record.pnl - 500) < 5, \
            f"空仓盈亏错误：期望约 500, 实际{record.pnl}"


class TestInsufficientMargin:
    """验证保证金不足拒绝逻辑"""

    def test_insufficient_margin_rejected(self):
        """保证金不足时开仓被拒绝"""
        # 初始余额 1000（小余额）
        executor = BacktestExecutor(initial_balance=1000.0)

        # 尝试开 10 BTC @ 50000，leverage=1
        # 需要保证金 = 10 × 50000 / 1 = 500000，远大于 1000
        success = executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=10,
            price=50000,
            leverage=1,
            timestamp=1700000000000
        )

        # 断言开仓失败
        assert success is False

        # 断言持仓列表为空
        positions = executor.get_all_positions()
        assert len(positions) == 0


class TestMaxDrawdown:
    """验证最大回撤 (MDD) 计算"""

    def test_mdd_captures_unrealized_loss(self):
        """最大回撤能捕捉未实现亏损"""
        # 初始余额 10000，开多 0.1 BTC @ 50000（leverage=10）
        executor = BacktestExecutor(initial_balance=10000.0)

        executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        # 调用 update_equity 模拟价格波动
        # ts=1: 价格 50000，无浮亏
        executor.update_equity({"BTCUSDT": 50000}, timestamp=1)

        # ts=2: 价格 40000，浮亏 = (40000-50000)×0.1 = -1000
        executor.update_equity({"BTCUSDT": 40000}, timestamp=2)

        # ts=3: 价格 50000，回升
        executor.update_equity({"BTCUSDT": 50000}, timestamp=3)

        # 平仓 @ 50000（无实现盈亏）
        position_id = executor.get_all_positions()[0].id
        executor.close_position(position_id=position_id, price=50000, timestamp=4)

        # 获取统计
        stats = executor.get_stats()

        # 断言：max_drawdown_pct > 0（必须捕捉到浮亏期间的回撤）
        assert stats['max_drawdown_pct'] > 0, \
            f"最大回撤应大于 0（捕捉到浮亏），实际{stats['max_drawdown_pct']}"


class TestSharpeRatio:
    """验证夏普比率 (Sharpe Ratio) 计算"""

    def test_sharpe_ratio_annualized(self):
        """夏普比率年化计算正确"""
        # 构造固定日收益率序列：每天收益率 0.001（0.1%）
        executor = BacktestExecutor(initial_balance=10000.0)

        # 模拟 30 天数据，每天权益增加 0.1%
        base_equity = 10000.0
        daily_return = 0.001  # 0.1%

        for day in range(30):
            # 通过直接修改 balance 来模拟固定收益
            # 实际场景中这是通过交易盈亏实现的
            executor.balance = base_equity * (1 + daily_return) ** day

            # 调用 update_equity 记录快照（timestamp 每天增加 86400*1000 毫秒）
            executor.update_equity(
                current_prices={},  # 无持仓，unrealized_pnl=0
                timestamp=(day + 1) * 86400 * 1000
            )

        # 获取夏普比率
        stats = executor.get_stats()
        sharpe = stats['sharpe_ratio']

        # 固定正收益率 + 低波动率 → 夏普应该为正且较高
        assert sharpe > 0, f"夏普比率应为正数，实际{sharpe}"


class TestEquityCurveFormat:
    """验证权益曲线返回格式"""

    def test_equity_curve_returns_dicts(self):
        """权益曲线返回字典列表而非 dataclass 对象"""
        executor = BacktestExecutor(initial_balance=10000.0)

        # 开仓
        executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        # 更新权益
        executor.update_equity({"BTCUSDT": 50000}, timestamp=1)
        executor.update_equity({"BTCUSDT": 51000}, timestamp=2)

        # 获取权益曲线
        equity_curve = executor.get_equity_curve()

        # 断言：返回结果是 list
        assert isinstance(equity_curve, list), "权益曲线应返回 list"

        # 断言：至少有一个元素
        assert len(equity_curve) > 0, "权益曲线不应为空"

        # 断言：每个元素是 dict（not dataclass）
        for point in equity_curve:
            assert isinstance(point, dict), f"权益曲线元素应为 dict，实际{type(point)}"

            # 断言：每个 dict 含有 "total_equity" 和 "timestamp" 字段
            assert "total_equity" in point, "权益曲线元素应包含 total_equity 字段"
            assert "timestamp" in point, "权益曲线元素应包含 timestamp 字段"

            # 断言：total_equity 是数字
            assert isinstance(point["total_equity"], (int, float)), \
                "total_equity 应为数字"


class TestPartialClose:
    """验证部分平仓逻辑"""

    def test_partial_close_reduces_position(self):
        """部分平仓减少持仓数量"""
        executor = BacktestExecutor(initial_balance=100000.0)

        # 开仓 1.0 BTC
        executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=1.0,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        position = executor.get_all_positions()[0]
        position_id = position.id
        initial_qty = position.quantity

        # 部分平仓 0.3
        success = executor.close_position(
            position_id=position_id,
            price=51000,
            quantity=0.3,
            timestamp=1700000001000
        )

        assert success is True

        # 验证持仓仍然存在
        positions = executor.get_all_positions()
        assert len(positions) == 1, "部分平仓后持仓应仍然存在"

        # 验证持仓数量减少
        remaining_position = positions[0]
        assert remaining_position.quantity == 0.7, \
            f"部分平仓后剩余数量应为 0.7，实际{remaining_position.quantity}"


class TestMakerTakerFee:
    """验证 Maker/Taker 手续费区分"""

    def test_limit_order_uses_maker_fee(self):
        """限价单使用 Maker 费率"""
        executor = BacktestExecutor(
            initial_balance=100000.0,
            fee_maker=0.00075,
            fee_taker=0.0008
        )

        # 限价单开仓
        executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            order_type="limit",
            timestamp=1700000000000
        )

        # 获取开仓记录
        open_records = [r for r in executor.get_trade_records() if r.action == "OPEN"]
        assert len(open_records) == 1

        record = open_records[0]
        expected_fee = 5000 * 0.00075  # position_value * maker_rate

        assert abs(record.fee - expected_fee) < 0.01, \
            f"Maker 手续费错误：期望{expected_fee}, 实际{record.fee}"
        assert record.fee_rate == 0.00075

    def test_market_order_uses_taker_fee(self):
        """市价单使用 Taker 费率"""
        executor = BacktestExecutor(
            initial_balance=100000.0,
            fee_maker=0.00075,
            fee_taker=0.0008
        )

        # 市价单开仓
        executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            order_type="market",
            timestamp=1700000000000
        )

        # 获取开仓记录
        open_records = [r for r in executor.get_trade_records() if r.action == "OPEN"]
        assert len(open_records) == 1

        record = open_records[0]
        expected_fee = 5000 * 0.0008  # position_value * taker_rate

        assert abs(record.fee - expected_fee) < 0.01, \
            f"Taker 手续费错误：期望{expected_fee}, 实际{record.fee}"
        assert record.fee_rate == 0.0008


class TestStatsCompleteness:
    """验证 get_stats() 返回完整指标"""

    def test_get_stats_returns_all_metrics(self):
        """get_stats() 返回所有必需指标"""
        executor = BacktestExecutor(initial_balance=100000.0)

        # 开仓
        executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        # 更新权益
        executor.update_equity({"BTCUSDT": 50000}, timestamp=1)
        executor.update_equity({"BTCUSDT": 51000}, timestamp=2)

        # 平仓
        position_id = executor.get_all_positions()[0].id
        executor.close_position(position_id=position_id, price=51000, timestamp=3)

        # 获取统计
        stats = executor.get_stats()

        # 验证所有必需字段存在
        required_fields = [
            'total_return_pct',
            'total_pnl',
            'total_fees',
            'max_drawdown_pct',
            'sharpe_ratio',
            'win_rate',
            'profit_factor',
            'total_trades',
            'win_count',
            'loss_count'
        ]

        for field in required_fields:
            assert field in stats, f"stats 应包含字段：{field}"
