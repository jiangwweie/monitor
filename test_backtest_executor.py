"""
BacktestExecutor 单元测试
"""
import unittest
from infrastructure.backtest.executor import BacktestExecutor, Position, EquitySnapshot


class TestBacktestExecutor(unittest.TestCase):
    """BacktestExecutor 测试用例"""

    def setUp(self):
        """每个测试前的准备工作"""
        self.executor = BacktestExecutor(
            initial_balance=100000.0,
            fee_maker=0.00075,
            fee_taker=0.0008
        )

    def test_open_long_position(self):
        """测试开多仓"""
        success = self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            order_type="market",
            timestamp=1700000000000
        )

        self.assertTrue(success)
        self.assertEqual(len(self.executor.positions), 1)

        # 验证持仓数据
        position = list(self.executor.positions.values())[0]
        self.assertEqual(position.symbol, "BTCUSDT")
        self.assertEqual(position.direction, "LONG")
        self.assertEqual(position.quantity, 0.1)
        self.assertEqual(position.entry_price, 50000)
        self.assertEqual(position.initial_qty, 0.1)  # 验证 initial_qty 在初始化时赋值

    def test_open_short_position(self):
        """测试开空仓"""
        success = self.executor.open_position(
            symbol="BTCUSDT",
            direction="SHORT",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        self.assertTrue(success)
        position = list(self.executor.positions.values())[0]
        self.assertEqual(position.direction, "SHORT")

    def test_open_position_insufficient_margin(self):
        """测试保证金不足时开仓失败"""
        # 尝试开立超过保证金的仓位
        success = self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=100,  # 100 * 50000 = 5,000,000，远超 100,000 余额
            price=50000,
            leverage=1,  # 1 倍杠杆，需要 5,000,000 保证金
            timestamp=1700000000000
        )

        self.assertFalse(success)
        self.assertEqual(len(self.executor.positions), 0)
        self.assertEqual(len(self.executor.rejection_log), 1)

    def test_close_position_full(self):
        """测试全仓平仓"""
        # 先开仓
        self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        position_id = list(self.executor.positions.keys())[0]

        # 全仓平仓
        success = self.executor.close_position(
            position_id=position_id,
            price=51000,
            timestamp=1700000001000
        )

        self.assertTrue(success)
        self.assertEqual(len(self.executor.positions), 0)

        # 验证成交记录
        close_trade = self.executor.trade_records[-1]
        self.assertEqual(close_trade.action, "CLOSE")
        self.assertGreater(close_trade.pnl, 0)  # 价格上涨，多仓盈利

    def test_close_position_partial(self):
        """测试部分平仓"""
        # 先开仓
        self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=1.0,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        position_id = list(self.executor.positions.keys())[0]

        # 部分平仓 0.3
        success = self.executor.close_position(
            position_id=position_id,
            price=51000,
            quantity=0.3,
            timestamp=1700000001000
        )

        self.assertTrue(success)
        self.assertEqual(len(self.executor.positions), 1)

        # 验证剩余持仓
        position = self.executor.positions[position_id]
        self.assertEqual(position.quantity, 0.7)

    def test_update_equity(self):
        """测试权益更新"""
        # 先开仓
        self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        # 更新权益
        self.executor.update_equity(
            current_prices={"BTCUSDT": 51000},
            timestamp=1700000001000
        )

        # 验证权益曲线
        self.assertEqual(len(self.executor.equity_curve), 1)
        snapshot = self.executor.equity_curve[0]
        self.assertEqual(snapshot.timestamp, 1700000001000)
        self.assertGreater(snapshot.unrealized_pnl, 0)  # 价格上涨，多仓盈利

    def test_maker_taker_fee(self):
        """测试 Maker/Taker 手续费区分"""
        # 限价单（Maker）
        self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            order_type="limit",
            timestamp=1700000000000
        )
        maker_fee = self.executor.trade_records[0].fee
        self.assertEqual(maker_fee, 5000 * 0.00075)  # 5000 * maker 费率

        # 重置
        self.executor.balance = 100000
        self.executor.cumulative_fees = 0
        self.executor.trade_records = []
        self.executor.positions = {}

        # 市价单（Taker）
        self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            order_type="market",
            timestamp=1700000000000
        )
        taker_fee = self.executor.trade_records[0].fee
        self.assertEqual(taker_fee, 5000 * 0.0008)  # 5000 * taker 费率

    def test_get_stats(self):
        """测试统计指标计算"""
        # 开多仓
        self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.1,
            price=50000,
            leverage=10,
            timestamp=1700000000000
        )

        # 更新权益（模拟 K 线推进）
        prices = [50000, 51000, 52000, 51500, 53000]
        for i, price in enumerate(prices):
            self.executor.update_equity(
                current_prices={"BTCUSDT": price},
                timestamp=1700000000000 + i * 3600000  # 每小时
            )

        # 平仓
        position_id = list(self.executor.positions.keys())[0]
        self.executor.close_position(
            position_id=position_id,
            price=53000,
            timestamp=1700000005000
        )

        # 获取统计
        stats = self.executor.get_stats()

        self.assertIn('total_return_pct', stats)
        self.assertIn('total_pnl', stats)
        self.assertIn('max_drawdown_pct', stats)
        self.assertIn('sharpe_ratio', stats)
        self.assertIn('win_rate', stats)
        self.assertIn('profit_factor', stats)
        self.assertIn('total_trades', stats)
        self.assertIn('win_count', stats)
        self.assertIn('loss_count', stats)

    def test_initial_qty_in_position_init(self):
        """测试 initial_qty 在 Position 初始化时赋值"""
        self.executor.open_position(
            symbol="BTCUSDT",
            direction="LONG",
            quantity=0.5,
            price=50000,
            timestamp=1700000000000
        )

        position = list(self.executor.positions.values())[0]
        self.assertEqual(position.initial_qty, 0.5)
        self.assertEqual(position.quantity, 0.5)


if __name__ == "__main__":
    unittest.main()
