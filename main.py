"""
系统统一入口 (Entrypoint)
实例化并编排所有依赖 (Dependency Injection)，将调度器挂载于 FastAPI 生命周期之中后台执行。
"""

import asyncio
import logging
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI
import uvicorn

# 引入领域策略层与风控
from domain.strategy.pinbar import PinbarStrategy
from domain.risk.sizer import PositionSizer

# 引入基础设施的各个底层驱动外设
from infrastructure.feed.binance_ws import BinanceWSFeed
from infrastructure.reader.binance_api import BinanceAccountReader
from infrastructure.notify.feishu import FeishuNotifier
from infrastructure.notify.telegram import TelegramNotifier
from infrastructure.notify.wecom import WeComNotifier
from infrastructure.notify.broadcaster import NotificationBroadcaster
from infrastructure.repo.sqlite_repo import SQLiteRepo

# 引入核心调配中间层
from application.monitor_engine import CryptoRadarEngine

# 引入原有的 Web API
# 由于你已实现了 web/api.py 中的 app，我们这里选择对其生命周期进行扩展式修改或者直接原封不动集成
# 为了做到无缝对接本文件要求，我们在这里重新配置并引入路由 (为简化起见直接覆盖初始化即可)
from web.api import app

# 设置全局纯净日志格式
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

# 保存挂载后台任务的对象以便控制
engine_task = None


def assemble_engine() -> CryptoRadarEngine:
    """依赖注入编排：将零散的组件拼接成强劲的业务引擎"""

    # 实例化领域大脑
    strategy = PinbarStrategy(ema_period=60, atr_period=14)
    risk_sizer = PositionSizer()

    # 实例化数据与访问源
    feed = BinanceWSFeed(ws_url="wss://fstream.binance.com/ws")

    # !注意: 实际部署时 API Key 等需从环境变量或安全存储库读取，不要明文写入
    account_reader = BinanceAccountReader(
        api_key="your_readonly_binance_api_key",
        api_secret="your_readonly_binance_api_secret",
    )

    repo = SQLiteRepo("radar.db")

    # 实例化推流发送阵列与组合广播器
    feishu = FeishuNotifier(repo=repo)
    telegram = TelegramNotifier(repo=repo)
    wecom = WeComNotifier(repo=repo)

    broadcaster = NotificationBroadcaster()
    broadcaster.register(feishu).register(telegram).register(wecom)

    # 整体装填引擎
    engine = CryptoRadarEngine(
        feed=feed,
        account_reader=account_reader,
        repo=repo,
        notifier=broadcaster,
        strategy=strategy,
        risk_sizer=risk_sizer,
        active_symbols=["ETHUSDT"],  # Default, will be overwritten in lifespan
        interval="1h",  # Default, will be overwritten in lifespan
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

    # 尝试从数据库加载 Binance 密钥以覆盖默认占位符
    api_key = await engine.repo.get_secret("binance_api_key")
    api_secret = await engine.repo.get_secret("binance_api_secret")
    if api_key and api_secret:
        engine.account_reader.api_key = api_key
        engine.account_reader.api_secret = api_secret

    # 加载保存在数据库中的用户组合币种，如果不为空则覆盖默认配置
    saved_symbols_json = await engine.repo.get_secret("active_symbols")
    if saved_symbols_json:
        try:
            saved_symbols = json.loads(saved_symbols_json)
            if isinstance(saved_symbols, list) and len(saved_symbols) > 0:
                engine.active_symbols = saved_symbols
                # 重新初始化缓存字典
                engine.history_bars = {s.upper(): [] for s in engine.active_symbols}
        except Exception as e:
            logging.error(f"无法解析数据中的 active_symbols 配置: {e}")

    # 读取配置：监听周期及其各自的配置
    monitor_intervals_json = await engine.repo.get_secret("monitor_intervals")
    if monitor_intervals_json:
        try:
            intervals = json.loads(monitor_intervals_json)
            # 兼容老数据 list 形态，并向新版的 dict 平滑过渡
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
            logging.error(f"无法解析数据中的 monitor_intervals 配置: {e}")
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
            logging.error(f"无法解析数据中的 pinbar_config 配置: {e}")

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
    # 使用 Uvicorn 运行。这样就可以一边提供配置页面，一边在后台默默地 7x24 进行只读监听和风控告警工作了
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
