
import asyncio
import logging
import time
from typing import List

from core.entities import Bar, ScoringWeights, AccountBalance
from domain.strategy.pinbar import PinbarStrategy
from domain.risk.sizer import PositionSizer
from infrastructure.repo.sqlite_repo import SQLiteRepo
from infrastructure.notify.broadcaster import NotificationBroadcaster
from infrastructure.notify.wecom import WeComNotifier
from infrastructure.notify.feishu import FeishuNotifier

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger("VerifyFlow")

async def verify_full_flow():
    logger.info("开始全业务流程验证 (Mock 模拟)...")
    
    # 1. 初始化组件
    repo = SQLiteRepo("radar.db")
    await repo.init_db()
    
    strategy = PinbarStrategy(ema_period=60, atr_period=14)
    risk_sizer = PositionSizer()
    
    # 2. 构造组合推送 (包含企微)
    broadcaster = NotificationBroadcaster()
    wecom = WeComNotifier(repo=repo)
    feishu = FeishuNotifier(webhook_url="") # 占位
    broadcaster.register(wecom).register(feishu)
    
    # 3. 构造 Mock 历史数据 (顺势 LONG)
    # EMA60 会在 2000 左右
    history_bars = []
    base_price = 2000
    for i in range(70):
        history_bars.append(Bar(
            symbol="ETHUSDT",
            open=base_price + i,
            close=base_price + i + 1,
            high=base_price + i + 2,
            low=base_price + i - 1,
            volume=100,
            timestamp=int(time.time() * 1000) - (70 - i) * 3600000,
            is_closed=True
        ))
    
    # 4. 构造触发信号的最后一根 Pinbar (LONG)
    # 收盘 > EMA (约 2035)
    # Body (Close-Open) = 5. Range (High-Low) = 60.
    # Shadow (Min(O,C)-Low) = 50.
    mock_current_bar = Bar(
        symbol="ETHUSDT",
        open=2100,
        close=2105,
        high=2110,
        low=2050, # 下影线 50
        volume=500,
        timestamp=int(time.time() * 1000),
        is_closed=True
    )
    
    logger.info("Step 1: 策略判定中...")
    weights = ScoringWeights(w_shape=0.4, w_trend=0.4, w_vol=0.2)
    signal = strategy.evaluate(
        current_bar=mock_current_bar,
        history_bars=history_bars,
        max_sl_dist=0.05,
        weights=weights
    )
    
    if not signal:
        logger.error("❌ 策略判定未触发，请检查 Mock Bar 参数。")
        return

    logger.info(f"✅ 策略触发成功! 方向: {signal.direction}, 得分: {signal.score}")
    
    # 5. 模拟账户余额 (10000 USDT)
    logger.info("Step 2: 风控算仓中...")
    mock_account = AccountBalance(
        total_wallet_balance=10000.0,
        available_balance=8000.0,
        current_positions_count=1,
        positions=[]
    )
    
    sizing = risk_sizer.calculate(
        signal=signal,
        account=mock_account,
        risk_pct=0.02,
        max_leverage=20.0
    )
    
    logger.info(f"✅ 算仓结果: 建议数量 {sizing.suggested_quantity}, 杠杆 {sizing.suggested_leverage}x")
    
    # 6. 持久化
    logger.info("Step 3: 持久化入库...")
    await repo.save_signal(signal)
    
    # 7. 推送验证
    logger.info("Step 4: 发起并发推送 (含企微)...")
    
    # 模拟 engine 的 _format_message 逻辑
    from datetime import datetime
    timestamp_str = datetime.fromtimestamp(signal.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
    display_score = round(signal.score / 10, 1)
    
    message = (
        f"**🚨发现交易信号 ({signal.reason})**\n"
        f"**项目**: #{signal.symbol.upper()}\n"
        f"**周期**: 1h | **方向**: 🟢 LONG\n"
        f"**时间**: {timestamp_str}\n\n"
        f"- 入场参考: `{signal.entry_price}`\n"
        f"- 初始止损: `{signal.stop_loss}`\n"
        f"- 预期 TP1: `{signal.take_profit_1}` (1.5R)\n\n"
        f"- EMA60 状态: Price > EMA60\n"
        f"- ADX 强度: `Active`\n"
        f"- 形态评分: `{display_score}/10`\n\n"
        f"- 建议杠杆 {sizing.suggested_leverage:.1f}x\n"
    )
    await broadcaster.send_markdown(message)
    logger.info("🚀 验证任务执行完毕。")

if __name__ == "__main__":
    asyncio.run(verify_full_flow())
