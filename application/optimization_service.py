"""
参数优化服务模块

提供基于网格搜索的参数优化框架 MVP，支持：
- 多参数组合搜索（笛卡尔积）
- 自定义优化目标（收益率、回撤、夏普比率等）
- 返回 Top-N 最优参数组合
- 异步并发执行回测任务

架构说明：
- 依赖 BacktestService 执行子回测任务
- 使用 ProcessPoolExecutor 并发执行 FMZ 回测
- 任务状态存储于内存 Dict（生产环境可升级为 Redis）
"""
import os
import sys
import uuid
import asyncio
import logging
import itertools
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application.backtest_service import BacktestService, BacktestTask, TaskStatus

logger = logging.getLogger(__name__)


# ==============================================================================
# 常量定义
# ==============================================================================
# 优化目标白名单
VALID_OBJECTIVES = {
    "total_return_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    "win_rate",
    "profit_factor"
}


# ==============================================================================
# 数据类定义
# ==============================================================================
@dataclass
class OptimizationParam:
    """
    优化参数（单个参数的搜索范围）

    Attributes:
        name: 参数名，如 "ema_period"
        values: 候选值列表，如 [30, 60, 90, 120]
    """
    name: str            # 参数名，如 "ema_period"
    values: List[Any]    # 候选值列表，如 [30, 60, 90, 120]


@dataclass
class OptimizationConfig:
    """
    参数优化任务配置

    Attributes:
        base_config: 基础回测配置（同 BacktestRunRequest 的字段）
        params: 要搜索的参数列表
        objective: 优化目标字段名（如 "total_return_pct", "max_drawdown_pct"）
        top_n: 返回 Top-N 结果
        max_combinations: 最大组合数量上限（防止爆炸）
    """
    base_config: Dict[str, Any]      # 基础回测配置
    params: List[OptimizationParam]  # 要搜索的参数列表
    objective: str = "total_return_pct"  # 优化目标字段名
    top_n: int = 10                  # 返回 Top-N 结果
    max_combinations: int = 200      # 最大组合数量上限


@dataclass
class OptimizationResult:
    """
    单次参数组合的回测结果

    Attributes:
        params: 本次组合的参数值
        total_return_pct: 总收益率
        max_drawdown_pct: 最大回撤
        sharpe_ratio: 夏普比率
        win_rate: 胜率
        profit_factor: 盈亏比
        total_trades: 总交易次数
    """
    params: Dict[str, Any]     # 本次组合的参数值
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0


# ==============================================================================
# 参数优化服务
# ==============================================================================
class OptimizationService:
    """
    参数优化服务（网格搜索 MVP）

    核心功能：
    1. 生成所有参数组合（笛卡尔积）
    2. 按顺序/并发执行每个组合的回测
    3. 收集结果并按优化目标排序
    4. 返回 Top-N 最优参数组合

    使用示例：
        service = get_optimization_service()
        config = OptimizationConfig(
            base_config={"symbol": "BTCUSDT", "interval": "1h", ...},
            params=[
                OptimizationParam(name="ema_period", values=[30, 60, 90]),
                OptimizationParam(name="leverage", values=[5, 10, 20]),
            ],
            objective="total_return_pct",
            top_n=5
        )
        opt_task_id = await service.run_optimization(config)
    """

    def __init__(self, backtest_service: BacktestService):
        """
        初始化参数优化服务

        :param backtest_service: BacktestService 实例（依赖注入）
        """
        self.backtest_service = backtest_service
        self.tasks: Dict[str, Dict] = {}  # 任务状态存储

        logger.info(f"OptimizationService 初始化完成")

    def _generate_combinations(self, params: List[OptimizationParam]) -> List[Dict]:
        """
        生成所有参数组合（笛卡尔积）

        :param params: 优化参数列表
        :return: 参数组合字典列表

        示例：
        >>> params = [
        ...     OptimizationParam(name="ema_period", values=[30, 60]),
        ...     OptimizationParam(name="leverage", values=[5, 10]),
        ... ]
        >>> combinations = [
        ...     {"ema_period": 30, "leverage": 5},
        ...     {"ema_period": 30, "leverage": 10},
        ...     {"ema_period": 60, "leverage": 5},
        ...     {"ema_period": 60, "leverage": 10},
        ... ]
        """
        keys = [p.name for p in params]
        values = [p.values for p in params]
        all_combos = list(itertools.product(*values))
        return [dict(zip(keys, combo)) for combo in all_combos]

    def _extract_result(self, task: BacktestTask, combo: Dict) -> Optional[OptimizationResult]:
        """
        从 BacktestTask 提取 OptimizationResult

        :param task: 完成的回测任务
        :param combo: 当前参数组合（直接赋值给 params）
        :return: OptimizationResult 或 None
        """
        if not task.result:
            return None

        custom_metrics = task.result.get("CustomMetrics", {})
        if not custom_metrics:
            return None

        # 提取统计指标（params 直接使用传入的 combo）
        return OptimizationResult(
            params=combo,   # 【修复 1】直接使用当前参数组合，不从 custom_metrics 读取
            total_return_pct=custom_metrics.get("total_return_pct", 0.0),
            max_drawdown_pct=custom_metrics.get("max_drawdown_pct", 0.0),
            sharpe_ratio=custom_metrics.get("sharpe_ratio", 0.0),
            win_rate=custom_metrics.get("win_rate", 0.0),
            profit_factor=custom_metrics.get("profit_factor", 0.0),
            total_trades=custom_metrics.get("total_trades", 0)
        )

    async def run_optimization(self, config: OptimizationConfig) -> str:
        """
        启动参数优化任务（异步）

        流程：
        1. 生成所有参数组合
        2. 如果超过 max_combinations，截取前 max_combinations 个
        3. 创建优化任务记录（status: "running"）
        4. 异步按顺序执行每个组合的回测
        5. 按 objective 字段排序
        6. 更新任务状态为 "completed"
        7. 返回 opt_task_id

        :param config: 优化配置
        :return: opt_task_id
        """
        # ========== 1. 生成所有参数组合 ==========
        combinations = self._generate_combinations(config.params)
        total_combinations = len(combinations)

        logger.info(f"生成 {total_combinations} 个参数组合")

        # ========== 2. 限制组合数量 ==========
        if total_combinations > config.max_combinations:
            logger.warning(f"组合数量 {total_combinations} 超过上限 {config.max_combinations}，截断处理")
            combinations = combinations[:config.max_combinations]
            total_combinations = len(combinations)

        # ========== 3. 创建优化任务记录 ==========
        opt_task_id = f"opt-{uuid.uuid4().hex[:8]}"

        self.tasks[opt_task_id] = {
            "opt_task_id": opt_task_id,
            "status": "running",
            "created_at": datetime.now().isoformat(),
            "config": asdict(config),
            "total_combinations": total_combinations,
            "completed_combinations": 0,
            "results": [],
            "errors": []
        }

        # ========== 4. 异步执行优化（不阻塞返回） ==========
        asyncio.create_task(self._execute_optimization(opt_task_id, config, combinations))

        return opt_task_id

    async def _execute_optimization(
        self,
        opt_task_id: str,
        config: OptimizationConfig,
        combinations: List[Dict]
    ):
        """
        实际执行优化任务的内部方法

        :param opt_task_id: 优化任务 ID
        :param config: 优化配置
        :param combinations: 参数组合列表
        """
        task_record = self.tasks.get(opt_task_id)
        if not task_record:
            logger.error(f"优化任务不存在：{opt_task_id}")
            return

        results = []
        completed = 0

        try:
            for i, combo in enumerate(combinations):
                try:
                    logger.info(f"执行组合 {i+1}/{len(combinations)}: {combo}")

                    # ========== a. 合并配置（combo 优先级更高） ==========
                    merged_config = {**config.base_config, **combo}

                    # ========== b. 创建回测任务 ==========
                    backtest_task = self.backtest_service.create_task(merged_config)

                    # ========== c. 执行回测并等待完成 ==========
                    # 使用 asyncio.wrap_future 等待 ProcessPoolExecutor 完成
                    await self.backtest_service.run_backtest(backtest_task)

                    # 等待任务完成（轮询状态）
                    max_wait_seconds = 600  # 最长等待 10 分钟
                    wait_interval = 0.5
                    waited = 0

                    while backtest_task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                        await asyncio.sleep(wait_interval)
                        waited += wait_interval
                        if waited > max_wait_seconds:
                            raise TimeoutError(f"回测任务超时：{backtest_task.task_id}")

                    # ========== d. 检查任务状态 ==========
                    if backtest_task.status == TaskStatus.FAILED:
                        logger.error(f"回测任务失败：{backtest_task.task_id}, 错误：{backtest_task.error_message}")
                        task_record["errors"].append({
                            "combination": combo,
                            "error": backtest_task.error_message
                        })
                        continue

                    # ========== e. 提取结果 ==========
                    result = self._extract_result(backtest_task, combo)  # 【修复 1】传入 combo
                    if result:
                        results.append(result)
                        logger.info(f"组合 {combo} 完成：收益率={result.total_return_pct:.2f}%")

                except Exception as e:
                    logger.exception(f"执行组合 {combo} 时异常：{e}")
                    task_record["errors"].append({
                        "combination": combo,
                        "error": str(e)
                    })
                    # 继续执行其他组合

                completed += 1
                task_record["completed_combinations"] = completed

            # ========== 5. 按 objective 排序 ==========
            # 【修复 2】objective 白名单校验
            objective = config.objective
            if objective not in VALID_OBJECTIVES:
                logger.warning(f"无效的优化目标：{objective}，使用默认值 total_return_pct")
                objective = "total_return_pct"

            # 只有回撤是升序（越小越好），其他都是降序（越大越好）
            reverse_sort = objective != "max_drawdown_pct"

            # 排序
            results.sort(
                key=lambda r: getattr(r, objective, 0.0),
                reverse=reverse_sort
            )

            # ========== 6. 截取 Top-N ==========
            top_results = results[:config.top_n]

            # ========== 7. 更新任务状态 ==========
            task_record["status"] = "completed"
            task_record["completed_at"] = datetime.now().isoformat()
            task_record["results"] = [asdict(r) for r in top_results]

            logger.info(f"参数优化完成：{opt_task_id}, 最优收益率={top_results[0].total_return_pct if top_results else 0:.2f}%")

        except Exception as e:
            logger.exception(f"参数优化任务异常：{opt_task_id}, 错误：{e}")
            task_record["status"] = "failed"
            task_record["error_message"] = str(e)

    def get_optimization_result(self, opt_task_id: str) -> Optional[Dict]:
        """
        获取优化任务结果

        :param opt_task_id: 优化任务 ID
        :return: 任务记录字典，None 表示不存在
        """
        return self.tasks.get(opt_task_id)

    def get_optimization_task(self, opt_task_id: str) -> Optional[Dict]:
        """
        获取优化任务状态（用于进度查询）

        :param opt_task_id: 优化任务 ID
        :return: 任务记录字典
        """
        return self.tasks.get(opt_task_id)


# ==============================================================================
# 全局单例
# ==============================================================================
_optimization_service: Optional[OptimizationService] = None


def get_optimization_service(backtest_service: Optional[BacktestService] = None) -> OptimizationService:
    """
    获取 OptimizationService 单例

    :param backtest_service: BacktestService 实例（首次调用时传入）
    :return: OptimizationService 单例
    """
    global _optimization_service
    if _optimization_service is None:
        if backtest_service is None:
            from application.backtest_service import get_backtest_service
            backtest_service = get_backtest_service()
        _optimization_service = OptimizationService(backtest_service)
    return _optimization_service


def shutdown_optimization_service():
    """关闭 OptimizationService"""
    global _optimization_service
    if _optimization_service:
        _optimization_service = None
