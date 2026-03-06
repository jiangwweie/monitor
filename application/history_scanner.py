"""
应用层：历史信号扫描引擎 (History Scanner)
实现异步任务管理 + 策略回放 + MTF 穿越式趋势校验。
【绝对红线】：仅允许 GET 读取 + 本地计算 + 入库 + 推送，严禁任何 create_order / 下单逻辑。
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable

from core.entities import Bar, ScoringWeights, PinbarConfig, IntervalConfig
from core.interfaces import IRepository, INotifier
from domain.strategy.pinbar import PinbarStrategy
from domain.strategy.indicators import calculate_ema
from infrastructure.feed.binance_kline_fetcher import BinanceKlineFetcher

logger = logging.getLogger(__name__)

# 多重时间框架映射 (与 monitor_engine.py 保持完全一致)
MTF_MAPPING = {
    "15m": "1h",
    "1h": "4h",
    "4h": "1d",
    "1d": "1d",
}


@dataclass
class HistoryScanTask:
    """异步扫描任务状态容器"""
    task_id: str
    status: str = "running"        # "running" | "completed" | "failed"
    progress: int = 0              # 0 ~ 100
    message: str = ""
    result: Optional[dict] = None  # {total_bars_scanned, signals_found, signals_saved}
    config: Optional[dict] = None  # {symbol, interval, start_date, end_date}


class HistoryScanner:
    """
    历史信号扫描器。
    全量复用 PinbarStrategy 检测逻辑与 ScoringWeights 评分权重。
    通过 asyncio.create_task 在后台执行，不阻塞前端 UI。
    """

    def __init__(
        self,
        strategy: PinbarStrategy,
        repo: IRepository,
        notifier: INotifier,
        kline_fetcher: BinanceKlineFetcher,
        engine,  # CryptoRadarEngine 引用，用于读取实时配置
    ):
        self.strategy = strategy
        self.repo = repo
        self.notifier = notifier
        self.kline_fetcher = kline_fetcher
        self.engine = engine

        # 内存任务注册表
        self._tasks: Dict[str, HistoryScanTask] = {}
        # 保留 asyncio.Task 引用以防 GC
        self._async_tasks: Dict[str, asyncio.Task] = {}

    def submit_task(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
    ) -> str:
        """
        提交一次历史扫描任务。

        :return: task_id (UUID)
        """
        task_id = f"scan-{uuid.uuid4().hex[:12]}"

        task = HistoryScanTask(
            task_id=task_id,
            status="running",
            progress=0,
            message="任务已提交，正在初始化...",
            config={
                "symbol": symbol,
                "interval": interval,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        self._tasks[task_id] = task

        # 用 asyncio.create_task 启动后台协程，立即返回 task_id
        async_task = asyncio.create_task(
            self._run_scan(task_id, symbol, interval, start_date, end_date)
        )
        self._async_tasks[task_id] = async_task

        logger.info(
            f"[HistoryScanner] 任务已提交: {task_id} | "
            f"{symbol} {interval} {start_date} ~ {end_date}"
        )
        return task_id

    def get_task_status(self, task_id: str) -> Optional[HistoryScanTask]:
        """查询任务状态"""
        return self._tasks.get(task_id)

    async def _run_scan(
        self,
        task_id: str,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
    ) -> None:
        """
        扫描主流水线 (后台协程)。

        流程:
        1. 拉取目标级别历史 K 线
        2. 如有 MTF，拉取大级别历史 K 线
        3. 逐根回放 PinbarStrategy.evaluate()
        4. 命中信号 → source="history_scan" → 入库
        5. 完成后推送飞书/企微汇总通知
        """
        task = self._tasks[task_id]

        try:
            # ============================
            # 1. 读取引擎当前配置
            # ============================
            weights: ScoringWeights = self.engine.weights
            pinbar_config: PinbarConfig = self.engine.pinbar_config
            max_sl_dist: float = self.engine.max_sl_dist
            monitor_intervals: Dict[str, IntervalConfig] = self.engine.monitor_intervals

            # 判断是否需要 MTF 趋势校验
            interval_config = monitor_intervals.get(interval, IntervalConfig())
            use_trend_filter = interval_config.use_trend_filter
            higher_interval = MTF_MAPPING.get(interval)
            need_mtf = (
                use_trend_filter
                and higher_interval is not None
                and higher_interval != interval
            )

            # ============================
            # 2. 拉取目标级别历史 K 线
            # ============================
            task.message = f"正在拉取 {symbol} {interval} 历史K线..."

            def update_fetch_progress(fetched: int, total: int):
                # 数据拉取阶段占进度条的 0~40%
                pct = min(40, int(fetched / max(total, 1) * 40))
                task.progress = pct
                task.message = f"正在拉取K线数据: {fetched} / {total}"

            target_bars = await self.kline_fetcher.fetch_history_klines(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                on_progress=update_fetch_progress,
            )

            if not target_bars:
                task.status = "completed"
                task.progress = 100
                task.message = "未获取到任何K线数据"
                task.result = {
                    "total_bars_scanned": 0,
                    "signals_found": 0,
                    "signals_saved": 0,
                }
                return

            # ============================
            # 3. 拉取大级别 K 线 (如需 MTF)
            # ============================
            higher_bars: List[Bar] = []
            if need_mtf and higher_interval:
                task.message = f"正在拉取 {symbol} {higher_interval} 大级别K线 (MTF)..."
                task.progress = 42
                higher_bars = await self.kline_fetcher.fetch_history_klines(
                    symbol=symbol,
                    interval=higher_interval,
                    start_date=start_date,
                    end_date=end_date,
                )
                logger.info(
                    f"[HistoryScanner] MTF 大级别 {higher_interval} 拉取到 {len(higher_bars)} 根"
                )

            # ============================
            # 4. 策略回放：逐根扫描
            # ============================
            task.message = "正在执行策略回放扫描..."
            task.progress = 45

            total_bars = len(target_bars)
            signals_found = []

            # 滑动窗口：保存最近 100 根已处理的 K 线作为历史
            history_window: List[Bar] = []
            # EMA 需要至少 60 根历史数据计算

            for i, bar in enumerate(target_bars):
                # 更新进度：策略回放阶段占 45% ~ 90%
                if i % max(1, total_bars // 50) == 0:
                    scan_pct = 45 + int(i / max(total_bars, 1) * 45)
                    task.progress = min(90, scan_pct)
                    task.message = f"已扫描 {i} / {total_bars} 根K线"

                # ---- MTF 穿越式趋势校验 ----
                higher_trend = None
                if need_mtf and higher_bars:
                    higher_trend = self._compute_historical_trend(
                        bar.timestamp, bar.close, higher_bars
                    )

                # ---- 调用策略引擎 evaluate ----
                signal = self.strategy.evaluate(
                    current_bar=bar,
                    history_bars=history_window,
                    max_sl_dist=max_sl_dist,
                    weights=weights,
                    higher_trend=higher_trend,
                    pinbar_config=pinbar_config,
                )

                # 维护滑动窗口
                history_window.append(bar)
                if len(history_window) > 100:
                    history_window.pop(0)

                if signal:
                    # 标记来源为历史扫描
                    signal.source = "history_scan"
                    signals_found.append(signal)

            # ============================
            # 5. 持久化入库
            # ============================
            task.message = f"正在保存 {len(signals_found)} 个信号..."
            task.progress = 92

            signals_saved = 0
            for signal in signals_found:
                try:
                    await self.repo.save_signal(signal)
                    signals_saved += 1
                except Exception as e:
                    logger.error(f"[HistoryScanner] 信号入库失败: {e}")

            # ============================
            # 6. 推送汇总通知
            # ============================
            task.progress = 96
            task.message = "正在发送汇总推送..."

            if signals_found:
                await self._send_summary_notification(
                    symbol, interval, start_date, end_date,
                    total_bars, signals_saved, signals_found
                )

            # ============================
            # 7. 标记完成
            # ============================
            task.status = "completed"
            task.progress = 100
            task.message = f"扫描完成: 共 {total_bars} 根K线, 发现 {len(signals_found)} 个信号"
            task.result = {
                "total_bars_scanned": total_bars,
                "signals_found": len(signals_found),
                "signals_saved": signals_saved,
            }
            logger.info(
                f"[HistoryScanner] 任务 {task_id} 完成: "
                f"扫描 {total_bars} 根, 发现 {len(signals_found)} 个信号, 入库 {signals_saved} 个"
            )

        except Exception as e:
            import traceback
            task.status = "failed"
            task.progress = 100
            task.message = f"扫描失败: {str(e)}"
            task.result = {"error": str(e)}
            logger.error(
                f"[HistoryScanner] 任务 {task_id} 异常: {e}\n{traceback.format_exc()}"
            )

    def _compute_historical_trend(
        self,
        target_timestamp: int,
        current_close: float,
        higher_bars: List[Bar],
    ) -> Optional[str]:
        """
        穿越式 MTF 趋势校验。

        在大级别 K 线序列中，找到 <= target_timestamp 的所有 K 线，
        计算它们的 EMA60，判定当时的趋势方向。
        这保证了在检测 2 月 1 日的 15m 信号时，匹配的是 2 月 1 日当时的 1h EMA 趋势。
        """
        # 过滤出 <= 当前时间点的大级别 K 线
        relevant_bars = [b for b in higher_bars if b.timestamp <= target_timestamp]

        if len(relevant_bars) < 60:
            return None

        closes = [b.close for b in relevant_bars]
        ema60 = calculate_ema(closes, 60)

        return "LONG" if current_close > ema60 else "SHORT"

    async def _send_summary_notification(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        total_bars: int,
        signals_saved: int,
        signals: list,
    ) -> None:
        """拼装并发送历史扫描汇总推送"""
        try:
            # 取出全局推送总闸
            global_push_val = await self.repo.get_secret("global_push_enabled")
            is_global_push = global_push_val.lower() == "true" if global_push_val else True

            if not is_global_push:
                logger.info("[HistoryScanner] 全局推送已关闭，跳过汇总通知")
                return

            # 信号明细 (最多展示前 10 条)
            details_lines = []
            for i, sig in enumerate(signals[:10]):
                ts_str = datetime.fromtimestamp(sig.timestamp / 1000).strftime('%m-%d %H:%M')
                direction_emoji = "🟢" if sig.direction == "LONG" else "🔴"
                score_display = round(sig.score / 10, 1)
                details_lines.append(
                    f"  {i+1}. {ts_str} {direction_emoji} {sig.direction} "
                    f"入场 `{sig.entry_price}` 评分 `{score_display}/10`"
                )

            if len(signals) > 10:
                details_lines.append(f"  ... 及其余 {len(signals) - 10} 条信号")

            details_text = "\n".join(details_lines)

            message = (
                f"**📊 历史信号扫描完成**\n\n"
                f"**交易对**: #{symbol}\n"
                f"**级别**: {interval}\n"
                f"**扫描区间**: {start_date} ～ {end_date}\n"
                f"**K线总数**: {total_bars} 根\n"
                f"**发现信号**: {signals_saved} 个\n\n"
                f"**信号明细:**\n{details_text}\n"
            )

            await self.notifier.send_markdown(message)
            logger.info("[HistoryScanner] 汇总推送已发送")

        except Exception as e:
            logger.error(f"[HistoryScanner] 汇总推送失败: {e}")
