"""
scripts/history_test_eth.py
历史数据回溯测试脚本
用于拉取过去 7 天的 1h K 线，并喂入策略引擎验证信号触发率及推送排版。
"""

import asyncio
import logging
from datetime import datetime
import httpx

from core.entities import Bar, ScoringWeights, AccountBalance, PinbarConfig
from domain.strategy.pinbar import PinbarStrategy
from domain.risk.sizer import PositionSizer
from infrastructure.repo.sqlite_repo import SQLiteRepo
from infrastructure.notify.broadcaster import NotificationBroadcaster
from infrastructure.notify.wecom import WeComNotifier
from infrastructure.notify.feishu import FeishuNotifier
from infrastructure.notify.telegram import TelegramNotifier

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("HistoryTest")


async def fetch_klines(symbol: str, interval: str, limit: int):
    # 使用生产网 URL
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()


class ForceNotifyWeCom(WeComNotifier):
    """一个特制的企微推送器，忽略数据库开关，强制发送"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send_markdown(self, formatted_message: str) -> None:
        if not self.webhook_url:
            return
        payload = {"msgtype": "markdown", "markdown": {"content": formatted_message}}
        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json=payload)


class ForceNotifyFeishu(FeishuNotifier):
    """强制发送飞书"""

    async def send_markdown(self, formatted_message: str) -> None:
        if not self.webhook_url or "xxx" in self.webhook_url:
            return
        await super().send_markdown(formatted_message)


async def run_history_test():
    logger.info("开始拉取 Binance ETHUSDT 历史 K 线数据 (生产网)...")

    intervals_to_test = ["15m", "1h"]
    all_bars_by_interval = {}

    # 获取必要的全部 K 线（包括用于 MTF 校验的高级别 K 线）
    required_intervals = set(intervals_to_test)
    # 模拟引擎逻辑：如果开启了趋势过滤，则需要更高一级别的 K 线
    # 15m -> 1h, 1h -> 4h
    required_intervals.add("4h")  # 1h 的高级别
    # for 15m -> 1h is already in intervals_to_test

    for ivl in required_intervals:
        limit = 168 + 60
        if ivl == "15m":
            limit = 672 + 60
        elif ivl == "4h":
            limit = 42 + 60

        klines_data = await fetch_klines("ETHUSDT", ivl, limit)
        bars = []
        for k in klines_data:
            bars.append(
                Bar(
                    symbol="ETHUSDT",
                    interval=ivl,
                    timestamp=k[0],
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                    is_closed=True,
                )
            )
        all_bars_by_interval[ivl] = bars
        logger.info(f"成功拉取 {ivl} 级别 {len(bars)} 根 K 线。")

    repo = SQLiteRepo("radar.db")
    await repo.init_db()

    strategy = PinbarStrategy(ema_period=60, atr_period=14)
    risk_sizer = PositionSizer()
    weights = ScoringWeights(w_shape=0.4, w_trend=0.4, w_vol=0.2)
    mock_account = AccountBalance(
        total_wallet_balance=10000.0,
        available_balance=10000.0,
        current_positions_count=0,
        positions=[],
    )

    # 获取真实 Webhook，并绕过全局开关强制装载 (在本测试中直接用重构后的动态推送器)
    broadcaster = NotificationBroadcaster()

    # 注册所有推送器，它们会自动从 repo 获取配置并检查开关
    broadcaster.register(FeishuNotifier(repo=repo))
    broadcaster.register(TelegramNotifier(repo=repo))
    broadcaster.register(WeComNotifier(repo=repo))

    logger.info("已装载所有动态推送器，将根据数据库中的开关状态尝试发送信号推送。")

    # 从数据库读取最新的 Pinbar 策略参数
    pinbar_config = PinbarConfig()  # 默认值
    pinbar_config_json = await repo.get_secret("pinbar_config")
    if pinbar_config_json:
        import json

        try:
            pinbar_data = json.loads(pinbar_config_json)
            pinbar_config = PinbarConfig(**pinbar_data)
            logger.info(f"成功加载动态 Pinbar 配置: {pinbar_config}")
        except Exception as e:
            logger.error(f"加载 Pinbar 配置失败，使用默认值: {e}")
    else:
        logger.info("未发现自定义 Pinbar 配置，使用系统默认值。")

    # 读取周期配置
    from core.entities import IntervalConfig
    import json

    interval_configs = {
        "15m": IntervalConfig(),
        "1h": IntervalConfig(),
        "4h": IntervalConfig(),
    }
    val = await repo.get_secret("monitor_intervals")
    if val:
        try:
            data = json.loads(val)
            for k, v in data.items():
                interval_configs[k] = IntervalConfig(**v)
            logger.info(f"成功加载周期配置: {interval_configs}")
        except:
            pass

    # 定义 MTF 映射
    mtf_map = {"15m": "1h", "1h": "4h"}
    max_test_sl_dist = 0.035

    signals_found = []

    for ivl, bars in all_bars_by_interval.items():
        # 预先计算高级别趋势（如果需要）
        higher_ivl = mtf_map.get(ivl)
        use_mtf = interval_configs.get(ivl, IntervalConfig()).use_trend_filter

        logger.info(f"开始回测 {ivl}... 趋势过滤状态: {use_mtf} (参考: {higher_ivl})")

        for current_idx in range(60, len(bars)):
            current_bar = bars[current_idx]
            history_bars = bars[current_idx - 60 : current_idx]

            higher_trend = None
            if use_mtf and higher_ivl in all_bars_by_interval:
                # 寻找高级别中与当前时间戳最接近的闭合 K 线
                h_bars = all_bars_by_interval[higher_ivl]
                # 找到所有 timestamp <= current_bar.timestamp 的 h_bars
                valid_h_bars = [
                    b for b in h_bars if b.timestamp <= current_bar.timestamp
                ]
                if len(valid_h_bars) >= 60:
                    from domain.strategy.indicators import calculate_ema

                    h_closes = [b.close for b in valid_h_bars]
                    h_ema60 = calculate_ema(h_closes, 60)
                    last_h_close = valid_h_bars[-1].close
                    if last_h_close > h_ema60:
                        higher_trend = "LONG"
                    elif last_h_close < h_ema60:
                        higher_trend = "SHORT"

            signal = strategy.evaluate(
                current_bar=current_bar,
                history_bars=history_bars,
                max_sl_dist=max_test_sl_dist,
                weights=weights,
                higher_trend=higher_trend,
                pinbar_config=pinbar_config,
            )

            if signal:
                # 过滤出“今天”的信号 (假设 2026-02-28)
                # 或者直接保留所有信号，用户可以通过控制台看
                signals_found.append(signal)

                await repo.save_signal(signal)
                sizing = risk_sizer.calculate(signal, mock_account, 0.02, 20.0)
                await repo.save_position_sizing(sizing)

                timestamp_str = datetime.fromtimestamp(
                    signal.timestamp / 1000
                ).strftime("%Y-%m-%d %H:%M:%S")
                direction_emoji = (
                    "🟢 LONG" if signal.direction == "LONG" else "🔴 SHORT"
                )
                ema_status = (
                    "Price > EMA60" if signal.direction == "LONG" else "Price < EMA60"
                )
                display_score = round(signal.score / 10, 1)

                message = (
                    f"**🚨 【测试】最近7天历史信号 ({signal.reason})**\n"
                    f"---\n\n"
                    f"**项目**: #{signal.symbol.upper()}\n"
                    f"**周期**: {signal.interval} | **方向**: {direction_emoji}\n"
                    f"**时间**: {timestamp_str}\n\n"
                    f"**📊 核心参数**\n\n"
                    f"- 入场参考: `{signal.entry_price}`\n"
                    f"- 初始止损: `{signal.stop_loss}`\n"
                    f"- 预期 TP1: `{signal.take_profit_1}` (1.5R)\n\n"
                    f"**🔍 过滤指标**\n\n"
                    f"- EMA60 状态: {ema_status}\n"
                    f"- ADX 强度: `Active`\n"
                    f"- 形态评分: `{display_score}/10`\n\n"
                    f"**🛠️ 执行状态**\n\n"
                    f"- 自动下单: Read-Only (建议杠杆 {sizing.suggested_leverage:.1f}x)\n"
                    f"- 订单编号: `HIST-{signal.timestamp}`\n\n"
                    f"---\n"
                    f"*详情请访问 Web 控制台*"
                )
                logger.info(
                    f"历史发现: {timestamp_str} | 级别: {signal.interval} | 方向: {signal.direction} | 价格: {signal.entry_price}"
                )

                await broadcaster.send_markdown(message)

    print("\n" + "=" * 50)
    print("🎯 高级回溯测试报告 (生产网全周期)")
    print("=" * 50)
    if signals_found:
        avg_score = sum(s.score for s in signals_found) / len(signals_found)
        print(f"总计检测 15m, 1h 级别数据 (MTF 过滤按配置执行)")
        print(f"共识别到符合严格风控(<=3.5%)的 Pinbar 信号: {len(signals_found)} 个")
        for s in signals_found:
            ts = datetime.fromtimestamp(s.timestamp / 1000).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            print(
                f"- [{ts}] {s.interval}: {s.direction} @ {s.entry_price} (Score: {s.score})"
            )
        print(f"历史信号平均质量得分: {avg_score:.1f} / 100")
        print("\n提示：这些信号已存入 SQLite，去您的 Dashboard 就可以看到了。")
    else:
        print("总计检测 15m, 1h 级别数据")
        print(
            "在严格风控(<=3.5%)下，最近几天内未识别出满足当前策略的有效 Pinbar 信号。"
        )
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(run_history_test())
