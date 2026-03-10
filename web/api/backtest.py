"""
回测 API 路由

提供 FMZ 回测任务的 HTTP 接口：
- POST /api/backtest/run - 启动回测任务
- GET /api/backtest/tasks - 获取任务列表
- GET /api/backtest/task/{taskId}/result - 获取任务结果
"""
import logging
from typing import List, Optional, Any, Dict, Literal
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from application.backtest_service import (
    BacktestService,
    BacktestTask,
    TaskStatus,
    get_backtest_service,
    FMZResultParser,
)
from application.optimization_service import (
    OptimizationService,
    OptimizationConfig,
    OptimizationParam,
    get_optimization_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["backtest"])


# ==============================================================================
# Request/Response Models
# ==============================================================================
class BacktestRunRequest(BaseModel):
    """启动回测请求"""
    symbol: str = Field(default="BTCUSDT", description="交易对")
    interval: str = Field(default="1h", description="时间周期")
    start_date: str = Field(default="2024-01-01 00:00:00", description="开始日期")
    end_date: str = Field(default="2024-02-01 00:00:00", description="结束日期")

    # FMZ 配置
    initial_balance: float = Field(default=100000.0, ge=1000, description="初始资金")
    fee_maker: int = Field(default=75, ge=0, description="Maker 手续费 (万分比)")
    fee_taker: int = Field(default=80, ge=0, description="Taker 手续费 (万分比)")
    fee_denominator: int = Field(default=5, ge=1, description="手续费分母")
    slip_point: int = Field(default=0, ge=0, description="滑点")

    # 策略配置
    max_sl_dist: float = Field(default=0.035, gt=0, le=1, description="最大止损距离")
    ema_period: int = Field(default=60, gt=0, description="EMA 周期")
    atr_period: int = Field(default=14, gt=0, description="ATR 周期")
    pinbar_config: Optional[Dict[str, Any]] = Field(default=None, description="Pinbar 配置")
    scoring_weights: Optional[Dict[str, Any]] = Field(default=None, description="评分权重")

    # 风控配置
    leverage: int = Field(default=10, ge=1, le=125, description="杠杆倍数")
    risk_pct: float = Field(default=0.02, gt=0, le=0.5, description="单笔风险比例")
    funding_rate: float = Field(default=0.0001, ge=0, description="资金费率")


class BacktestRunResponse(BaseModel):
    """启动回测响应"""
    taskId: str
    status: str


class TaskSummary(BaseModel):
    """任务摘要"""
    taskId: str
    symbol: str
    interval: str
    startDate: str
    endDate: str
    status: str
    progress: int
    createdAt: float
    startedAt: Optional[float] = None
    completedAt: Optional[float] = None
    errorMessage: Optional[str] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskSummary]
    total: int


class BacktestStatsResponse(BaseModel):
    """回测统计响应"""
    initialBalance: float
    finalBalance: float
    totalReturnPct: float
    totalPnl: float
    maxDrawdownPct: float
    winRate: float
    totalTrades: int
    winCount: int
    lossCount: int
    profitFactor: float
    buyCount: int
    sellCount: int
    errorCount: int
    # 新增字段（带默认值，向下兼容）
    sharpeRatio: float = 0.0
    totalFundingFees: float = 0.0
    totalFees: float = 0.0
    leverageUsed: int = 1


class BacktestResultResponse(BaseModel):
    """回测结果响应"""
    status: str
    taskId: Optional[str] = None
    stats: Optional[BacktestStatsResponse] = None
    equityCurve: Optional[List[Dict[str, Any]]] = None
    tradeLogs: Optional[List[Dict[str, Any]]] = None
    klineData: Optional[List[Dict[str, Any]]] = None  # 【新增】K 线 OHLCV 数据
    errorMessage: Optional[str] = None


# ==============================================================================
# API Endpoints
# ==============================================================================
@router.post("/run", response_model=BacktestRunResponse, summary="启动回测任务")
async def run_backtest(request: BacktestRunRequest):
    """
    启动一次 FMZ 回测任务

    将参数组装成 config string，然后在独立进程中拉起 FMZ VCtx 并运行。

    返回 taskId，用于后续轮询结果。
    """
    service = get_backtest_service()

    # 创建任务
    config = request.model_dump()
    task = service.create_task(config)

    # 提交执行
    await service.run_backtest(task)

    return BacktestRunResponse(
        taskId=task.task_id,
        status=task.status
    )


@router.get("/tasks", response_model=TaskListResponse, summary="获取任务列表")
async def list_tasks(
    status: Optional[str] = Query(None, description="状态过滤：pending, running, completed, failed"),
    limit: int = Query(50, ge=1, le=500, description="返回数量限制"),
):
    """
    获取历史任务列表

    支持按状态过滤，默认返回最近 50 条任务。
    """
    service = get_backtest_service()

    tasks = service.list_tasks(status=status)

    # 限制数量
    tasks = tasks[:limit]

    # 转换为摘要
    task_summaries = [
        TaskSummary(
            taskId=t.task_id,
            symbol=t.symbol,
            interval=t.interval,
            startDate=t.start_date,
            endDate=t.end_date,
            status=t.status,
            progress=t.progress,
            createdAt=t.created_at,
            startedAt=t.started_at,
            completedAt=t.completed_at,
            errorMessage=t.error_message,
        )
        for t in tasks
    ]

    return TaskListResponse(
        tasks=task_summaries,
        total=len(task_summaries)
    )


@router.get("/task/{task_id}/result", response_model=BacktestResultResponse, summary="获取任务结果")
async def get_task_result(task_id: str):
    """
    获取解析完成的回测成果

    包含：
    - stats: 统计指标（余额、盈亏、胜率等）
    - equityCurve: 权益曲线数据
    - tradeLogs: 交易日志
    """
    service = get_backtest_service()

    # 获取任务
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在：{task_id}")

    # 检查状态
    if task.status == TaskStatus.PENDING:
        return BacktestResultResponse(
            status=task.status,
            taskId=task_id,
            errorMessage="任务等待执行中"
        )

    if task.status == TaskStatus.RUNNING:
        return BacktestResultResponse(
            status=task.status,
            taskId=task_id,
            errorMessage="任务执行中，请稍后查询"
        )

    if task.status == TaskStatus.FAILED:
        return BacktestResultResponse(
            status=task.status,
            taskId=task_id,
            errorMessage=task.error_message
        )

    if task.status == TaskStatus.CANCELLED:
        return BacktestResultResponse(
            status=task.status,
            taskId=task_id,
            errorMessage="任务已取消"
        )

    # 获取解析结果
    result = service.get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=500, detail="结果解析失败")

    # 构建响应
    stats = result.get("stats", {})
    equity_curve = result.get("equityCurve", [])
    trade_logs = result.get("tradeLogs", [])
    # 从 CustomMetrics 提取新增字段
    custom_metrics = result.get("raw", {}).get("CustomMetrics", {})

    # 【新增】提取 K 线数据
    kline_data = custom_metrics.get("klines", [])

    return BacktestResultResponse(
        status=task.status,
        taskId=task_id,
        stats=BacktestStatsResponse(
            initialBalance=stats.get("initial_balance", 0),
            finalBalance=stats.get("final_balance", 0),
            totalReturnPct=stats.get("total_return_pct", 0),
            totalPnl=stats.get("total_pnl", 0),
            maxDrawdownPct=stats.get("max_drawdown_pct", 0),
            winRate=stats.get("win_rate", 0),
            totalTrades=stats.get("total_trades", 0),
            winCount=stats.get("win_count", 0),
            lossCount=stats.get("loss_count", 0),
            profitFactor=stats.get("profit_factor", 0),
            buyCount=stats.get("buy_count", 0),
            sellCount=stats.get("sell_count", 0),
            errorCount=stats.get("error_count", 0),
            # 新增字段
            sharpeRatio=custom_metrics.get("sharpe_ratio", 0.0),
            totalFundingFees=custom_metrics.get("total_funding_fees", 0.0),
            totalFees=custom_metrics.get("total_fees", 0.0),
            leverageUsed=custom_metrics.get("leverage_used", 1),
        ),
        equityCurve=equity_curve,
        tradeLogs=trade_logs,
        klineData=kline_data,  # 【新增】K 线数据
    )


@router.get("/task/{task_id}", summary="获取任务状态")
async def get_task_status(task_id: str):
    """
    仅获取任务状态和进度

    用于轻量级轮询，不返回完整结果
    """
    service = get_backtest_service()

    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在：{task_id}")

    return {
        "taskId": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "createdAt": task.created_at,
        "startedAt": task.started_at,
        "completedAt": task.completed_at,
        "errorMessage": task.error_message,
    }


# ==============================================================================
# 参数优化端点
# ==============================================================================
class OptimizationParamRequest(BaseModel):
    """参数优化请求 - 单个参数"""
    name: str = Field(..., description="参数名，如 'ema_period'")
    values: List[Any] = Field(..., description="候选值列表，如 [30, 60, 90]")


class OptimizationRunRequest(BaseModel):
    """启动参数优化请求"""
    base_config: Dict[str, Any] = Field(..., description="基础回测配置")
    params: List[OptimizationParamRequest] = Field(..., description="要搜索的参数列表")
    objective: Literal[
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe_ratio",
        "win_rate",
        "profit_factor"
    ] = Field(default="total_return_pct", description="优化目标字段名")
    top_n: int = Field(default=10, ge=1, le=50, description="返回 Top-N 结果")
    max_combinations: int = Field(default=200, ge=1, le=500, description="最大组合数量上限")


class OptimizationRunResponse(BaseModel):
    """启动参数优化响应"""
    optTaskId: str
    status: str
    totalCombinations: int


class OptimizationResultResponse(BaseModel):
    """参数优化结果响应"""
    status: str
    optTaskId: str
    totalCombinations: int
    completedCombinations: int
    results: Optional[List[Dict[str, Any]]] = None
    errorMessage: Optional[str] = None


@router.post("/optimize/run", response_model=OptimizationRunResponse, summary="启动参数优化任务")
async def run_optimization(request: OptimizationRunRequest):
    """
    启动参数优化任务（网格搜索）

    流程：
    1. 根据 params 生成所有参数组合（笛卡尔积）
    2. 按顺序执行每个组合的回测
    3. 按 objective 字段排序，返回 Top-N 结果

    优化目标说明：
    - total_return_pct: 总收益率（越大越好）
    - max_drawdown_pct: 最大回撤（越小越好）
    - sharpe_ratio: 夏普比率（越大越好）
    - win_rate: 胜率（越大越好）
    - profit_factor: 盈亏比（越大越好）
    """
    service = get_optimization_service()

    # 构建优化配置
    opt_params = [
        OptimizationParam(name=p.name, values=p.values)
        for p in request.params
    ]

    config = OptimizationConfig(
        base_config=request.base_config,
        params=opt_params,
        objective=request.objective,
        top_n=request.top_n,
        max_combinations=request.max_combinations
    )

    # 预计算组合数量（用于响应）
    import itertools
    values = [p.values for p in opt_params]
    total_combinations = len(list(itertools.product(*values)))
    if total_combinations > request.max_combinations:
        total_combinations = request.max_combinations

    # 启动优化任务
    opt_task_id = await service.run_optimization(config)

    return OptimizationRunResponse(
        optTaskId=opt_task_id,
        status="running",
        totalCombinations=total_combinations
    )


@router.get("/optimize/{opt_task_id}/result", response_model=OptimizationResultResponse, summary="获取参数优化结果")
async def get_optimization_result(opt_task_id: str):
    """
    获取参数优化任务结果

    返回格式：
    - status: "running" | "completed" | "failed"
    - results: 按 objective 排序的 Top-N 结果列表
    """
    service = get_optimization_service()

    # 获取任务状态
    task_record = service.get_optimization_result(opt_task_id)

    if not task_record:
        raise HTTPException(status_code=404, detail=f"优化任务不存在：{opt_task_id}")

    status = task_record.get("status", "running")

    # 构建响应
    response_data = {
        "status": status,
        "optTaskId": opt_task_id,
        "totalCombinations": task_record.get("total_combinations", 0),
        "completedCombinations": task_record.get("completed_combinations", 0),
        "results": None,
        "errorMessage": task_record.get("error_message")
    }

    # 如果任务完成，返回结果
    if status == "completed":
        results = task_record.get("results", [])
        # 添加 rank 字段
        for i, r in enumerate(results):
            r["rank"] = i + 1
        response_data["results"] = results

    return OptimizationResultResponse(**response_data)


@router.get("/optimize/{opt_task_id}", summary="获取参数优化任务状态")
async def get_optimization_task_status(opt_task_id: str):
    """
    仅获取优化任务状态和进度（轻量级接口）

    用于轮询时减少数据传输量
    """
    service = get_optimization_service()

    task = service.get_optimization_task(opt_task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"优化任务不存在：{opt_task_id}")

    return {
        "optTaskId": task.get("opt_task_id"),
        "status": task.get("status"),
        "totalCombinations": task.get("total_combinations", 0),
        "completedCombinations": task.get("completed_combinations", 0),
        "createdAt": task.get("created_at"),
        "completedAt": task.get("completed_at"),
        "errorMessage": task.get("error_message"),
    }
