"""
核心引擎应用层模块
负责编排获取数据 -> 计算信号 -> 取只读资产 -> 风控算仓 -> 入库 -> 广播的最上层流水线。
纯粹的调度器，不包含底层业务逻辑或具体的发单网络请求。
"""

import asyncio
import logging
from typing import List, Dict
from types import SimpleNamespace
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from core.interfaces import IDataFeed, IAccountReader, IRepository, INotifier
from domain.strategy.pinbar import PinbarStrategy
from domain.risk.sizer import PositionSizer
from domain.risk.portfolio_risk import PortfolioRiskService
from core.entities import Bar, ScoringWeights, RiskConfig
from domain.strategy.scoring_config import ScoringConfig
from core.exceptions import RiskLimitExceeded

logger = logging.getLogger(__name__)


class CryptoRadarEngine:
    """
    监控系统的主动力引擎 (The Engine)。
    组装了数据源、探针、仓储、推送器以及核心业务大脑。
    """

    def __init__(
        self,
        feed: IDataFeed,
        account_reader: IAccountReader,
        repo: IRepository,
        notifier: INotifier,
        strategy: PinbarStrategy,
        risk_sizer: PositionSizer,
        active_symbols: List[str] = None,
        interval: str = "1h",
    ):
        self.feed = feed
        self.account_reader = account_reader
        self.repo = repo
        self.notifier = notifier
        self.strategy = strategy
        self.risk_sizer = risk_sizer
        self.portfolio_risk_service = PortfolioRiskService()
        self.max_portfolio_risk_pct = 0.08  # 投资组合总风险上限 8%

        self.active_symbols = active_symbols or []
        self.monitor_intervals = {
            "15m": SimpleNamespace(use_trend_filter=False),
            "1h": SimpleNamespace(use_trend_filter=False),
            "4h": SimpleNamespace(use_trend_filter=False),
        }  # 会被 config.py 层面动态覆盖

        # 策略使用的历史 K 线缓存 (按级别、币种双层隔离)
        # 结构：{"15m": {"BTCUSDT": [Bar, Bar...]}, "1h": {...}}
        self.history_bars: Dict[str, Dict[str, List[Bar]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # 用于 Dashboard 实时价格看板的最新价格缓存
        self.latest_prices: Dict[str, float] = {}

        # 全局风控参数，后续应由 IConfigProvider 动态拉取，此处为快速启动赋默认值
        self.risk_config = RiskConfig(
            risk_pct=0.02,
            max_sl_dist=0.035,
            max_leverage=20.0,
            max_positions=4
        )
        self.weights = ScoringWeights(w_shape=0.4, w_trend=0.4, w_vol=0.2)
        from core.entities import PinbarConfig

        self.pinbar_config = PinbarConfig()
        self.system_enabled = True

        # ================================
        # 遥测系统指标数据 (Telemetry)
        # ================================
        import time

        self.start_time = time.time()
        self.is_connected = False
        self.api_latency_ms = 0
        self.api_weight_usage = 0.0

    async def _warmup_history(self):
        """
        冷启动预热：预加载最近 100 根历史 K 线到缓冲区。
        解决 PinbarStrategy 需要至少 60 根历史才能计算 EMA60 的冷启动问题。
        若无此步骤，15m 级别需等待 15 小时，1h 需等待 2.5 天才能产出首个信号。
        """
        from infrastructure.feed.binance_kline_fetcher import (
            BinanceKlineFetcher,
            INTERVAL_MS,
        )

        fetcher = BinanceKlineFetcher()
        warmup_bars = 100  # 预加载根数

        # 收集所有需要订阅的级别 (含 MTF 大级别)
        mtf_mapping = {"15m": "1h", "1h": "4h", "4h": "1d", "1d": "1d"}
        all_intervals = set(self.monitor_intervals.keys())
        for ivl, cfg in self.monitor_intervals.items():
            if cfg.use_trend_filter and ivl in mtf_mapping:
                all_intervals.add(mtf_mapping[ivl])

        total_tasks = len(self.active_symbols) * len(all_intervals)
        logger.info(
            f"🔥 开始冷启动预热：{len(self.active_symbols)} 个币种 × {len(all_intervals)} 个级别 = {total_tasks} 个缓冲区"
        )

        success_count = 0
        for sym in self.active_symbols:
            for ivl in all_intervals:
                try:
                    interval_ms = INTERVAL_MS.get(ivl, 3_600_000)
                    # 往前推 warmup_bars 根 K 线的时间
                    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                    start_ms = now_ms - (warmup_bars * interval_ms)
                    start_date = datetime.fromtimestamp(
                        start_ms / 1000, tz=timezone.utc
                    ).strftime("%Y-%m-%d")
                    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    bars = await fetcher.fetch_history_klines(
                        symbol=sym,
                        interval=ivl,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    # 只保留最近 100 根
                    bars = bars[-warmup_bars:]
                    self.history_bars[ivl][sym.upper()] = bars
                    success_count += 1
                    logger.info(f"  ✅ {sym} {ivl} 预加载 {len(bars)} 根 K 线")

                except Exception as e:
                    logger.warning(f"  ⚠️ {sym} {ivl} 预加载失败 (非致命): {e}")

        logger.info(f"🔥 冷启动预热完成：{success_count}/{total_tasks} 个缓冲区已就绪")

    async def start(self):
        """
        引擎主干线：无限循环的事件驱动处理程序。
        必须做好最外层的防御性 try-except 机制，保证 7x24 小时运行。
        """
        # === 冷启动预热：预加载历史 K 线，消除 EMA60 需要 60 根历史的等待漏洞 ===
        await self._warmup_history()

        logger.info(
            f"🚀 CryptoRadar 引擎已启动！正在监听 {self.active_symbols} {self.monitor_intervals} K 线流..."
        )

        # 定义多重时间框架 (MTF) 的大级别映射关系
        mtf_mapping = {
            "15m": "1h",
            "1h": "4h",
            "4h": "1d",
            "1d": "1d",  # 1d 暂时没有配置，让其参考自身
        }

        while True:
            try:
                self.is_connected = False

                # 计算出所有需要订阅的 K 线级别 (目标周期 + 如果开启了 MTF 则额外订阅的其依赖的高级周期)
                needed_intervals = set(self.monitor_intervals.keys())
                for ivl, config in self.monitor_intervals.items():
                    if config.use_trend_filter and ivl in mtf_mapping:
                        needed_intervals.add(mtf_mapping[ivl])

                async for current_bar in self.feed.subscribe_klines(
                    self.active_symbols, list(needed_intervals)
                ):
                    self.is_connected = True

                    self.latest_prices[current_bar.symbol.upper()] = current_bar.close

                    if not current_bar.is_closed:
                        continue

                    logger.debug(
                        f"收到闭合 K 线：{current_bar.symbol} {current_bar.interval} {current_bar.timestamp} 收盘价：{current_bar.close}"
                    )

                    if not self.system_enabled:
                        continue

                    sym_upper = current_bar.symbol.upper()
                    ivl = current_bar.interval

                    # 只有当前收盘线的周期在我们目标监控列表里，才触发策略计算。
                    # 如果这仅仅是一根用作"支撑大级别趋势"而不在监控列表的 K 线，我们只追加缓存，不触发打单检查。
                    should_evaluate = ivl in self.monitor_intervals

                    current_history = self.history_bars[ivl][sym_upper]

                    # 提取 MTF 高级别趋势 (如果当前就是 1d 或者未配置，默认 None 走原逻辑)
                    higher_trend = None
                    if (
                        should_evaluate
                        and ivl in mtf_mapping
                        and mtf_mapping[ivl] != ivl
                    ):
                        interval_config = self.monitor_intervals.get(ivl)
                        if interval_config and interval_config.use_trend_filter:
                            higher_ivl = mtf_mapping[ivl]
                            higher_history = self.history_bars[higher_ivl][sym_upper]
                            # 计算大级别 EMA60
                            if len(higher_history) >= 60:
                                from domain.strategy.indicators import calculate_ema

                                higher_closes = [b.close for b in higher_history]
                                higher_ema60 = calculate_ema(higher_closes, 60)
                                # 如果当前价格在大级别 EMA 之上则看多
                                higher_trend = (
                                    "LONG"
                                    if current_bar.close > higher_ema60
                                    else "SHORT"
                                )

                    signal = None
                    if should_evaluate:
                        signal = self.strategy.evaluate(
                            current_bar=current_bar,
                            history_bars=current_history,
                            max_sl_dist=self.max_sl_dist,
                            weights=self.weights,
                            higher_trend=higher_trend,
                            pinbar_config=self.pinbar_config,
                        )

                    # 更新履历
                    current_history.append(current_bar)
                    if len(current_history) > 100:
                        current_history.pop(0)

                    if not signal:
                        continue

                    logger.info(
                        f"✨ 发现有效策略信号！级别：{signal.interval} 方向：{signal.direction} 理由：{signal.reason}"
                    )

                    # 2. 探针：获取真实的账户只读状态
                    try:
                        import time

                        start_req = time.time()
                        account_balance = (
                            await self.account_reader.fetch_account_balance()
                        )
                        self.api_latency_ms = int((time.time() - start_req) * 1000)
                        # 模拟权重消耗积累和释放的监控
                        self.api_weight_usage = min(100.0, self.api_weight_usage + 5.0)
                    except Exception as e:
                        self.api_latency_ms = 999
                        logger.error(f"无法读取币安余额信息：{e}")
                        continue

                    # 3. 检查投资组合总风险敞口
                    portfolio_risk_metrics = self.portfolio_risk_service.calculate_portfolio_risk(
                        positions=account_balance.positions,
                        total_wallet_balance=account_balance.total_wallet_balance
                    )

                    if not self.portfolio_risk_service.check_portfolio_limit(
                        portfolio_risk_metrics,
                        self.max_portfolio_risk_pct
                    ):
                        logger.warning(
                            f"🚫 投资组合总风险超限：{portfolio_risk_metrics.total_risk_pct:.2%} "
                            f"(上限：{self.max_portfolio_risk_pct:.2%})"
                        )
                        continue

                    # 4. 风控算仓大脑计算 (纯领域计算)
                    try:
                        sizing = self.risk_sizer.calculate(
                            signal=signal,
                            account=account_balance,
                            risk_config=self.risk_config,
                        )
                    except RiskLimitExceeded as e:
                        logger.warning(f"🚫 信号由于硬风控被拦截丢弃：{str(e)}")
                        continue

                    # 4. 只读动作下沉持久化入库用于审计
                    await self.repo.save_signal(signal)
                    await self.repo.save_position_sizing(sizing)

                    # 5. 根据信号质量分级决定推送策略
                    # A 级：精品信号 - 立即推送 + 高亮
                    # B 级：普通信号 - 正常推送
                    # C 级：观察信号 - 仅记录不推送
                    quality_tier = getattr(signal, 'quality_tier', 'B')

                    if quality_tier == 'C':
                        logger.info(
                            f"📝 观察到 C 级信号：{signal.symbol} {signal.direction} (评分：{signal.score}, 仅记录不推送)"
                        )
                        # C 级信号只记录，不推送
                        continue

                    # 5.1 组装推送到用户的 Markdown 告警富文本
                    markdown_message = self._format_message(sizing, account_balance, signal)

                    # 取出全局推送总闸状态，默认开启
                    global_push_val = await self.repo.get_secret("global_push_enabled")
                    is_global_push = (
                        global_push_val.lower() == "true" if global_push_val else True
                    )

                    if is_global_push:
                        # 根据信号等级添加前缀标记
                        tier_prefix = "🌟【精品信号】" if quality_tier == 'A' else "📢【普通信号】"
                        markdown_message = f"{tier_prefix}\n\n{markdown_message}"

                        # 并发广播给多个收信端，绝对不阻塞
                        await self.notifier.send_markdown(markdown_message)
                        logger.info(
                            f"✅ 已推送 {quality_tier}级信号：{signal.symbol} {signal.direction}"
                        )
                    else:
                        logger.info(
                            f"监控到信号：#{signal.symbol.upper()} - {signal.direction}，但全局推送 (global_push_enabled) 已关闭，跳过告警。"
                        )

            except Exception as e:
                import traceback

                self.is_connected = False
                logger.error(
                    f"引擎出现全局未处理的阻断级异常：{e}，将在 10 秒后重启内部大循环。\n{traceback.format_exc()}"
                )

                # 在此触发强制断网或异常告警推送
                try:
                    await self.notifier.send_markdown(
                        f"🚨 **系统发生阻断级异常**\n\n```text\n{e}\n```\n系统将于 10 秒后重试连接。"
                    )
                except:
                    pass
                await asyncio.sleep(10)

        # 在循环最后或者后台任务中，模拟性能消耗衰减
        # 这里为了简化不另开 task，可放在循环空闲期，不过当前是阻塞流，由其他机制衰减亦可。

    def _format_message(self, sizing, account, signal=None) -> str:
        """组装 Markdown 通知 - 精简版，只保留关键信息"""
        if signal is None:
            signal = sizing.signal
        timestamp_str = datetime.fromtimestamp(signal.timestamp / 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        direction_emoji = "🟢 多" if signal.direction == "LONG" else "🔴 空"

        # 将打分 (0-100) 映射到 (0-10)
        display_score = round(signal.score / 10, 1)

        # 信号等级标记
        quality_tier = getattr(signal, 'quality_tier', 'B')
        tier_icon = "🌟" if quality_tier == 'A' else "📊" if quality_tier == 'B' else "📝"

        return (
            f"**{tier_icon} {signal.reason} · {display_score}分**\n"
            f"#{signal.symbol.upper()} | {signal.interval} | {direction_emoji}\n"
            f"入场：`{signal.entry_price}`\n"
            f"止损：`{signal.stop_loss}`\n"
            f"目标：`{signal.take_profit_1}`\n"
            f"杠杆：`{sizing.suggested_leverage:.1f}x`"
        )
