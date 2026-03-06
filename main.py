"""
系统统一入口 (Entrypoint)
实例化并编排所有依赖 (Dependency Injection)，将调度器挂载于 FastAPI 生命周期之中后台执行。
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI
import uvicorn

# 引入环境配置加载模块
from infrastructure.config.env_loader import load_env, validate_required_config, get_binance_config, get_push_config

# 引入领域策略层与风控
from domain.strategy.pinbar import PinbarStrategy
from domain.risk.sizer import PositionSizer

# 引入基础设施的各个底层驱动外设
from infrastructure.feed.binance_ws import BinanceWSFeed
from infrastructure.reader.binance_api import BinanceAccountReader
from infrastructure.notify.feishu import FeishuNotifier
from infrastructure.notify.wecom import WeComNotifier
from infrastructure.notify.broadcaster import NotificationBroadcaster
from infrastructure.repo.sqlite_repo import SQLiteRepo

# 引入核心调配中间层
from application.monitor_engine import CryptoRadarEngine

# 引入原有的 Web API
from web.api import app

# 设置全局纯净日志格式
LOG_DIR = os.getenv("LOG_DIR")
if LOG_DIR is None:
    LOG_DIR = "logs" if os.path.isdir("logs") else "."
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "backend.log"), encoding="utf-8")
    ]
)

# 数据库路径配置
DB_DIR = os.getenv("DB_DIR")
if DB_DIR is None:
    DB_DIR = "."
DB_PATH = os.path.join(DB_DIR, "radar.db")

# 保存挂载后台任务的对象以便控制
engine_task = None


def assemble_engine() -> CryptoRadarEngine:
    """依赖注入编排：将零散的组件拼接成强劲的业务引擎"""

    logger = logging.getLogger(__name__)

    # 加载环境变量并验证必填配置
    load_env()
    try:
        validate_required_config()
        logger.info("环境变量验证通过")
    except ValueError as e:
        logger.error(f"配置验证失败：{e}")
        raise

    # 实例化领域大脑
    strategy = PinbarStrategy(ema_period=60, atr_period=14)
    risk_sizer = PositionSizer()

    # 实例化数据与访问源
    feed = BinanceWSFeed(ws_url="wss://fstream.binance.com/ws")

    # 从环境变量读取币安 API 配置
    api_key, api_secret = get_binance_config()
    account_reader = BinanceAccountReader(
        api_key=api_key,
        api_secret=api_secret,
    )
    logger.info(f"币安 API 配置已加载 (API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 4 else '****'})")

    repo = SQLiteRepo(DB_PATH)

    # 获取推送配置
    push_config = get_push_config()
    logger.info(f"推送配置：全局={'开启' if push_config['global_enabled'] else '关闭'}, "
                f"飞书={'开启' if push_config['feishu']['enabled'] else '关闭'}, "
                f"企业微信={'开启' if push_config['wecom']['enabled'] else '关闭'}")

    # 实例化推送通知器（不再包含 Telegram）
    feishu = FeishuNotifier()  # 不再需要 repo 参数
    wecom = WeComNotifier()  # 不再需要 repo 参数

    broadcaster = NotificationBroadcaster()
    broadcaster.register(feishu).register(wecom)

    # 整体装填引擎
    engine = CryptoRadarEngine(
        feed=feed,
        account_reader=account_reader,
        repo=repo,
        notifier=broadcaster,
        strategy=strategy,
        risk_sizer=risk_sizer,
        active_symbols=["ETHUSDT"],
        interval="1h",
    )

    return engine


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    FastAPI 的生命周期管理。
    启动时，在后台调度引擎的大循环。关闭时释放资源。
    """
    global engine_task

    engine = assemble_engine()

    # 挂载状态用于 API 层路由取用
    fastapi_app.state.engine = engine
    fastapi_app.state.repo = engine.repo

    # 确立数据库基础设施，如果还未建立表结构
    await engine.repo.init_db()

    # 不再从数据库加载 Binance 密钥（已改为环境变量）
    # 不再从数据库加载推送配置（已改为环境变量）

    # 加载保存在数据库中的用户组合币种，如果不为空则覆盖默认配置
    saved_symbols_json = await engine.repo.get_secret("active_symbols")
    if saved_symbols_json:
        try:
            saved_symbols = json.loads(saved_symbols_json)
            if isinstance(saved_symbols, list) and len(saved_symbols) > 0:
                engine.active_symbols = saved_symbols
        except Exception as e:
            logging.error(f"无法解析数据中的 active_symbols 配置：{e}")

    # 读取配置：监听周期及其各自的配置
    monitor_intervals_json = await engine.repo.get_secret("monitor_intervals")
    if monitor_intervals_json:
        try:
            intervals = json.loads(monitor_intervals_json)
            from core.entities import IntervalConfig

            if isinstance(intervals, list) and len(intervals) > 0:
                engine.monitor_intervals = {ivl: IntervalConfig() for ivl in intervals}
            elif isinstance(intervals, dict) and len(intervals) > 0:
                parsed_intervals = {}
                for k, v in intervals.items():
                    parsed_intervals[k] = (
                        IntervalConfig(**v) if isinstance(v, dict) else IntervalConfig()
                    )
                engine.monitor_intervals = parsed_intervals
        except Exception as e:
            logging.error(f"无法解析数据中的 monitor_intervals 配置：{e}")
            from core.entities import IntervalConfig

            engine.monitor_intervals = {
                "15m": IntervalConfig(),
                "1h": IntervalConfig(),
                "4h": IntervalConfig(),
            }
    else:
        from core.entities import IntervalConfig

        engine.monitor_intervals = {
            "15m": IntervalConfig(),
            "1h": IntervalConfig(),
            "4h": IntervalConfig(),
        }

    # 读取配置：Pinbar 策略形态参数
    pinbar_config_json = await engine.repo.get_secret("pinbar_config")
    if pinbar_config_json:
        try:
            from core.entities import PinbarConfig

            pinbar_data = json.loads(pinbar_config_json)
            engine.pinbar_config = PinbarConfig(**pinbar_data)
        except Exception as e:
            logging.error(f"无法解析数据中的 pinbar_config 配置：{e}")

    # 实例化历史 K 线分片采集器与历史信号扫描引擎
    from infrastructure.feed.binance_kline_fetcher import BinanceKlineFetcher
    from application.history_scanner import HistoryScanner

    kline_fetcher = BinanceKlineFetcher()
    history_scanner = HistoryScanner(
        strategy=engine.strategy,
        repo=engine.repo,
        notifier=engine.notifier,
        kline_fetcher=kline_fetcher,
        engine=engine,
    )
    fastapi_app.state.history_scanner = history_scanner

    # 实例化 K 线图表数据聚合服务
    from application.chart_service import ChartService

    chart_service = ChartService(kline_fetcher=kline_fetcher, db_path=DB_PATH)
    fastapi_app.state.chart_service = chart_service

    # 注册信号查询服务（应用层）
    from application.signal_query_service import SignalQueryService
    fastapi_app.state.signal_query_service = SignalQueryService(engine.repo)

    # 注册持仓服务（应用层）
    from application.position_service import PositionService
    fastapi_app.state.position_service = PositionService(engine.account_reader, engine.repo)

    # 不阻塞地在后台事件循环中拉起监察大循环
    engine_task = asyncio.create_task(engine.start())

    yield

    # 当收到 Ctrl+C 或者终止信号时的资源清理退格
    if engine_task:
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass
        logging.info("后台调度器引擎已平滑关机终止。")


# 重新绑定生命周期至前一阶段导入的 app
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    # 从环境变量读取端口配置
    port = int(os.getenv("BACKEND_PORT", "8000"))
    # 使用 Uvicorn 运行
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
