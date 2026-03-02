"""
Web API 模块
提供用于热更新风控参数、获取指标雷达数据与系统遥测的状态面板。
"""

import time
from typing import Optional, List, Dict
from fastapi import FastAPI, Request, Query, Body, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import httpx
import json
import logging
import dataclasses

from core.entities import SignalFilter, ScoringWeights, PinbarConfig, IntervalConfig
from infrastructure.reader.binance_api import BinanceAccountReader

logger = logging.getLogger(__name__)

# 初始化 FastAPI 实例
app = FastAPI(title="CryptoRadar API", description="系统动态配置中心及监控面板")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5176",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5176",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="web/static"), name="static")


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

    return {
        "is_connected": getattr(engine, "is_connected", False),
        "api_latency_ms": getattr(engine, "api_latency_ms", 0),
        "api_weight_usage": getattr(engine, "api_weight_usage", 0.0),
        "uptime": f"{days}d {hours}h {minutes}m",
    }


# ==========================================
# 1.5 交易所账户与持仓 (Dashboard)
# ==========================================
@app.get("/api/account/dashboard")
async def get_account_dashboard(request: Request):
    """获取真实账户余额和持仓列表。验证 Key 是否只读与有效。"""
    repo = request.app.state.repo
    api_key = await repo.get_secret("binance_api_key")
    api_secret = await repo.get_secret("binance_api_secret")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=400,
            detail="Binance API keys are not configured. Please set them in Settings.",
        )

    reader = BinanceAccountReader(api_key=api_key, api_secret=api_secret)
    try:
        balance = await reader.fetch_account_balance()
        return {
            "status": "success",
            "data": {
                "total_wallet_balance": balance.total_wallet_balance,
                "available_balance": balance.available_balance,
                "total_unrealized_pnl": balance.total_unrealized_pnl,
                "current_positions_count": balance.current_positions_count,
                "positions": balance.positions,
            },
        }
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code in [401, 403]:
            try:
                raw_msg = e.response.json().get("msg", "Unknown error")
            except:
                raw_msg = e.response.text
            raise HTTPException(
                status_code=status_code,
                detail=f"BINANCE API ERROR: Invalid API Key or IP not allowed. Ensure the key is Read-Only. ({raw_msg})",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch account data from Binance: {e.response.text}",
        )
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
        status_code = e.response.status_code
        if status_code in [401, 403]:
            try:
                raw_msg = e.response.json().get("msg", "Unknown error")
            except:
                raw_msg = e.response.text
            raise HTTPException(
                status_code=status_code, detail=f"BINANCE API ERROR: ({raw_msg})"
            )
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch position data: {e.response.text}"
        )
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
    sort_by: str = Query("timestamp", regex="^(timestamp|score)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    """分页、多维度历史信号检索接口"""
    repo = request.app.state.repo

    symbol_list = symbols.split(",") if symbols else None
    interval_list = intervals.split(",") if intervals else None
    direction_list = directions.split(",") if directions else None

    filter_params = SignalFilter(
        symbols=symbol_list,
        intervals=interval_list,
        directions=direction_list,
        start_time=start_time,
        end_time=end_time,
        min_score=min_score,
        sort_by=sort_by,
        order=order,
    )

    total, items = await repo.get_signals(filter_params, page, size)
    return {"total": total, "items": items}


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
async def get_chart_data(request: Request, symbol: str, interval: str = "1h", limit: int = 200):
    """
    获取指定交易对的 K 线 + 信号标记聚合数据 (TradingView 兼容格式)。
    内置 LRU 缓存，同一 symbol+interval 在一个 K 线周期内复用缓存。
    """
    chart_service = getattr(request.app.state, "chart_service", None)
    if not chart_service:
        raise HTTPException(status_code=503, detail="图表服务未初始化")

    try:
        data = await chart_service.get_chart_data(
            symbol=symbol,
            interval=interval,
            limit=limit,
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


class ConfigUpdateReq(BaseModel):
    system_enabled: Optional[bool] = None
    active_symbols: Optional[List[str]] = None
    monitor_intervals: Optional[Dict[str, IntervalConfigReq]] = None
    scoring_weights: Optional[ScoringWeightsConfig] = None
    exchange_settings: Optional[ExchangeSettingsConfig] = None
    webhook_settings: Optional[WebhookSettingsConfig] = None
    pinbar_config: Optional[PinbarConfigReq] = None
    auto_order_status: Optional[str] = (
        None  # 仅仅是为了接口兼容，后端将强行忽略该值的修改
    )


@app.get("/api/config")
async def get_config(request: Request):
    engine = request.app.state.engine
    repo = engine.repo

    # 真实情况下需查 DB 看 Secret 有没有
    wecom_enabled_val = await repo.get_secret("wecom_enabled")
    wecom_enabled = wecom_enabled_val.lower() == "true" if wecom_enabled_val else False

    global_push_enabled_val = await repo.get_secret("global_push_enabled")
    global_push_enabled = (
        global_push_enabled_val.lower() == "true" if global_push_enabled_val else True
    )  # 默认开启

    import dataclasses

    return {
        "system_enabled": engine.system_enabled,
        "active_symbols": engine.active_symbols,
        "monitor_intervals": {
            k: dataclasses.asdict(v) for k, v in engine.monitor_intervals.items()
        }
        if engine.monitor_intervals
        else {},
        "risk_config": {
            "risk_pct": engine.risk_pct,
            "max_sl_dist": engine.max_sl_dist,
            "max_leverage": engine.max_leverage,
        },
        "scoring_weights": {
            "w_shape": engine.weights.w_shape,
            "w_trend": engine.weights.w_trend,
            "w_vol": engine.weights.w_vol,
        },
        "exchange_settings": {"has_binance_key": True},
        "webhook_settings": {
            "global_push_enabled": global_push_enabled,
            "feishu_enabled": True,  # You might want to get this from DB too, but adapting contract for now
            "wecom_enabled": wecom_enabled,
            "has_feishu_secret": True,  # Mock logic based on contract
            "has_wecom_secret": bool(await repo.get_secret("wecom_secret")),
        },
        "pinbar_config": dataclasses.asdict(engine.pinbar_config)
        if engine.pinbar_config
        else {},
        "auto_order_status": "OFF",
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
        )
        await repo.set_secret(
            "pinbar_config", json.dumps(dataclasses.asdict(engine.pinbar_config))
        )

    if req.exchange_settings:
        if req.exchange_settings.binance_api_key:
            engine.account_reader.api_key = req.exchange_settings.binance_api_key
            await repo.set_secret(
                "binance_api_key", req.exchange_settings.binance_api_key
            )
        if req.exchange_settings.binance_api_secret:
            engine.account_reader.api_secret = req.exchange_settings.binance_api_secret
            await repo.set_secret(
                "binance_api_secret", req.exchange_settings.binance_api_secret
            )

    # 安全防线：忽视所有对 auto_order_status 的修改，保持后端处于零执行的只读模式
    if req.auto_order_status is not None:
        logger.warning(
            f"检测到试图修改 auto_order_status 为 {req.auto_order_status}，后端安全锁已拒绝该操作。"
        )

    # 涉及到数据库加密保存的落盘动作
    if req.webhook_settings:
        if req.webhook_settings.global_push_enabled is not None:
            await repo.set_secret(
                "global_push_enabled",
                str(req.webhook_settings.global_push_enabled).lower(),
            )

        if req.webhook_settings.feishu_enabled is not None:
            await repo.set_secret(
                "feishu_enabled", str(req.webhook_settings.feishu_enabled).lower()
            )

        if req.webhook_settings.feishu_secret is not None:
            # 兼容前端命名，feishu_secret 对应 backend 的 webhook_url
            await repo.set_secret(
                "feishu_webhook_url", req.webhook_settings.feishu_secret
            )

        if req.webhook_settings.wecom_enabled is not None:
            await repo.set_secret(
                "wecom_enabled", str(req.webhook_settings.wecom_enabled).lower()
            )

        if req.webhook_settings.wecom_secret is not None:
            # 兼容前端命名，wecom_secret 对应 backend 的 webhook_url
            await repo.set_secret(
                "wecom_webhook_url", req.webhook_settings.wecom_secret
            )

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
