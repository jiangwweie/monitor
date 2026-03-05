"""
模拟推送测试脚本 - 测试新的消息格式
"""
from datetime import datetime, timezone

# 模拟信号对象
class MockSignal:
    def __init__(self, symbol, entry_price, direction="LONG", tier="A"):
        self.symbol = symbol
        self.interval = "1h"
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss = entry_price * 0.98
        self.take_profit_1 = entry_price * 1.03
        self.sl_distance_pct = 2.0
        self.score = 85 if tier == "A" else 65
        self.quality_tier = tier
        self.timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

# 模拟 sizing 对象
class MockSizing:
    def __init__(self, signal):
        self.signal = signal

def format_message(sizing):
    """复制引擎中的格式化方法"""
    signal = sizing.signal
    timestamp_str = datetime.fromtimestamp(signal.timestamp / 1000).strftime("%m-%d %H:%M")

    direction_emoji = "🟢" if signal.direction == "LONG" else "🔴"
    direction_text = "做多" if signal.direction == "LONG" else "做空"

    quality_tier = getattr(signal, 'quality_tier', 'B')
    tier_badge = "A 级" if quality_tier == 'A' else "B 级" if quality_tier == 'B' else "C 级"
    display_score = round(signal.score / 10, 1)

    # 价格精度简化
    price = signal.entry_price
    if price >= 1000:
        decimal_places = 2
    elif price >= 1:
        decimal_places = 4
    else:
        decimal_places = 6

    entry_str = f"{signal.entry_price:.{decimal_places}f}"
    sl_str = f"{signal.stop_loss:.{decimal_places}f}"
    tp_str = f"{signal.take_profit_1:.{decimal_places}f}"

    return (
        f"{tier_badge} {direction_emoji} {direction_text}信号\n\n"
        f"**{signal.symbol}** ({signal.interval})\n"
        f"时间：{timestamp_str} | 评分：{display_score}/10\n\n"
        f"入场：`{entry_str}`\n"
        f"止损：`{sl_str}`\n"
        f"止盈：`{tp_str}` (1.5R)\n\n"
        f"止损距离：{signal.sl_distance_pct:.2f}%"
    )

print("=" * 60)
print("📱 企业微信推送消息预览 - 新格式")
print("=" * 60)

# 测试不同价位的币种
test_cases = [
    ("ETHUSDT", 1850.50, "LONG", "A", "高价币 (≥1000) - 2 位小数"),
    ("BTCUSDT", 43250.80, "SHORT", "B", "高价币 (≥1000) - 2 位小数"),
    ("SOLUSDT", 145.32, "LONG", "A", "中价币 (1-1000) - 4 位小数"),
    ("PEPEUSDT", 0.001234, "LONG", "B", "低价币 (<1) - 6 位小数"),
]

for symbol, price, direction, tier, desc in test_cases:
    signal = MockSignal(symbol, price, direction, tier)
    sizing = MockSizing(signal)
    message = format_message(sizing)
    full_message = f"🌟 {tier}级\n\n{message}" if tier == "A" else f"📢 {tier}级\n\n{message}"
    
    print(f"\n【{desc}】")
    print("-" * 60)
    print(full_message)
    print()
