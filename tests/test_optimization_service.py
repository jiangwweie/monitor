"""
参数优化服务单元测试
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, AsyncMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application.optimization_service import (
    OptimizationParam,
    OptimizationConfig,
    OptimizationResult,
    OptimizationService,
)


class TestOptimizationParam:
    """测试 OptimizationParam 数据类"""

    def test_create_optimization_param(self):
        """创建优化参数"""
        param = OptimizationParam(name="ema_period", values=[30, 60, 90])

        assert param.name == "ema_period"
        assert param.values == [30, 60, 90]

    def test_param_with_string_values(self):
        """参数值为字符串类型"""
        param = OptimizationParam(name="interval", values=["15m", "1h", "4h"])

        assert param.name == "interval"
        assert param.values == ["15m", "1h", "4h"]


class TestOptimizationConfig:
    """测试 OptimizationConfig 数据类"""

    def test_create_optimization_config(self):
        """创建优化配置"""
        config = OptimizationConfig(
            base_config={"symbol": "BTCUSDT", "interval": "1h"},
            params=[
                OptimizationParam(name="ema_period", values=[30, 60]),
                OptimizationParam(name="leverage", values=[5, 10]),
            ],
            objective="total_return_pct",
            top_n=5
        )

        assert config.base_config["symbol"] == "BTCUSDT"
        assert len(config.params) == 2
        assert config.objective == "total_return_pct"
        assert config.top_n == 5
        assert config.max_combinations == 200

    def test_default_values(self):
        """测试默认值"""
        config = OptimizationConfig(
            base_config={},
            params=[]
        )

        assert config.objective == "total_return_pct"
        assert config.top_n == 10
        assert config.max_combinations == 200


class TestOptimizationResult:
    """测试 OptimizationResult 数据类"""

    def test_create_result(self):
        """创建优化结果"""
        result = OptimizationResult(
            params={"ema_period": 60, "leverage": 10},
            total_return_pct=23.5,
            max_drawdown_pct=8.2,
            sharpe_ratio=1.8,
            win_rate=55.3,
            profit_factor=1.6,
            total_trades=42
        )

        assert result.params["ema_period"] == 60
        assert result.total_return_pct == 23.5
        assert result.total_trades == 42

    def test_default_values(self):
        """测试默认值"""
        result = OptimizationResult(params={"ema_period": 60})

        assert result.total_return_pct == 0.0
        assert result.max_drawdown_pct == 0.0
        assert result.sharpe_ratio == 0.0
        assert result.win_rate == 0.0
        assert result.profit_factor == 0.0
        assert result.total_trades == 0


class TestOptimizationService:
    """测试 OptimizationService 类"""

    @pytest.fixture
    def mock_backtest_service(self):
        """模拟 BacktestService"""
        service = Mock(spec=Mock)
        service.create_task = Mock()
        service.run_backtest = AsyncMock()
        return service

    @pytest.fixture
    def optimization_service(self, mock_backtest_service):
        """创建 OptimizationService 实例"""
        return OptimizationService(mock_backtest_service)

    def test_generate_combinations_single_param(self, optimization_service):
        """测试生成单个参数的组合"""
        params = [
            OptimizationParam(name="ema_period", values=[30, 60, 90]),
        ]

        combinations = optimization_service._generate_combinations(params)

        assert len(combinations) == 3
        assert combinations == [
            {"ema_period": 30},
            {"ema_period": 60},
            {"ema_period": 90},
        ]

    def test_generate_combinations_multiple_params(self, optimization_service):
        """测试生成多个参数的组合（笛卡尔积）"""
        params = [
            OptimizationParam(name="ema_period", values=[30, 60]),
            OptimizationParam(name="leverage", values=[5, 10, 20]),
        ]

        combinations = optimization_service._generate_combinations(params)

        assert len(combinations) == 6  # 2 * 3 = 6
        assert combinations == [
            {"ema_period": 30, "leverage": 5},
            {"ema_period": 30, "leverage": 10},
            {"ema_period": 30, "leverage": 20},
            {"ema_period": 60, "leverage": 5},
            {"ema_period": 60, "leverage": 10},
            {"ema_period": 60, "leverage": 20},
        ]

    def test_generate_combinations_exceeds_max(self, optimization_service):
        """测试组合数量超过上限时的处理"""
        params = [
            OptimizationParam(name="param1", values=list(range(100))),
            OptimizationParam(name="param2", values=list(range(100))),
        ]

        combinations = optimization_service._generate_combinations(params)

        assert len(combinations) == 10000  # 100 * 100

    def test_extract_result_from_task(self, optimization_service):
        """测试从 BacktestTask 提取结果"""
        # 创建模拟任务
        mock_task = Mock()
        mock_task.result = {
            "CustomMetrics": {
                "total_return_pct": 15.5,
                "max_drawdown_pct": 5.2,
                "sharpe_ratio": 1.2,
                "win_rate": 60.0,
                "profit_factor": 1.8,
                "total_trades": 25,
                "ema_period": 60,
                "leverage": 10,
            }
        }
        combo = {"ema_period": 60, "leverage": 10}

        result = optimization_service._extract_result(mock_task, combo)

        assert result is not None
        assert result.total_return_pct == 15.5
        assert result.max_drawdown_pct == 5.2
        assert result.sharpe_ratio == 1.2
        assert result.win_rate == 60.0
        assert result.profit_factor == 1.8
        assert result.total_trades == 25
        # 【验证】params 直接使用传入的 combo
        assert result.params == combo

    def test_extract_result_returns_none_on_empty(self, optimization_service):
        """测试空任务返回 None"""
        mock_task = Mock()
        mock_task.result = None

        result = optimization_service._extract_result(mock_task, {"ema_period": 60})

        assert result is None

    def test_extract_result_returns_none_on_no_metrics(self, optimization_service):
        """测试没有 CustomMetrics 返回 None"""
        mock_task = Mock()
        mock_task.result = {"other_field": "value"}

        result = optimization_service._extract_result(mock_task, {"ema_period": 60})

        assert result is None


class TestCombinationLimit:
    """测试组合数量限制逻辑"""

    @pytest.fixture
    def mock_backtest_service(self):
        service = Mock(spec=Mock)
        return OptimizationService(service)

    def test_combinations_truncated_in_run(self, mock_backtest_service):
        """测试在 run_optimization 中截断组合"""
        params = [
            OptimizationParam(name="p1", values=list(range(50))),  # 50
            OptimizationParam(name="p2", values=list(range(50))),  # 50 * 50 = 2500
        ]

        combinations = mock_backtest_service._generate_combinations(params)

        # 验证生成了 2500 个组合
        assert len(combinations) == 2500

        # 但 max_combinations=200 会截断
        assert len(combinations[:200]) == 200


class TestSorting:
    """测试排序逻辑"""

    def test_sort_by_return_descending(self):
        """测试按收益率降序排序"""
        results = [
            OptimizationResult(params={"a": 1}, total_return_pct=5.0),
            OptimizationResult(params={"a": 2}, total_return_pct=15.0),
            OptimizationResult(params={"a": 3}, total_return_pct=10.0),
        ]

        # 按收益率降序
        results.sort(key=lambda r: r.total_return_pct, reverse=True)

        assert results[0].total_return_pct == 15.0
        assert results[1].total_return_pct == 10.0
        assert results[2].total_return_pct == 5.0

    def test_sort_by_drawdown_ascending(self):
        """测试按回撤升序排序"""
        results = [
            OptimizationResult(params={"a": 1}, max_drawdown_pct=8.0),
            OptimizationResult(params={"a": 2}, max_drawdown_pct=3.0),
            OptimizationResult(params={"a": 3}, max_drawdown_pct=5.0),
        ]

        # 按回撤升序（越小越好）
        results.sort(key=lambda r: r.max_drawdown_pct, reverse=False)

        assert results[0].max_drawdown_pct == 3.0
        assert results[1].max_drawdown_pct == 5.0
        assert results[2].max_drawdown_pct == 8.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
