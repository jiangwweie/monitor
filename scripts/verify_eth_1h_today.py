"""
验证脚本：检测今天 ETH 1h 级别是否存在 Pinbar 信号
如果有信号则入库保存，不推送通知。
"""
import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.entities import Bar, ScoringWeights, PinbarConfig, Signal
from domain.strategy.pinbar import PinbarStrategy
from infrastructure.feed.binance_kline_fetcher import BinanceKlineFetcher
from infrastructure.repo.sqlite_repo import SQLiteRepo


async def main():
    # 初始化组件
    fetcher = BinanceKlineFetcher()
    strategy = PinbarStrategy(ema_period=60, atr_period=14)
    repo = SQLiteRepo("radar.db")
    await repo.init_db()

    weights = ScoringWeights(w_shape=0.4, w_trend=0.4, w_vol=0.2)
    pinbar_config = PinbarConfig()
    max_sl_dist = 0.035

    # 拉取足够的历史数据 (EMA60 需要至少 60 根 K 线)
    # 今天是 2026-03-02，往前拉 5 天的数据确保有足够历史
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # 往前取 10 天数据，保证 EMA60 有足够的历史支撑
    start_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")

    print(f"=" * 60)
    print(f"ETH 15m Pinbar 信号验证")
    print(f"日期范围: {start_date} ~ {today}")
    print(f"=" * 60)

    # 拉取 K 线数据
    print(f"\n[1] 正在从 Binance 拉取 ETHUSDT 15m K线数据...")
    bars = await fetcher.fetch_history_klines(
        symbol="ETHUSDT",
        interval="15m",
        start_date=start_date,
        end_date=today,
    )
    print(f"    共拉取到 {len(bars)} 根 K 线")

    if len(bars) < 61:
        print("    K 线数据不足 61 根，无法计算 EMA60，退出。")
        return

    # 筛选出今天 UTC 时间范围内的 K 线
    today_start_ms = BinanceKlineFetcher._date_to_ms(today)
    today_bars = [b for b in bars if b.timestamp >= today_start_ms]
    print(f"    其中今天 ({today} UTC) 的已闭合 K 线: {len(today_bars)} 根")

    # 对今天的每根已闭合 K 线逐一检测
    print(f"\n[2] 开始逐根检测 Pinbar 信号...")
    signals_found = []

    for i, bar in enumerate(bars):
        if bar.timestamp < today_start_ms:
            continue
        if not bar.is_closed:
            continue

        # 获取该 K 线之前的历史数据
        bar_index = bars.index(bar)
        history = bars[:bar_index]

        if len(history) < max(60, 15):
            continue

        signal = strategy.evaluate(
            current_bar=bar,
            history_bars=history,
            max_sl_dist=max_sl_dist,
            weights=weights,
            higher_trend=None,
            pinbar_config=pinbar_config,
        )

        bar_time = datetime.fromtimestamp(bar.timestamp / 1000, tz=timezone.utc)
        beijing_time = bar_time + timedelta(hours=8)

        if signal:
            signal.source = "history_scan"
            signals_found.append(signal)
            print(f"    ✅ 发现信号! 时间={beijing_time.strftime('%m-%d %H:%M')} (北京)")
            print(f"       方向={signal.direction}, 入场={signal.entry_price:.2f}, "
                  f"止损={signal.stop_loss:.2f}, 止盈={signal.take_profit_1:.2f}")
            print(f"       得分={signal.score}, 止损距离={signal.sl_distance_pct*100:.2f}%")
            print(f"       影线比={signal.shadow_ratio}, EMA距离={signal.ema_distance}%, "
                  f"ATR波动={signal.volatility_atr}")
        else:
            print(f"    ⬜ {beijing_time.strftime('%m-%d %H:%M')} (北京) - 无信号")

    # 汇总结果
    print(f"\n{'=' * 60}")
    print(f"[3] 检测结果汇总")
    print(f"{'=' * 60}")
    print(f"    今天已闭合 K 线数: {len(today_bars)}")
    print(f"    发现信号数量: {len(signals_found)}")

    if signals_found:
        print(f"\n[4] 正在将 {len(signals_found)} 个信号入库保存 (不推送)...")
        for sig in signals_found:
            await repo.save_signal(sig)
            sig_time = datetime.fromtimestamp(sig.timestamp / 1000, tz=timezone.utc) + timedelta(hours=8)
            print(f"    💾 已入库: {sig.symbol} {sig.interval} {sig.direction} "
                  f"@ {sig_time.strftime('%m-%d %H:%M')} 得分={sig.score}")
        print(f"\n    全部入库完成!")
    else:
        print(f"\n    今天暂无 ETH 1H Pinbar 信号。")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
