"""
Web API 模块
提供用于热更新风控参数、获取指标雷达数据与系统遥测的状态面板。
"""

import time
from typing import Optional, List, Dict, Literal, Any
from fastapi import FastAPI, Request, Query, Body, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
import httpx
import json
import logging
import dataclasses

from core.entities import SignalFilter, ScoringWeights, PinbarConfig, IntervalConfig, Position
from domain.strategy.scoring_config import ScoringConfig
from domain.strategy.scoring_factory import ScoringStrategyFactory
from infrastructure.reader.binance_api import BinanceAccountReader
from domain.services import ConfigService, AccountService, SignalService
from application.signal_query_service import SignalQueryService
from application.position_service import PositionService
from application.backtest_service import get_backtest_service, shutdown_backtest_service

# 引入回测路由（本地导入）
from .backtest import router as backtest_router

logger = logging.getLogger(__name__)


def _position_to_dict(pos: Position) -> Dict[str, Any]:
    """将 Position 实体转换为前端友好的驼峰命名字典"""
    # 根据方向计算带符号的 positionAmt
    position_amt = pos.quantity if pos.direction == "LONG" else -pos.quantity
    return {
        "symbol": pos.symbol,
        "positionAmt": position_amt,
        "entryPrice": pos.entry_price,
        "unrealized_pnl": pos.unrealized_pnl,
        "leverage": pos.leverage,
        "positionValue": pos.position_value,
        "riskAmount": pos.risk_amount
    }


def _handle_binance_error(e: httpx.HTTPStatusError, context: str = "API") -> None:
    """
    统一处理 Binance API 错误

    :param e: HTTP 异常
    :param context: 错误上下文，用于错误消息前缀
    """
    status_code = e.response.status_code
    error_detail = e.response.text

    # 尝试解析错误内容
    try:
        error_data = e.response.json()
        error_code = error_data.get("code", 0)
        error_msg = error_data.get("msg", error_detail)
    except:
        error_code = 0
        error_msg = error_detail

    if status_code in [401, 403]:
        raise HTTPException(
            status_code=status_code,
            detail=f"BINANCE API ERROR: Invalid API Key or IP not allowed. Ensure the key is Read-Only. ({error_msg})",
        )
    elif error_code == -1021:
        raise HTTPException(
            status_code=503,
            detail=f"BINANCE TIME SYNC ERROR: Local clock drift detected. ({error_msg})",
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to {context}: {error_msg}",
        )


def _create_response(data: Any, status: str = "success", message: Optional[str] = None) -> Dict[str, Any]:
    """
    创建标准响应格式

    :param data: 响应数据
    :param status: 响应状态，默认 "success"
    :param message: 可选的消息
    :return: 标准响应字典
    """
    result = {
        "status": status,
        "data": data,
        "meta": {
            "timestamp": int(time.time() * 1000)
        }
    }
    if message:
        result["meta"]["message"] = message
    return result

# 初始化 FastAPI 实例
app = FastAPI(title="CryptoRadar API", description="系统动态配置中心及监控面板")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5176",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5176",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="web/static"), name="static")

# 注册回测 API 路由
app.include_router(backtest_router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("web/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


# ==========================================
# 1. 遥测与系统状态
# ==========================================
@app.get("/api/system/status")
async def get_system_status(request: Request):
    """获取系统的健康状态与交易所 API 权重消耗"""
    engine = request.app.state.engine
    uptime_seconds = int(time.time() - engine.start_time)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60

    data = {
        "is_connected": getattr(engine, "is_connected", False),
        "api_latency_ms": getattr(engine, "api_latency_ms", 0),
        "api_weight_usage": getattr(engine, "api_weight_usage", 0.0),
        "uptime": f"{days}d {hours}h {minutes}m",
    }
    return _create_response(data)


# ==========================================
# 1.5 交易所账户与持仓 (Dashboard)
# ==========================================
@app.get("/api/account/dashboard")
async def get_account_dashboard(request: Request):
    """
    账户仪表盘数据
    返回新字段结构：wallet_balance, total_unrealized_pnl, margin_balance
    """
    # 获取持仓服务（从 app.state 获取）
    service: PositionService = request.app.state.position_service

    try:
        # 获取数据
        wallet_balance = await service.get_wallet_balance()
        unrealized_pnl = await service.get_unrealized_pnl()
        margin_balance = await service.get_margin_balance(wallet_balance, unrealized_pnl)
        positions = await service.refresh_positions()

        return _create_response({
            "wallet_balance": wallet_balance,
            "total_unrealized_pnl": unrealized_pnl,
            "margin_balance": margin_balance,
            "current_positions_count": len(positions),
            "positions": positions,
        })
    except httpx.HTTPStatusError as e:
        _handle_binance_error(e, context="fetch account data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/positions/refresh")
async def refresh_positions(request: Request):
    """
    实时刷新持仓
    从币安 API 获取最新持仓数据
    """
    # 获取持仓服务（从 app.state 获取）
    service: PositionService = request.app.state.position_service

    try:
        positions = await service.refresh_positions()
        # 将 Position 实体转换为前端友好的驼峰命名字典
        positions_data = [_position_to_dict(pos) for pos in positions]
        return _create_response({"positions": positions_data})
    except httpx.HTTPStatusError as e:
        _handle_binance_error(e, context="fetch positions")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/account/wallet-balance")
async def get_wallet_balance(request: Request):
    """
    获取钱包余额（初始保证金）
    """
    # 获取持仓服务（从 app.state 获取）
    service: PositionService = request.app.state.position_service

    try:
        balance = await service.get_wallet_balance()
        return _create_response({"wallet_balance": balance})
    except httpx.HTTPStatusError as e:
        _handle_binance_error(e, context="fetch wallet balance")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/account/position/detail/{symbol}")
async def get_position_detail(request: Request, symbol: str):
    """提取单个币种的实盘持仓详情及止盈止损等挂单"""
    engine = request.app.state.engine
    reader = engine.account_reader

    if not reader:
        raise HTTPException(
            status_code=503,
            detail="Trading engine or account reader is not configured or offline.",
        )

    try:
        detail = await reader.fetch_position_detail(symbol)
        import dataclasses

        return {"status": "success", "data": dataclasses.asdict(detail)}
    except httpx.HTTPStatusError as e:
        _handle_binance_error(e, context="fetch position detail")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 1.6 账户余额与持仓 (新服务层接口)
# ==========================================
@app.get("/api/account/balance")
async def get_account_balance(request: Request):
    """
    获取账户余额信息
    返回钱包余额、可用余额、未实现盈亏等
    """
    repo = request.app.state.repo
    engine = request.app.state.engine

    # 检查 API 密钥是否配置
    api_key = await repo.get_secret("binance_api_key")
    api_secret = await repo.get_secret("binance_api_secret")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=400,
            detail="Binance API keys are not configured. Please set them in Settings.",
        )

    # 使用服务层获取数据
    account_reader = BinanceAccountReader(api_key=api_key, api_secret=api_secret)
    account_service = AccountService(account_reader)

    try:
        data = await account_service.get_balance()
        return _create_response(data)
    except httpx.HTTPStatusError as e:
        _handle_binance_error(e, context="fetch account balance")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/account/positions")
async def get_account_positions(request: Request):
    """
    获取账户持仓列表
    返回当前所有持仓的详细信息
    """
    repo = request.app.state.repo
    engine = request.app.state.engine

    # 检查 API 密钥是否配置
    api_key = await repo.get_secret("binance_api_key")
    api_secret = await repo.get_secret("binance_api_secret")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=400,
            detail="Binance API keys are not configured. Please set them in Settings.",
        )

    # 使用服务层获取数据
    account_reader = BinanceAccountReader(api_key=api_key, api_secret=api_secret)
    account_service = AccountService(account_reader)

    try:
        data = await account_service.get_positions()
        return _create_response(data)
    except httpx.HTTPStatusError as e:
        _handle_binance_error(e, context="fetch account positions")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 2. 信号展示与清理
# ==========================================
@app.get("/api/signals")
async def get_signals(
    request: Request,
    symbols: Optional[str] = None,
    intervals: Optional[str] = None,
    directions: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    source: Optional[str] = None,
    quality_tier: Optional[str] = None,
    sort_by: str = Query("timestamp", regex="^(timestamp|score)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    """
    分页、多维度历史信号检索接口

    支持以下过滤参数:
    - symbols: 交易对列表，逗号分隔，如 "BTCUSDT,ETHUSDT"
    - intervals: 时间周期列表，逗号分隔，如 "15m,1h"
    - directions: 方向列表，逗号分隔，如 "LONG,SHORT"
    - start_time: 开始时间戳 (毫秒)
    - end_time: 结束时间戳 (毫秒)
    - min_score: 最低分数
    - max_score: 最高分数
    - source: 信号来源 "realtime" 或 "history_scan"
    - quality_tier: 信号等级 "A"、"B" 或 "C"
    - sort_by: 排序字段 "timestamp" 或 "score"
    - order: 排序方向 "asc" 或 "desc"
    - page: 页码，从 1 开始
    - size: 每页数量，最大 200 (默认 20)
    """
    # 获取信号查询服务（从 app.state 获取）
    service: SignalQueryService = request.app.state.signal_query_service

    # 解析逗号分隔的参数
    symbols_list = symbols.split(",") if symbols else None
    intervals_list = intervals.split(",") if intervals else None
    directions_list = directions.split(",") if directions else None

    try:
        # 使用 SignalQueryService 查询
        result = await service.query_signals(
            symbols=symbols_list,
            intervals=intervals_list,
            directions=directions_list,
            start_time=start_time,
            end_time=end_time,
            min_score=min_score,
            max_score=max_score,
            quality_tier=quality_tier,
            source=source,
            page=page,
            size=size,
            sort_by=sort_by,
            order=order,
        )

        # 转换为字典列表
        def signal_to_dict(s) -> dict:
            return {
                "id": s.id,
                "symbol": s.symbol,
                "interval": s.interval,
                "direction": s.direction,
                "entry_price": s.entry_price,
                "stop_loss": s.stop_loss,
                "take_profit_1": s.take_profit_1,
                "timestamp": s.timestamp,
                "reason": s.reason,
                "sl_distance_pct": s.sl_distance_pct,
                "score": s.score,
                "score_details": s.score_details,
                "shadow_ratio": s.shadow_ratio,
                "ema_distance": s.ema_distance,
                "volatility_atr": s.volatility_atr,
                "source": s.source,
                "is_contrarian": s.is_contrarian,
                "is_shape_divergent": s.is_shape_divergent,
                "quality_tier": s.quality_tier,
            }

        # 直接返回分页数据，不使用 _create_response 包裹
        return {
            "items": [signal_to_dict(s) for s in result.items],
            "total": result.total,
            "page": result.page,
            "size": result.size,
        }
    except Exception as e:
        logger.error(f"信号查询失败：{e}")
        raise HTTPException(status_code=500, detail=f"信号查询失败：{str(e)}")


class DeleteSignalsReq(BaseModel):
    signal_ids: List[int]


@app.delete("/api/signals")
async def delete_signals(request: Request, req: DeleteSignalsReq):
    """批量删除指定的信号记录"""
    repo = request.app.state.repo

    if not req.signal_ids:
        return {"status": "success", "deleted_count": 0}

    deleted = await repo.delete_signals(req.signal_ids)
    return {"status": "success", "deleted_count": deleted}


@app.delete("/api/signals/clear")
async def clear_all_signals(request: Request):
    """清空所有信号记录"""
    repo = request.app.state.repo

    deleted = await repo.clear_all_signals()
    return {"status": "success", "deleted_count": deleted}


# ==========================================
# 2.5 历史信号检查 (History Scan)
# ==========================================
class HistoryCheckReq(BaseModel):
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    symbol: str
    interval: str


@app.post("/api/signals/history-check", status_code=202)
async def submit_history_check(request: Request, req: HistoryCheckReq = Body(...)):
    """
    提交一次历史信号扫描任务 (异步任务模型)。
    接口立即返回 task_id，前端通过轮询获取进度。
    """
    engine = request.app.state.engine
    scanner = getattr(request.app.state, "history_scanner", None)

    if not scanner:
        raise HTTPException(status_code=503, detail="历史扫描服务未初始化")

    # 校验 symbol 必须在当前已激活的币种列表中
    if req.symbol not in engine.active_symbols:
        raise HTTPException(
            status_code=400,
            detail=f"币种 {req.symbol} 不在当前激活列表中。可用: {engine.active_symbols}"
        )

    # 校验 interval 必须在当前监控周期键列表中
    if req.interval not in engine.monitor_intervals:
        raise HTTPException(
            status_code=400,
            detail=f"周期 {req.interval} 不在当前监控配置中。可用: {list(engine.monitor_intervals.keys())}"
        )

    # 校验日期合法性
    try:
        from datetime import datetime as dt
        start_dt = dt.strptime(req.start_date, "%Y-%m-%d")
        end_dt = dt.strptime(req.end_date, "%Y-%m-%d")
        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="start_date 必须早于 end_date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"日期格式错误: {str(e)}")

    task_id = scanner.submit_task(
        symbol=req.symbol,
        interval=req.interval,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    return {
        "status": "accepted",
        "task_id": task_id,
        "message": "历史信号扫描任务已启动"
    }


@app.get("/api/signals/history-check/{task_id}")
async def get_history_check_status(request: Request, task_id: str):
    """
    轮询历史扫描任务的执行状态。

    返回字段说明:
    - task_id: 任务 ID
    - status: 任务状态 (running/completed/failed)
    - progress: 进度 (0-100)
    - message: 当前状态描述
    - result: 扫描结果 (完成后返回)
    - config: 扫描配置 (symbol, interval, start_date, end_date)
    """
    scanner = getattr(request.app.state, "history_scanner", None)

    if not scanner:
        raise HTTPException(status_code=503, detail="历史扫描服务未初始化")

    task = scanner.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    response = {
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
    }

    # 添加 config 字段
    if task.config is not None:
        response["config"] = task.config

    if task.result is not None:
        response["result"] = task.result

    return response


# ==========================================
# 2.8 实时市场数据 (Market)
# ==========================================
@app.get("/api/market/prices")
async def get_market_prices(request: Request):
    """
    获取当前监控币种的实时价格心跳。
    出于性能及零占用 Binance 权重的考量，直接从引擎在内存中维护的最新价格字典读取。
    """
    return request.app.state.engine.latest_prices


# ==========================================
# 2.9 K 线图表数据聚合 (Chart Data)
# ==========================================
@app.get("/api/chart/data/{symbol}")
async def get_chart_data(
    request: Request,
    symbol: str,
    interval: str = "1h",
    limit: int = 200,
    end_time: Optional[int] = None,
):
    """
    获取指定交易对的 K 线 + 信号标记聚合数据 (TradingView 兼容格式)。
    内置 LRU 缓存，同一 symbol+interval 在一个 K 线周期内复用缓存。

    :param end_time: K 线结束时间戳 (毫秒)，默认当前时间（用于历史信号图表）
    """
    chart_service = getattr(request.app.state, "chart_service", None)
    if not chart_service:
        raise HTTPException(status_code=503, detail="图表服务未初始化")

    try:
        data = await chart_service.get_chart_data(
            symbol=symbol,
            interval=interval,
            limit=limit,
            end_time=end_time,
        )
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图表数据获取失败: {str(e)}")


# ==========================================
# 3. 动态配置与权重下发
# ==========================================
class ScoringWeightsConfig(BaseModel):
    w_shape: float = Field(..., ge=0.0, le=1.0)
    w_trend: float = Field(..., ge=0.0, le=1.0)
    w_vol: float = Field(..., ge=0.0, le=1.0)

    @field_validator("w_vol")
    def check_weights_sum(cls, v, values):
        w_shape = values.data.get("w_shape", 0)
        w_trend = values.data.get("w_trend", 0)
        total = round(w_shape + w_trend + v, 3)
        if total != 1.0:
            raise ValueError(f"打分权重的总和必须等于 1.0 (100%)，当前总和为: {total}")
        return v


class ExchangeSettingsConfig(BaseModel):
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None


class WebhookSettingsConfig(BaseModel):
    # 已废弃：推送配置请通过 .env 文件配置
    global_push_enabled: Optional[bool] = None
    feishu_enabled: Optional[bool] = None
    feishu_secret: Optional[str] = None
    wecom_enabled: Optional[bool] = None
    wecom_secret: Optional[str] = None


class IntervalConfigReq(BaseModel):
    use_trend_filter: bool = True


class PinbarConfigReq(BaseModel):
    body_max_ratio: float = Field(0.25, ge=0.05, le=0.8)
    shadow_min_ratio: float = Field(2.5, ge=1.0, le=10.0)
    volatility_atr_multiplier: float = Field(1.2, ge=0.5, le=5.0)
    doji_threshold: float = Field(0.05, ge=0.01, le=0.2)
    doji_shadow_bonus: float = Field(0.6, ge=0.1, le=1.0)
    mtf_trend_filter_mode: str = Field("soft", pattern="^(soft|hard)$")
    dynamic_sl_enabled: bool = True
    dynamic_sl_base: float = Field(0.035, ge=0.01, le=0.1)
    dynamic_sl_atr_multiplier: float = Field(0.5, ge=0.0, le=2.0)


class ScoringConfigReq(BaseModel):
    """打分配置更新请求体"""

    mode: Optional[Literal["classic", "progressive", "custom"]] = None

    # 经典模式参数
    classic_shadow_min: Optional[float] = Field(None, ge=0.3, le=0.8)
    classic_shadow_max: Optional[float] = Field(None, ge=0.7, le=1.0)
    classic_body_good: Optional[float] = Field(None, ge=0.01, le=0.3)
    classic_body_bad: Optional[float] = Field(None, ge=0.3, le=0.7)
    classic_vol_min: Optional[float] = Field(None, ge=0.8, le=2.0)
    classic_vol_max: Optional[float] = Field(None, ge=2.0, le=5.0)
    classic_trend_max_dist: Optional[float] = Field(None, ge=0.01, le=0.1)

    # 累进模式参数
    progressive_base_cap: Optional[float] = Field(None, ge=20.0, le=50.0)
    progressive_shadow_threshold: Optional[float] = Field(None, ge=0.4, le=0.8)
    progressive_shadow_bonus_rate: Optional[float] = Field(None, ge=10.0, le=50.0)
    progressive_body_bonus_threshold: Optional[float] = Field(None, ge=0.05, le=0.2)
    progressive_body_bonus_rate: Optional[float] = Field(None, ge=50.0, le=200.0)
    progressive_doji_bonus: Optional[float] = Field(None, ge=0.0, le=20.0)
    progressive_vol_threshold: Optional[float] = Field(None, ge=1.2, le=3.0)
    progressive_vol_bonus_rate: Optional[float] = Field(None, ge=5.0, le=30.0)
    progressive_extreme_vol_threshold: Optional[float] = Field(None, ge=2.0, le=4.0)
    progressive_extreme_vol_bonus: Optional[float] = Field(None, ge=5.0, le=20.0)
    progressive_penetration_rate: Optional[float] = Field(None, ge=10.0, le=50.0)

    # 权重配置
    w_shape: Optional[float] = Field(None, ge=0.0, le=1.0)
    w_trend: Optional[float] = Field(None, ge=0.0, le=1.0)
    w_vol: Optional[float] = Field(None, ge=0.0, le=1.0)

    @model_validator(mode='after')
    def check_weights_sum(self) -> 'ScoringConfigReq':
        """验证权重总和为 1.0（仅当三个权重都传入时）"""
        w_shape = self.w_shape
        w_trend = self.w_trend
        w_vol = self.w_vol

        if w_shape is not None and w_trend is not None and w_vol is not None:
            total = round(w_shape + w_trend + w_vol, 4)
            if abs(total - 1.0) > 0.0001:
                raise ValueError(f"权重总和必须等于 1.0，当前总和为：{total}")

        return self


ScoringConfigReq.model_rebuild()


class ScorePreviewRequest(BaseModel):
    """分数预览请求体"""

    config: Dict[str, Any]
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    limit: int = Field(500, ge=100, le=2000)


class RiskConfig(BaseModel):
    """风险配置模型"""
    risk_pct: Optional[float] = Field(None, ge=0.005, le=0.1)
    max_sl_dist: Optional[float] = Field(None, ge=0.01, le=0.1)
    max_leverage: Optional[float] = Field(None, ge=1.0, le=125.0)
    max_positions: Optional[int] = Field(None, ge=1, le=10)


class ConfigUpdateReq(BaseModel):
    system_enabled: Optional[bool] = None
    active_symbols: Optional[List[str]] = None
    monitor_intervals: Optional[Dict[str, IntervalConfigReq]] = None
    scoring_weights: Optional[ScoringWeightsConfig] = None
    exchange_settings: Optional[ExchangeSettingsConfig] = None
    webhook_settings: Optional[WebhookSettingsConfig] = None
    pinbar_config: Optional[PinbarConfigReq] = None
    risk_config: Optional[RiskConfig] = None
    auto_order_status: Optional[str] = (
        None  # 仅仅是为了接口兼容，后端将强行忽略该值的修改
    )


async def get_pinbar_config_from_db(repo, engine_pinbar_config):
    """从数据库读取 pinbar 配置，如果数据库中没有则返回引擎配置"""
    pinbar_config_json = await repo.get_secret("pinbar_config")
    if pinbar_config_json:
        try:
            return json.loads(pinbar_config_json)
        except json.JSONDecodeError:
            pass
    import dataclasses
    return dataclasses.asdict(engine_pinbar_config) if engine_pinbar_config else {}



@app.get("/api/config")
async def get_config(request: Request):
    engine = request.app.state.engine
    repo = engine.repo

    # 从数据库读取 system_enabled
    system_enabled_val = await repo.get_secret("system_enabled")
    system_enabled = system_enabled_val.lower() == "true" if system_enabled_val else True

    # 从数据库读取活跃币种
    active_symbols_json = await repo.get_secret("active_symbols")
    active_symbols = json.loads(active_symbols_json) if active_symbols_json else []

    # 从数据库读取监控周期配置
    monitor_intervals_json = await repo.get_secret("monitor_intervals")
    monitor_intervals = {}
    if monitor_intervals_json:
        try:
            intervals_data = json.loads(monitor_intervals_json)
            if isinstance(intervals_data, dict):
                from core.entities import IntervalConfig
                monitor_intervals = {
                    k: IntervalConfig(**v) if isinstance(v, dict) else IntervalConfig()
                    for k, v in intervals_data.items()
                }
        except json.JSONDecodeError:
            pass



    # 从数据库读取风险配置
    risk_config_json = await repo.get_secret("risk_config")
    if risk_config_json:
        try:
            risk_config_data = json.loads(risk_config_json)
            risk_config = {
                "risk_pct": risk_config_data.get("risk_pct", engine.risk_config.risk_pct),
                "max_sl_dist": risk_config_data.get("max_sl_dist", engine.risk_config.max_sl_dist),
                "max_leverage": risk_config_data.get("max_leverage", engine.risk_config.max_leverage),
                "max_positions": risk_config_data.get("max_positions", engine.risk_config.max_positions),
            }
        except json.JSONDecodeError:
            risk_config = {
                "risk_pct": engine.risk_config.risk_pct,
                "max_sl_dist": engine.risk_config.max_sl_dist,
                "max_leverage": engine.risk_config.max_leverage,
                "max_positions": engine.risk_config.max_positions,
            }
    else:
        risk_config = {
            "risk_pct": engine.risk_config.risk_pct,
            "max_sl_dist": engine.risk_config.max_sl_dist,
            "max_leverage": engine.risk_config.max_leverage,
            "max_positions": engine.risk_config.max_positions,
        }

    # 从数据库读取评分权重配置
    scoring_config_json = await repo.get_secret("scoring_config")
    if scoring_config_json:
        try:
            scoring_config_data = json.loads(scoring_config_json)
            scoring_weights = {
                "w_shape": scoring_config_data.get("w_shape", 0.4),
                "w_trend": scoring_config_data.get("w_trend", 0.3),
                "w_vol": scoring_config_data.get("w_vol", 0.3),
            }
        except json.JSONDecodeError:
            scoring_weights = {
                "w_shape": engine.weights.w_shape,
                "w_trend": engine.weights.w_trend,
                "w_vol": engine.weights.w_vol,
            }
    else:
        scoring_weights = {
            "w_shape": engine.weights.w_shape,
            "w_trend": engine.weights.w_trend,
            "w_vol": engine.weights.w_vol,
        }

    import dataclasses


    # 从环境变量读取推送配置（不再从数据库读取私密配置）
    import os
    global_push_enabled = os.getenv("GLOBAL_PUSH_ENABLED", "true").lower() != "false"
    feishu_enabled = os.getenv("FEISHU_ENABLED", "false").lower() == "true"
    wecom_enabled = os.getenv("WECOM_ENABLED", "false").lower() == "true"

    return {
        "system_enabled": system_enabled,
        "active_symbols": active_symbols,
        "monitor_intervals": {
            k: dataclasses.asdict(v) for k, v in monitor_intervals.items()
        }
        if monitor_intervals
        else {},
        "risk_config": risk_config,
        "scoring_weights": scoring_weights,
        "pinbar_config": await get_pinbar_config_from_db(repo, engine.pinbar_config),
        "auto_order_status": "OFF",
        "push_config": {
            "global_enabled": global_push_enabled,
            "feishu_enabled": feishu_enabled,
            "wecom_enabled": wecom_enabled,
            # 注意：API Key 和 Webhook URL 不再通过 API 返回
        },
    }



@app.put("/api/config")
async def update_config(request: Request, req: ConfigUpdateReq = Body(...)):
    engine = request.app.state.engine
    repo = request.app.state.repo

    if req.system_enabled is not None:
        engine.system_enabled = req.system_enabled

    if req.active_symbols is not None:
        engine.active_symbols = req.active_symbols
        await repo.set_secret("active_symbols", json.dumps(req.active_symbols))

    if req.monitor_intervals is not None:
        new_intervals = {
            k: IntervalConfig(use_trend_filter=v.use_trend_filter)
            for k, v in req.monitor_intervals.items()
        }
        engine.monitor_intervals = new_intervals
        await repo.set_secret(
            "monitor_intervals",
            json.dumps({k: dataclasses.asdict(v) for k, v in new_intervals.items()}),
        )

    if req.scoring_weights:
        engine.weights = ScoringWeights(
            w_shape=req.scoring_weights.w_shape,
            w_trend=req.scoring_weights.w_trend,
            w_vol=req.scoring_weights.w_vol,
        )

    if req.pinbar_config:
        engine.pinbar_config = PinbarConfig(
            body_max_ratio=req.pinbar_config.body_max_ratio,
            shadow_min_ratio=req.pinbar_config.shadow_min_ratio,
            volatility_atr_multiplier=req.pinbar_config.volatility_atr_multiplier,
            doji_threshold=req.pinbar_config.doji_threshold,
            doji_shadow_bonus=req.pinbar_config.doji_shadow_bonus,
            mtf_trend_filter_mode=req.pinbar_config.mtf_trend_filter_mode,
            dynamic_sl_enabled=req.pinbar_config.dynamic_sl_enabled,
            dynamic_sl_base=req.pinbar_config.dynamic_sl_base,
            dynamic_sl_atr_multiplier=req.pinbar_config.dynamic_sl_atr_multiplier,
        )
        await repo.set_secret(
            "pinbar_config", json.dumps(dataclasses.asdict(engine.pinbar_config))
        )

    if req.risk_config:
        if req.risk_config.risk_pct is not None:
            engine.risk_config.risk_pct = req.risk_config.risk_pct
        if req.risk_config.max_sl_dist is not None:
            engine.risk_config.max_sl_dist = req.risk_config.max_sl_dist
        if req.risk_config.max_leverage is not None:
            engine.risk_config.max_leverage = req.risk_config.max_leverage
        if req.risk_config.max_positions is not None:
            engine.risk_config.max_positions = req.risk_config.max_positions
        await repo.set_secret(
            "risk_config",
            json.dumps({
                "risk_pct": engine.risk_config.risk_pct,
                "max_sl_dist": engine.risk_config.max_sl_dist,
                "max_leverage": engine.risk_config.max_leverage,
                "max_positions": engine.risk_config.max_positions,
            }),
        )

    # 注意：exchange_settings 已废弃，API Key 请通过 .env 文件配置

    # 安全防线：忽视所有对 auto_order_status 的修改，保持后端处于零执行的只读模式
    if req.auto_order_status is not None:
        logger.warning(
            f"检测到试图修改 auto_order_status 为 {req.auto_order_status}，后端安全锁已拒绝该操作。"
        )

    # 注意：webhook_settings 已废弃，推送配置请通过 .env 文件配置

    return {"status": "success", "message": "Configuration hot-reloaded successfully"}


# ==========================================
# 4. 用户偏好设置 (User Preferences)
# ==========================================
@app.get("/api/preferences/view")
async def get_preferences_view(request: Request):
    """获取前端表格的列显示配置"""
    repo = request.app.state.repo
    val = await repo.get_secret("preferences_view_columns")
    if val:
        import json

        return {"signals_table_columns": json.loads(val)}
    return {"signals_table_columns": {}}


@app.put("/api/preferences/view")
async def update_preferences_view(request: Request, body: dict = Body(...)):
    """保存前端表格的列显示配置"""
    repo = request.app.state.repo
    columns = body.get("signals_table_columns", {})
    import json

    await repo.set_secret("preferences_view_columns", json.dumps(columns))
    return {"status": "success"}


# ==========================================
# 4.5 配置管理子接口 (Config Sub-APIs)
# ==========================================
@app.get("/api/config/system")
async def get_system_config(request: Request):
    """
    获取系统配置
    返回系统启用状态、活跃币种、监控周期等基础配置
    """
    repo = request.app.state.repo
    config_service = ConfigService(repo)

    try:
        data = await config_service.get_system_config()
        return _create_response(data)
    except Exception as e:
        logger.error(f"系统配置获取失败：{e}")
        raise HTTPException(status_code=500, detail=f"系统配置获取失败：{str(e)}")


@app.get("/api/config/symbols")
async def get_symbols_config(request: Request):
    """
    获取币种配置
    返回当前监控的交易对列表
    """
    repo = request.app.state.repo
    config_service = ConfigService(repo)

    try:
        data = await config_service.get_symbols_config()
        return _create_response(data)
    except Exception as e:
        logger.error(f"币种配置获取失败：{e}")
        raise HTTPException(status_code=500, detail=f"币种配置获取失败：{str(e)}")


@app.get("/api/config/monitor")
async def get_monitor_config(request: Request):
    """
    获取监控周期配置
    返回各时间周期的监控设置
    """
    repo = request.app.state.repo
    config_service = ConfigService(repo)

    try:
        data = await config_service.get_monitor_config()
        return _create_response(data)
    except Exception as e:
        logger.error(f"监控配置获取失败：{e}")
        raise HTTPException(status_code=500, detail=f"监控配置获取失败：{str(e)}")


class MonitorConfigReq(BaseModel):
    """监控配置更新请求体"""
    active_symbols: Optional[List[str]] = None
    monitor_intervals: Optional[Dict[str, Any]] = None


@app.put("/api/config/monitor")
async def update_monitor_config(request: Request, req: MonitorConfigReq):
    """
    更新监控配置
    支持热更新活跃币种列表和监控周期
    """
    repo = request.app.state.repo
    engine = request.app.state.engine
    config_service = ConfigService(repo)

    update_data = req.model_dump(exclude_unset=True)

    try:
        # 更新引擎内存中的配置
        if "active_symbols" in update_data:
            engine.active_symbols = update_data["active_symbols"]
        if "monitor_intervals" in update_data:
            new_intervals = {
                k: IntervalConfig(use_trend_filter=v.get("use_trend_filter", False))
                for k, v in update_data["monitor_intervals"].items()
            }
            engine.monitor_intervals = new_intervals

        data = await config_service.update_monitor_config(update_data)
        return _create_response(data, message="监控配置已热更新")
    except ConfigValidationError as e:
        logger.warning(f"监控配置校验失败：{e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"监控配置更新失败：{e}")
        raise HTTPException(status_code=500, detail=f"监控配置更新失败：{str(e)}")


@app.get("/api/config/risk")
async def get_risk_config(request: Request):
    """
    获取风控配置
    返回风险百分比、最大止损距离、最大杠杆等配置
    """
    repo = request.app.state.repo
    engine = request.app.state.engine
    config_service = ConfigService(repo)

    try:
        from core.entities import RiskConfig as RiskConfigEntity
        data = await config_service.get_risk_config(engine.risk_config if hasattr(engine, 'risk_config') else None)
        return _create_response(data)
    except Exception as e:
        logger.error(f"风控配置获取失败：{e}")
        raise HTTPException(status_code=500, detail=f"风控配置获取失败：{str(e)}")


class RiskConfigReq(BaseModel):
    """风控配置更新请求体"""
    risk_pct: Optional[float] = Field(None, ge=0.005, le=0.1)
    max_sl_dist: Optional[float] = Field(None, ge=0.01, le=0.1)
    max_leverage: Optional[float] = Field(None, ge=1.0, le=125.0)
    max_positions: Optional[int] = Field(None, ge=1, le=10)


@app.put("/api/config/risk")
async def update_risk_config(request: Request, req: RiskConfigReq):
    """
    更新风控配置
    支持热更新风险百分比、最大止损距离、最大杠杆等参数
    """
    repo = request.app.state.repo
    engine = request.app.state.engine
    config_service = ConfigService(repo)

    update_data = req.model_dump(exclude_unset=True)

    # 更新引擎内存中的配置
    if "risk_pct" in update_data:
        engine.risk_config.risk_pct = update_data["risk_pct"]
    if "max_sl_dist" in update_data:
        engine.risk_config.max_sl_dist = update_data["max_sl_dist"]
    if "max_leverage" in update_data:
        engine.risk_config.max_leverage = update_data["max_leverage"]
    if "max_positions" in update_data:
        engine.risk_config.max_positions = update_data["max_positions"]

    try:
        data = await config_service.update_risk_config(update_data)
        return _create_response(data, message="风控配置已热更新")
    except Exception as e:
        logger.error(f"风控配置更新失败：{e}")
        raise HTTPException(status_code=500, detail=f"风控配置更新失败：{str(e)}")


@app.get("/api/config/scoring")
async def get_scoring_config_new(request: Request):
    """
    获取打分配置
    返回打分模式、参数和权重配置
    """
    repo = request.app.state.repo
    config_service = ConfigService(repo)

    try:
        data = await config_service.get_scoring_config()
        return _create_response(data)
    except Exception as e:
        logger.error(f"打分配置获取失败：{e}")
        raise HTTPException(status_code=500, detail=f"打分配置获取失败：{str(e)}")


@app.put("/api/config/scoring")
async def update_scoring_config_new(request: Request, req: ScoringConfigReq):
    """
    更新打分配置
    支持热更新打分配置，包括模式切换、参数调整和权重配置
    """
    repo = request.app.state.repo
    engine = request.app.state.engine
    config_service = ConfigService(repo)

    # 获取当前配置作为基础
    current_config_json = await repo.get_secret("scoring_config")
    if current_config_json:
        try:
            current_data = json.loads(current_config_json)
        except json.JSONDecodeError:
            current_data = {}
    else:
        current_data = {}

    # 构建新的配置数据（只更新传入的字段）
    update_data = req.model_dump(exclude_unset=True)

    # 合并配置
    new_data = {**current_data, **update_data}

    # 验证权重总和并自动修复
    w_shape = new_data.get("w_shape", 0.4)
    w_trend = new_data.get("w_trend", 0.3)
    w_vol = new_data.get("w_vol", 0.3)
    total = round(w_shape + w_trend + w_vol, 4)

    # 检查是否有三个权重都被设置（无论是从现有配置还是更新数据）
    all_weights_present = ("w_shape" in new_data and "w_trend" in new_data and "w_vol" in new_data)

    if all_weights_present and abs(total - 1.0) > 0.0001:
        # 检查是否只有单个权重被更新
        weight_updates = {k: v for k, v in update_data.items() if k in ["w_shape", "w_trend", "w_vol"]}

        if len(weight_updates) == 1:
            # 单个权重更新，自动重新平衡其他两个权重
            updated_key = list(weight_updates.keys())[0]
            updated_value = weight_updates[updated_key]

            other_keys = ["w_shape", "w_trend", "w_vol"]
            other_keys.remove(updated_key)

            other_weights_sum = current_data.get(other_keys[0], 0.3) + current_data.get(other_keys[1], 0.3)
            remaining_weight = 1 - updated_value

            if other_weights_sum == 0:
                new_data[other_keys[0]] = remaining_weight / 2
                new_data[other_keys[1]] = remaining_weight / 2
            else:
                ratio0 = current_data.get(other_keys[0], 0.3) / other_weights_sum
                new_data[other_keys[0]] = remaining_weight * ratio0
                new_data[other_keys[1]] = remaining_weight * (1 - ratio0)

            # 重新计算总和进行验证
            w_shape = new_data.get("w_shape", 0.4)
            w_trend = new_data.get("w_trend", 0.3)
            w_vol = new_data.get("w_vol", 0.3)
            total = round(w_shape + w_trend + w_vol, 4)
            logger.info(f"自动平衡权重：{updated_key}={updated_value}, 新总和={total}")

        elif len(update_data) > 0 and len(weight_updates) == 0:
            # 没有权重更新但权重总和不对，说明是旧配置有问题，自动修复
            if total > 0:
                new_data["w_shape"] = round(w_shape / total, 4)
                new_data["w_trend"] = round(w_trend / total, 4)
                new_data["w_vol"] = round(w_vol / total, 4)
                logger.info(f"修正旧配置权重：原总和={total}, 新权重={new_data['w_shape']},{new_data['w_trend']},{new_data['w_vol']}")
            else:
                # 极端情况：所有权重都为 0，使用默认值
                new_data["w_shape"] = 0.4
                new_data["w_trend"] = 0.3
                new_data["w_vol"] = 0.3
                logger.info("权重配置异常，重置为默认值")

        else:
            # 多个权重同时更新或非法更新，抛出错误
            raise HTTPException(
                status_code=400,
                detail=f"权重总和必须等于 1.0，当前总和为：{total}。请调整权重配置。"
            )

    # 验证模式
    mode = new_data.get("mode", "classic")
    if mode not in ["classic", "progressive", "custom"]:
        raise HTTPException(
            status_code=400,
            detail=f"未知的打分模式：{mode}，可用模式：['classic', 'progressive', 'custom']"
        )

    # 保存到数据库
    await repo.set_secret("scoring_config", json.dumps(new_data))

    # 更新引擎内存中的配置
    try:
        from domain.strategy.scoring_config import ScoringConfig as ScoringConfigEntity
        engine.scoring_config = ScoringConfigEntity(**new_data)
        # 同时更新 weights 引擎（策略实际使用的是 engine.weights）
        engine.weights = ScoringWeights(
            w_shape=new_data.get("w_shape", 0.4),
            w_trend=new_data.get("w_trend", 0.3),
            w_vol=new_data.get("w_vol", 0.3)
        )
    except ValueError as e:
        # 如果验证失败，回滚并使用默认配置
        logger.error(f"配置验证失败：{e}")
        engine.scoring_config = ScoringConfigEntity()
        engine.weights = ScoringWeights(w_shape=0.4, w_trend=0.3, w_vol=0.3)

    return {
        "status": "success",
        "data": {
            "mode": new_data.get("mode", "classic"),
            "w_shape": new_data.get("w_shape", 0.4),
            "w_trend": new_data.get("w_trend", 0.3),
            "w_vol": new_data.get("w_vol", 0.3),
        },
        "meta": {
            "timestamp": int(time.time() * 1000),
            "message": "打分配置已热更新"
        }
    }


@app.get("/api/config/pinbar")
async def get_pinbar_config(request: Request):
    """
    获取 Pinbar 策略配置
    返回 Pinbar 形态识别参数
    """
    repo = request.app.state.repo
    config_service = ConfigService(repo)

    try:
        engine = request.app.state.engine
        data = await config_service.get_pinbar_config(engine.pinbar_config if hasattr(engine, 'pinbar_config') else None)
        return _create_response(data)
    except Exception as e:
        logger.error(f"Pinbar 配置获取失败：{e}")
        raise HTTPException(status_code=500, detail=f"Pinbar 配置获取失败：{str(e)}")


@app.put("/api/config/pinbar")
async def update_pinbar_config(request: Request, req: PinbarConfigReq):
    """
    更新 Pinbar 配置
    支持热更新 Pinbar 形态识别参数
    """
    repo = request.app.state.repo
    engine = request.app.state.engine
    config_service = ConfigService(repo)

    update_data = req.model_dump(exclude_unset=True)

    # 更新引擎内存中的配置
    if "body_max_ratio" in update_data:
        engine.pinbar_config.body_max_ratio = update_data["body_max_ratio"]
    if "shadow_min_ratio" in update_data:
        engine.pinbar_config.shadow_min_ratio = update_data["shadow_min_ratio"]
    if "volatility_atr_multiplier" in update_data:
        engine.pinbar_config.volatility_atr_multiplier = update_data["volatility_atr_multiplier"]
    if "doji_threshold" in update_data:
        engine.pinbar_config.doji_threshold = update_data["doji_threshold"]
    if "doji_shadow_bonus" in update_data:
        engine.pinbar_config.doji_shadow_bonus = update_data["doji_shadow_bonus"]
    if "mtf_trend_filter_mode" in update_data:
        engine.pinbar_config.mtf_trend_filter_mode = update_data["mtf_trend_filter_mode"]
    if "dynamic_sl_enabled" in update_data:
        engine.pinbar_config.dynamic_sl_enabled = update_data["dynamic_sl_enabled"]
    if "dynamic_sl_base" in update_data:
        engine.pinbar_config.dynamic_sl_base = update_data["dynamic_sl_base"]
    if "dynamic_sl_atr_multiplier" in update_data:
        engine.pinbar_config.dynamic_sl_atr_multiplier = update_data["dynamic_sl_atr_multiplier"]

    try:
        data = await config_service.update_pinbar_config(update_data)
        return _create_response(data, message="Pinbar 配置已热更新")
    except Exception as e:
        logger.error(f"Pinbar 配置更新失败：{e}")
        raise HTTPException(status_code=500, detail=f"Pinbar 配置更新失败：{str(e)}")






# ==========================================
# 5. 打分配置管理 (Scoring Config) - 保留旧接口兼容性
# ==========================================
# 注意：/api/config/scoring 接口已在上面第 4.5 节实现
# 此处保留原有接口逻辑以保持向后兼容

    # 验证模式
    mode = new_data.get("mode", "classic")
    if mode not in ["classic", "progressive", "custom"]:
        raise HTTPException(
            status_code=400,
            detail=f"未知的打分模式：{mode}，可用模式：['classic', 'progressive', 'custom']"
        )

    # 保存到数据库
    await repo.set_secret("scoring_config", json.dumps(new_data))

    # 更新引擎内存中的配置
    try:
        from domain.strategy.scoring_config import ScoringConfig as ScoringConfigEntity
        engine.scoring_config = ScoringConfigEntity(**new_data)
    except ValueError as e:
        # 如果验证失败，回滚并使用默认配置
        logger.error(f"配置验证失败：{e}")
        engine.scoring_config = ScoringConfigEntity()

    return {
        "status": "success",
        "data": {
            "mode": new_data.get("mode", "classic"),
            "w_shape": new_data.get("w_shape", 0.4),
            "w_trend": new_data.get("w_trend", 0.3),
            "w_vol": new_data.get("w_vol", 0.3),
        },
        "meta": {
            "timestamp": int(time.time() * 1000),
            "message": "打分配置已热更新"
        }
    }


@app.post("/api/config/scoring/preview")
async def preview_scoring_score(request: Request, req: ScorePreviewRequest = Body(...)):
    """
    分数预览接口

    基于指定配置和历史 K 线数据，重算最近 N 条 K 线的分数分布。
    用于前端展示配置调整后的效果预览。
    """
    engine = request.app.state.engine
    repo = request.app.state.repo

    try:
        # 构建 ScoringConfig 实例
        config = ScoringConfig(**req.config)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"配置验证失败：{str(e)}"
        )

    # 获取策略实例
    try:
        strategy = ScoringStrategyFactory.get_strategy(config.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 从数据库获取历史信号进行重算（简化版本：返回模拟数据）
    # 实际实现需要：
    # 1. 从 Binance API 获取 K 线数据
    # 2. 遍历 K 线调用 strategy.calculate
    # 3. 统计分数分布

    # 模拟数据（实际项目中需要从数据库或 API 获取真实数据）
    score_distribution = {
        "0-20": 5,
        "20-40": 8,
        "40-60": 12,
        "60-80": 15,
        "80-100": 5
    }

    tier_distribution = {
        "A": 3,
        "B": 10,
        "C": 12,
        "REJECTED": 20
    }

    sample_signals = [
        {
            "timestamp": 1741000000000,
            "direction": "LONG",
            "score": 85,
            "shape_score": 88,
            "trend_score": 82,
            "vol_score": 75,
            "quality_tier": "A"
        },
        {
            "timestamp": 1741003600000,
            "direction": "SHORT",
            "score": 65,
            "shape_score": 70,
            "trend_score": 60,
            "vol_score": 55,
            "quality_tier": "B"
        }
    ]

    return {
        "status": "success",
        "data": {
            "total_bars": req.limit,
            "signals_found": 45,
            "score_distribution": score_distribution,
            "tier_distribution": tier_distribution,
            "sample_signals": sample_signals,
            "config_used": {
                "mode": config.mode,
                "w_shape": config.w_shape,
                "w_trend": config.w_trend,
                "w_vol": config.w_vol,
            }
        }
    }


# ==========================================
# 6. 推送配置管理 (Push Config)
# ==========================================
class PushConfigReq(BaseModel):
    """推送配置更新请求体（已废弃：推送配置请通过 .env 文件设置）"""
    # 已废弃：所有推送配置请通过 .env 文件设置
    global_push_enabled: Optional[bool] = None
    feishu_enabled: Optional[bool] = None
    feishu_webhook_url: Optional[str] = None
    wecom_enabled: Optional[bool] = None
    wecom_webhook_url: Optional[str] = None






# ==========================================
# 7. 交易所配置管理 (Exchange Config)
# ==========================================

@app.post("/api/push/test")
async def test_push_notification(request: Request, channel: str = "wecom"):
    """
    测试推送通知
    :param channel: 推送通道 (wecom, feishu, all)
    """
    # 注意：推送配置已从环境变量读取，不再支持通过 API 测试
    # 此接口仅用于测试连接性，实际推送请使用配置好的环境变量
    return {"status": "info", "message": "推送配置已改为从 .env 文件读取，请查看日志确认推送状态"}


class ExchangeConfigReq(BaseModel):
    """交易所配置更新请求体"""
    binance_api_key: Optional[str] = Field(None, min_length=1)
    binance_api_secret: Optional[str] = Field(None, min_length=1)
    use_testnet: Optional[bool] = None






# ==========================================
# 8. 配置导入导出 (Config Import/Export)
# ==========================================
import os
import yaml
from datetime import datetime

from domain.services.config_service import ConfigValidationError

@app.post("/api/config/export")
async def export_config(request: Request):
    """
    导出配置为 YAML 文件
    敏感字段（binance_api_key、binance_api_secret、feishu_webhook_url、wecom_webhook_url）会被置空
    """
    repo = request.app.state.repo
    config_service = ConfigService(repo)

    try:
        # 获取所有配置
        all_config = await config_service.get_all_config_for_export()

        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = "config"
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, f"exported_config_{timestamp}.yaml")

        # 写入 YAML 文件
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(all_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        logger.info(f"配置已导出：{file_path}")

        return _create_response({
            "file_path": file_path,
            "exported_at": timestamp,
        }, message=f"配置已导出到 {file_path}")

    except Exception as e:
        logger.error(f"配置导出失败：{e}")
        raise HTTPException(status_code=500, detail=f"配置导出失败：{str(e)}")


@app.post("/api/config/import")
async def import_config(
    request: Request,
    file: Optional[UploadFile] = File(None),
    yaml_content: Optional[str] = Form(None)
):
    """
    从 YAML 导入配置
    支持文件上传或直接传入 yaml_content
    支持导入所有配置项，包括 binance_api_key、binance_api_secret、feishu_webhook_url、wecom_webhook_url
    """
    repo = request.app.state.repo
    engine = request.app.state.engine
    config_service = ConfigService(repo)

    content = yaml_content

    # 如果上传了文件，读取文件内容
    if file:
        if not file.filename or not (file.filename.endswith(".yaml") or file.filename.endswith(".yml")):
            raise HTTPException(status_code=400, detail="文件格式错误，请上传 .yaml 或 .yml 文件")
        try:
            file_bytes = await file.read()
            content = file_bytes.decode("utf-8")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"读取文件失败：{str(e)}")

    if not content:
        raise HTTPException(status_code=400, detail="yaml_content 或 file 必须提供一个")

    try:
        # 解析 YAML
        config = yaml.safe_load(content)
        if not isinstance(config, dict):
            raise ValueError("YAML 内容必须是字典格式")

        # 校验并导入配置
        imported_config = await config_service.import_config_from_yaml(config, engine)

        logger.info("配置导入成功")

        return _create_response({
            "imported_config": imported_config,
        }, message="配置导入成功")

    except ConfigValidationError as e:
        logger.warning(f"配置校验失败：{e}")
        raise HTTPException(status_code=400, detail=str(e))

    except yaml.YAMLError as e:
        logger.error(f"YAML 解析失败：{e}")
        raise HTTPException(status_code=400, detail=f"YAML 格式错误：{str(e)}")

    except ValueError as e:
        logger.error(f"配置验证失败：{e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"配置导入失败：{e}")
        raise HTTPException(status_code=500, detail=f"配置导入失败：{str(e)}")
