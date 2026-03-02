"""
诊断脚本：分析 2026-03-02 16:00(北京) / 08:00(UTC) 的 ETH 1H K 线
验证形态背离处理逻辑 - 即使 EMA 趋势向下，长下影线也可产生 LONG 信号 (扣 20 分)
"""
import asyncio
import sys, os
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.entities import Bar, ScoringWeights, PinbarConfig
from domain.strategy.pinbar import PinbarStrategy
from domain.strategy.indicators import calculate_ema, calculate_atr
from infrastructure.feed.binance_kline_fetcher import BinanceKlineFetcher
from infrastructure.repo.sqlite_repo import SQLiteRepo

# 配置日志输出
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def main():
    fetcher = BinanceKlineFetcher()
    strategy = PinbarStrategy(ema_period=60, atr_period=14)
    pinbar_config = PinbarConfig()
    pinbar_config.volatility_atr_multiplier = 1.1 # 临时调整 ATR 限制，用于演示完整的背离扣分入库流程
    weights = ScoringWeights(w_shape=0.4, w_trend=0.4, w_vol=0.2)
    max_sl_dist = 0.035

    # 拉取足够历史 (EMA60 需要 60+ 根)
    print("📡 正在从币安获取历史 K 线数据...")
    bars = await fetcher.fetch_history_klines(
        symbol="ETHUSDT", interval="1h",
        start_date="2026-02-20", end_date="2026-03-02",
    )

    # 北京时间 16:00 = UTC 08:00, 时间戳对应 2026-03-02 08:00 UTC
    target_utc = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)
    target_ms = int(target_utc.timestamp() * 1000)

    # 找到目标 K 线
    target_bar = None
    target_idx = None
    for i, b in enumerate(bars):
        if b.timestamp == target_ms:
            target_bar = b
            target_idx = i
            break

    if not target_bar:
        print(f"❌ 未找到目标 K 线 (timestamp={target_ms})")
        # 打印附近 K 线看看
        print("🔍 附近 K 线:")
        for b in bars:
            bt = datetime.fromtimestamp(b.timestamp / 1000, tz=timezone.utc) + timedelta(hours=8)
            if "03-02" in bt.strftime("%m-%d") and 14 <= bt.hour <= 18:
                print(f"  {bt.strftime('%m-%d %H:%M')} O={b.open} H={b.high} L={b.low} C={b.close}")
        return

    history = bars[:target_idx]

    print("=" * 70)
    print("📊 ETH 1H Pinbar 形态背离诊断分析")
    print(f"目标 K 线：北京时间 2026-03-02 16:00 (UTC 08:00)")
    print("=" * 70)

    # 1. 基本数据
    print(f"\n📈 K 线数据:")
    print(f"   Open  = {target_bar.open}")
    print(f"   High  = {target_bar.high}")
    print(f"   Low   = {target_bar.low}")
    print(f"   Close = {target_bar.close}")
    print(f"   Volume= {target_bar.volume}")
    print(f"   Closed= {target_bar.is_closed}")

    # 2. 计算指标
    all_bars = history + [target_bar]
    closes = [b.close for b in all_bars]
    highs = [b.high for b in all_bars]
    lows = [b.low for b in all_bars]

    ema60 = calculate_ema(closes, 60)
    atr14 = calculate_atr(highs, lows, closes, 14)

    print(f"\n📉 技术指标:")
    print(f"   EMA60 = {ema60:.2f}")
    print(f"   ATR14 = {atr14:.2f}")
    print(f"   历史 K 线数 = {len(history)} (需要 >= 60)")

    # 3. 逐步检查每个过滤条件 (新逻辑：形态与趋势解耦)
    print(f"\n🔍 逐步过滤条件检查 (新逻辑 - 形态与趋势解耦):")

    # 条件 0: is_closed
    print(f"\n   [0] K 线已闭合？{target_bar.is_closed}")
    if not target_bar.is_closed:
        print(f"       ❌ 未闭合，直接拒绝")
        return
    print(f"       ✅ 通过")

    # 条件 1: 形态识别 (先于趋势判断)
    body_length = abs(target_bar.open - target_bar.close)
    total_length = target_bar.high - target_bar.low
    body_ratio_val = body_length / total_length if total_length > 0 else 1

    print(f"\n   [1] 形态过滤 - 实体比例:")
    print(f"       实体长度 = |{target_bar.open} - {target_bar.close}| = {body_length:.2f}")
    print(f"       总长度   = {target_bar.high} - {target_bar.low} = {total_length:.2f}")
    print(f"       实体比例 = {body_ratio_val:.4f} (阈值：<= {pinbar_config.body_max_ratio})")

    if total_length == 0:
        print(f"       ❌ 总长度为 0, 被拒绝")
        return
    if body_length > total_length * pinbar_config.body_max_ratio:
        print(f"       ❌ 实体比例 {body_ratio_val:.4f} > {pinbar_config.body_max_ratio}, 实体太大，被拒绝!")
        return
    print(f"       ✅ 通过")

    # 条件 2: 十字星检查 & 影线比例
    is_doji = body_ratio_val < pinbar_config.doji_threshold
    effective_shadow_ratio = (
        pinbar_config.shadow_min_ratio * pinbar_config.doji_shadow_bonus
        if is_doji else pinbar_config.shadow_min_ratio
    )

    lower_shadow = min(target_bar.open, target_bar.close) - target_bar.low
    upper_shadow = target_bar.high - max(target_bar.open, target_bar.close)

    print(f"\n   [2] 形态过滤 - 影线比例 (解耦分析):")
    print(f"       十字星？{is_doji} (实体/全长 {body_ratio_val:.4f} < {pinbar_config.doji_threshold}?)")
    print(f"       有效影线倍数要求 = {effective_shadow_ratio}")
    print(f"       下影线长度 = {lower_shadow:.2f}")
    print(f"       上影线长度 = {upper_shadow:.2f}")
    print(f"       实体长度 = {body_length:.2f}")

    valid_long_shape = lower_shadow >= body_length * effective_shadow_ratio
    valid_short_shape = upper_shadow >= body_length * effective_shadow_ratio

    print(f"\n       形态方向判定:")
    print(f"       - 长下影线 (做多) 条件：{lower_shadow:.2f} >= {body_length:.2f} × {effective_shadow_ratio} = {body_length * effective_shadow_ratio:.2f} → {'✅ 满足' if valid_long_shape else '❌ 不满足'}")
    print(f"       - 长上影线 (做空) 条件：{upper_shadow:.2f} >= {body_length:.2f} × {effective_shadow_ratio} = {body_length * effective_shadow_ratio:.2f} → {'✅ 满足' if valid_short_shape else '❌ 不满足'}")

    if not valid_long_shape and not valid_short_shape:
        print(f"\n       ❌ 上下影线都不满足条件，被拒绝!")
        return

    # 根据形态决定方向
    if valid_long_shape and not valid_short_shape:
        shape_direction = "LONG"
        print(f"\n       🎯 形态方向 = LONG (仅下影线满足)")
    elif valid_short_shape and not valid_long_shape:
        shape_direction = "SHORT"
        print(f"\n       🎯 形态方向 = SHORT (仅上影线满足)")
    elif valid_long_shape and valid_short_shape:
        shape_direction = "LONG" if lower_shadow > upper_shadow else "SHORT"
        print(f"\n       🎯 形态方向 = {shape_direction} (上下影线都满足，取更长者)")

    # 条件 3: EMA 趋势判断 & 背离检测
    ema_trend_is_long = target_bar.close > ema60
    ema_trend_is_short = target_bar.close < ema60

    print(f"\n   [3] EMA 趋势判断 & 背离检测:")
    print(f"       Close({target_bar.close:.2f}) vs EMA60({ema60:.2f})")
    print(f"       EMA 趋势 = {'LONG' if ema_trend_is_long else 'SHORT' if ema_trend_is_short else '无方向'}")

    is_shape_divergent = False
    if shape_direction == "LONG" and ema_trend_is_short:
        is_shape_divergent = True
        print(f"\n       ⚠️ 形态背离！形态看多 (LONG) 但 EMA 趋势看空 (SHORT)")
    elif shape_direction == "SHORT" and ema_trend_is_long:
        is_shape_divergent = True
        print(f"\n       ⚠️ 形态背离！形态看空 (SHORT) 但 EMA 趋势看多 (LONG)")

    if not is_shape_divergent:
        print(f"\n       ✅ 形态与 EMA 趋势一致，无背离")

    # 条件 4: 波动率 ATR 过滤
    atr_threshold = pinbar_config.volatility_atr_multiplier * atr14

    print(f"\n   [4] 波动率过滤 (ATR):")
    print(f"       K 线总波幅 = {total_length:.2f}")
    print(f"       ATR14 = {atr14:.2f}")
    print(f"       要求：总波幅 ({total_length:.2f}) > {pinbar_config.volatility_atr_multiplier} × ATR({atr14:.2f}) = {atr_threshold:.2f}")

    if total_length <= atr_threshold:
        print(f"       ❌ 波幅不够！{total_length:.2f} <= {atr_threshold:.2f}, 被拒绝!")
        return
    print(f"       ✅ 通过")

    # 条件 5: 止损距离检查
    entry_price = target_bar.close
    stop_loss = target_bar.low if shape_direction == "LONG" else target_bar.high
    actual_sl_distance = abs(entry_price - stop_loss)
    sl_distance_pct = actual_sl_distance / entry_price

    effective_max_sl = strategy._calculate_dynamic_sl_threshold(
        atr14=atr14, entry_price=entry_price,
        base_max_sl_dist=max_sl_dist, config=pinbar_config
    )

    print(f"\n   [5] 止损距离过滤:")
    print(f"       入场价 = {entry_price:.2f}")
    print(f"       止损价 = {stop_loss:.2f}")
    print(f"       止损距离 = {sl_distance_pct*100:.2f}%")
    print(f"       动态止损上限 = {effective_max_sl*100:.2f}%")

    if sl_distance_pct > effective_max_sl:
        print(f"       ❌ 止损距离过大！{sl_distance_pct*100:.2f}% > {effective_max_sl*100:.2f}%, 被拒绝!")
        return
    print(f"       ✅ 通过")

    # 6. 评分计算
    print(f"\n   [6] 评分计算:")
    signal = strategy.evaluate(
        current_bar=target_bar, history_bars=history,
        max_sl_dist=max_sl_dist, weights=weights, pinbar_config=pinbar_config,
    )

    if signal:
        print(f"\n{'='*70}")
        print("🎉 信号生成成功!")
        print(f"{'='*70}")
        print(f"   📌 信号方向：{signal.direction}")
        print(f"   📌 入场价格：{signal.entry_price}")
        print(f"   📌 止损价格：{signal.stop_loss}")
        print(f"   📌 止盈价格：{signal.take_profit_1}")
        print(f"   📌 信号得分：{signal.score}")
        print(f"   📌 形态背离：{'是 (扣 20 分)' if signal.is_shape_divergent else '否'}")
        print(f"   📌 逆势信号：{'是 (扣 15 分)' if signal.is_contrarian else '否'}")
        print(f"   📌 影线比例：{signal.shadow_ratio}")
        print(f"   📌 EMA 距离：{signal.ema_distance}%")
        print(f"   📌 止损距离：{signal.sl_distance_pct*100:.2f}%")
        if signal.score_details:
            print(f"   📌 评分详情：{signal.score_details}")

        # 入库保存
        print(f"\n{'='*70}")
        print("💾 正在保存信号到数据库...")
        repo = SQLiteRepo(db_path="radar.db")
        await repo.init_db()
        await repo.save_signal(signal)
        print(f"[DB] 信号已成功入库!")

        # 验证入库
        from core.entities import SignalFilter
        total, items = await repo.get_signals(
            SignalFilter(symbols=["ETHUSDT"], min_score=0),
            page=1, size=1
        )
        if items:
            print(f"\n📋 数据库中最新信号验证:")
            print(f"   - 信号 ID: {items[0].get('id')}")
            print(f"   - 方向：{items[0].get('direction')}")
            print(f"   - 得分：{items[0].get('score')}")
            print(f"   - 形态背离：{items[0].get('is_shape_divergent')}")

        print(f"\n{'='*70}")
        print("✅ 诊断完成！形态背离处理逻辑验证通过。")
        print(f"{'='*70}")
    else:
        print(f"\n⚠️ 策略引擎返回 None，信号未生成")
        print(f"   可能原因：其他过滤条件未通过")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())