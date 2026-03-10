# Pinbar 策略详细设计文档

## 1. 概述

Pinbar 策略是本监测系统的核心决策引擎，基于经典的 Pinbar（Pinocchio Bar）K 线形态，结合 EMA60 趋势过滤和 ATR 波动率过滤，生成高概率的交易信号。

**设计原则**：
- **纯领域逻辑**：无网络请求、无数据库操作、无副作用
- **零执行**：仅生成信号建议，绝不执行实际订单
- **可测试性**：所有依赖通过参数显式传入，便于单元测试

**文件位置**：`domain/strategy/pinbar.py`

---

## 2. 核心架构

### 2.1 类结构

```
PinbarStrategy
├── __init__(ema_period=60, atr_period=14)
├── evaluate(...)                    # 主入口：评估 K 线生成信号
├── _evaluate_shape(...)             # 形态评估
├── _calculate_shape_score(...)      # 形态评分
├── _evaluate_trend(...)             # 趋势评估
├── _evaluate_volatility(...)        # 波动率评估
├── _calculate_risk_penalty(...)     # 风险扣分
├── _calculate_dynamic_sl_threshold(...) # 动态止损阈值
└── _determine_signal_tier(...)      # 信号质量分级
```

### 2.2 数据流

```
输入：current_bar, history_bars, max_sl_dist, weights, higher_trend, pinbar_config
       │
       ▼
┌──────────────────────┐
│ 1. 数据验证           │
│    - is_closed 检查   │
│    - 历史数据长度检查 │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. 指标计算           │
│    - EMA60           │
│    - ATR14           │
└──────────┬───────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐   ┌──────────┐
│ 形态评估 │   │ 趋势评估 │
│ (Shape) │   │ (Trend)  │
└────┬────┘   └────┬─────┘
     │             │
     ▼             ▼
┌──────────────────────┐
│ 3. 波动率评估         │
│    (Volatility)      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. 风险评估           │
│    - 止损距离检查     │
│    - 动态止损阈值     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 5. 动态评分计算       │
│    - 加权各维度分数   │
│    - 背离扣分         │
│    - 逆势扣分         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 6. 信号质量分级       │
│    A 级 (精品)        │
│    B 级 (普通)        │
│    C 级 (观察)        │
└──────────┬───────────┘
           │
           ▼
输出：Signal 对象 或 None
```

---

## 3. 形态识别逻辑

### 3.1 Pinbar 定义

Pinbar（Pinocchio Bar）是一种单 K 线反转形态，特征是：
- **小实体**：开盘价与收盘价接近
- **长影线**：一侧影线显著长于另一侧
- **拒绝价格**：长影线表示价格在该方向被强烈拒绝

### 3.2 形态度量 (`_evaluate_shape`)

```python
body_length = abs(open - close)           # 实体长度
total_length = high - low                 # 总长度
body_ratio = body_length / total_length   # 实体占比

lower_shadow = min(open, close) - low     # 下影线
upper_shadow = high - max(open, close)    # 上影线
```

**Doji（十字星）判定**：
```python
is_doji = body_ratio < doji_threshold  # 默认 0.05 (5%)
```

**有效形状验证**：
```python
# 做空 Pinbar：上影线足够长
valid_short_shape = upper_shadow >= body_length * effective_shadow_ratio

# 做多 Pinbar：下影线足够长
valid_long_shape = lower_shadow >= body_length * effective_shadow_ratio

# Doji 模式下，影线要求放宽 40%
effective_shadow_ratio = (
    shadow_min_ratio * doji_shadow_bonus if is_doji
    else shadow_min_ratio
)  # 默认：2.5 * 0.6 = 1.5 (Doji) 或 2.5 (普通)
```

### 3.3 硬性拒绝条件

以下情况直接返回 `None`，不进入评分系统：

1. **未闭合 K 线**：`is_closed=False`
2. **历史数据不足**：`len(all_bars) < max(ema_period, atr_period + 1)`
3. **实体过大**：`body_ratio > 0.50` (超过 50% 直接拒绝)
4. **止损距离极端**：`sl_distance_pct > effective_max_sl_dist * 2`
5. **质量太差**：`score < 20` 或 `quality_tier == REJECTED`

---

## 4. 趋势过滤逻辑

### 4.1 EMA 趋势判断

```python
ema_trend_is_long = close > ema60
ema_trend_is_short = close < ema60

# 形态方向与 EMA 趋势相反 = 背离
is_divergent = (is_long and ema_trend_is_short) or
               ((not is_long) and ema_trend_is_long)
```

### 4.2 MTF（多重时间框架）趋势过滤

**大级别映射关系**：
- 15m → 参考 1h 趋势
- 1h → 参考 4h 趋势
- 4h → 参考 1d 趋势

**两种模式**：

| 模式 | 行为 |
|------|------|
| `hard` | 逆势信号直接拒绝（返回 `None`） |
| `soft` | 逆势信号标记为 `is_contrarian`，后续扣 15 分 |

```python
if higher_trend and direction_str != higher_trend:
    if pinbar_config.mtf_trend_filter_mode == "hard":
        return 0.0, is_divergent, True  # 直接拒绝
    else:
        is_contrarian = True  # soft 模式：标记逆势
```

### 4.3 趋势评分

```python
dist_to_ema = abs(close - ema60) / ema60

# 距离越近分越高：0%→100 分，3%→0 分
base_trend_score = (0.03 - dist_to_ema) / 0.025 * 100.0

# 背离扣 20 分，逆势扣 15 分
if is_divergent:
    base_trend_score -= 20
if is_contrarian:
    base_trend_score -= 15
```

---

## 5. 波动率过滤

### 5.1 ATR 计算

使用 Wilder's Smoothing Method (RMA)：

```python
# 1. 计算真实波幅 TR
true_ranges = []
for i in range(1, len(highs)):
    tr = max(
        highs[i] - lows[i],
        abs(highs[i] - closes[i-1]),
        abs(lows[i] - closes[i-1])
    )
    true_ranges.append(tr)

# 2. 前 period 个周期使用 SMA
atr = sum(true_ranges[:period]) / period

# 3. 后续周期使用 RMA 平滑
for i in range(period, len(true_ranges)):
    atr = (atr * (period - 1) + true_ranges[i]) / period
```

### 5.2 波动率评分

```python
vol_ratio = total_length / atr14

# 1.2x→0 分，3.0x→100 分
base_vol_score = (vol_ratio - 1.2) / 1.8 * 100.0

# 低于阈值压缩到 30%
if vol_ratio < volatility_atr_multiplier:
    base_vol_score *= 0.3
```

---

## 6. 动态止损机制

### 6.1 动态止损阈值公式

```python
if dynamic_sl_enabled:
    atr_volatility = atr14 / entry_price
    dynamic_sl = dynamic_sl_base + (atr_volatility * dynamic_sl_atr_multiplier)
    # 默认：3.5% + (ATR 波动率 * 0.5)
else:
    dynamic_sl = base_max_sl_dist  # 固定 3.5%
```

**上限保护**：
```python
dynamic_sl = min(dynamic_sl, base_max_sl_dist * 1.5)  # 最多放宽到 5.25%
```

### 6.2 风险扣分

```python
if sl_distance_pct <= effective_max_sl_dist:
    risk_penalty = 0.0  # 安全范围内不扣分

excess_ratio = sl_distance_pct / effective_max_sl_dist
if excess_ratio <= 1.2:
    risk_penalty = (excess_ratio - 1.0) * 50   # 超出 0-20%，扣 0-10 分
elif excess_ratio <= 1.5:
    risk_penalty = 10 + (excess_ratio - 1.2) * 100  # 超出 20-50%，扣 10-40 分
else:
    risk_penalty = 40 + (excess_ratio - 1.5) * 120  # 超出 50% 以上，重罚
```

---

## 7. 动态评分系统

### 7.1 评分维度

| 维度 | 权重 | 评分逻辑 |
|------|------|----------|
| 形态分 (`shape`) | 40% | 影线/总长比 + 实体/总长比 + 影线/实体比 |
| 趋势分 (`trend`) | 30% | 距离 EMA60 远近 + 是否背离 + 是否逆势 |
| 波动分 (`vol`) | 30% | K 线长度/ATR 倍数 |

### 7.2 经典模式公式

```python
# 形态分
s_shadow = (shadow_ratio - 0.6) / 0.3 * 100  # 0.6→0 分，0.9→100 分
s_body = (0.5 - body_ratio) / 0.4 * 100      # 0.1→100 分，0.5→0 分
s_ratio = (shadow_to_body - 1.5) / 2.5 * 100 # 1.5→0 分，4.0→100 分
shape_score = s_shadow * 0.4 + s_body * 0.3 + s_ratio * 0.3

# 趋势分
dist_to_ema = abs(close - ema60) / ema60
trend_score = (0.03 - dist_to_ema) / 0.03 * 100

# 波动分
vol_ratio = total_length / atr14
vol_score = (vol_ratio - 1.2) / 1.8 * 100

# 加权总分
score = shape_score * 0.4 + trend_score * 0.3 + vol_score * 0.3
```

### 7.3 累进模式公式

**基础分 + 奖励分** 机制：

```python
# 形态分 = 基础分 (0-30) + 奖励分 (0-40)
base_shape = 30 * 0.6 (if body_ratio < 0.1) + 30 * 0.4 (if shadow_to_total > 0.6)

bonus_shape = (
    (shadow_to_total - 0.6) * 20 +           # 影线奖励
    (0.1 - body_ratio) * 100 +               # 实体极小奖励
    5 (if body_ratio < 0.05) +               # 十字星奖励
    (shadow_to_body - 3.0) * 2               # 影线/实体比奖励
)
```

---

## 8. 信号质量分级

### 8.1 分级标准

| 等级 | 要求 | 推送策略 |
|------|------|----------|
| **A 级 (精品)** | 实体≤20%、形态分≥70、趋势分≥60、波动分≥60、总分≥70、无风险扣分、非逆势 | 立即推送 + 高亮 |
| **B 级 (普通)** | 实体≤30%、形态分≥50、趋势分≥40、波动分≥40、风险扣分≤10、非逆势 | 正常推送 |
| **C 级 (观察)** | 实体≤40%、形态分≥30、总分≥30、风险扣分≤20 | 仅记录不推送 |
| **REJECTED** | 不满足 C 级最低要求 | 直接丢弃 |

### 8.2 分级逻辑

```python
def _determine_signal_tier(...):
    # C 级最低要求
    if (body_ratio <= 0.40 and shape_score >= 30 and
        total_score >= 30 and risk_penalty <= 20):

        # B 级要求
        if (body_ratio <= 0.30 and shape_score >= 50 and
            trend_score >= 40 and vol_score >= 40 and
            risk_penalty <= 10 and not is_contrarian):

            # A 级要求
            if (body_ratio <= 0.20 and shape_score >= 70 and
                trend_score >= 60 and vol_score >= 60 and
                total_score >= 70 and risk_penalty == 0 and
                not is_contrarian):
                return SignalTier.A_CLASS
            return SignalTier.B_CLASS
        return SignalTier.C_CLASS
    return SignalTier.REJECTED
```

---

## 9. Signal 对象输出

### 9.1 字段说明

```python
@dataclass
class Signal:
    symbol: str              # 交易对 (如 "ETHUSDT")
    interval: str            # 时间级别 (如 "1h")
    direction: str           # "LONG" 或 "SHORT"
    entry_price: float       # 入场价格 (收盘价)
    stop_loss: float         # 止损价格 (影线极值)
    take_profit_1: float     # 目标价位 (1.5R)
    timestamp: int           # 时间戳 (毫秒)
    reason: str              # 命中理由 ("Pinbar+EMA60")
    sl_distance_pct: float   # 止损距离百分比
    score: int               # 信号得分 (0-100)
    score_details: dict      # 打分详情 {shape, trend, vol, quality_tier, risk_penalty}
    shadow_ratio: float      # 影线/实体比
    ema_distance: float      # 价格与 EMA60 距离 (%)
    volatility_atr: float    # K 线波幅/ATR 倍数
    source: str              # 来源："realtime" | "history_scan"
    is_contrarian: bool      # 是否 MTF 逆势
    is_shape_divergent: bool # 是否形态背离
    quality_tier: str        # 质量分级："A" | "B" | "C"
```

### 9.2 止盈止损计算

```python
# 止损位置
stop_loss = low if is_long else high

# 止损距离
actual_sl_distance = abs(entry_price - stop_loss)

# 止盈位置 (1.5R 盈亏比)
take_profit_1 = entry_price + (actual_sl_distance * 1.5) if is_long else entry_price - (actual_sl_distance * 1.5)
```

---

## 10. 配置参数说明

### 10.1 PinbarConfig 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `body_max_ratio` | 0.25 | 实体最大比例（实体/全长） |
| `shadow_min_ratio` | 2.5 | 影线最小比例（影线/实体） |
| `volatility_atr_multiplier` | 1.2 | 波幅 ATR 乘数过滤 |
| `doji_threshold` | 0.05 | 十字星阈值（实体/全长 < 5%） |
| `doji_shadow_bonus` | 0.6 | 十字星影线比例放宽系数 |
| `mtf_trend_filter_mode` | "soft" | MTF 趋势过滤模式："soft" | "hard" |
| `dynamic_sl_enabled` | True | 是否启用动态止损 |
| `dynamic_sl_base` | 0.035 | 动态止损基准值 (3.5%) |
| `dynamic_sl_atr_multiplier` | 0.5 | ATR 对止损的贡献系数 |
| `atr_volatility_lookback` | 20 | ATR 波动率回溯周期 |
| `shape_divergence_penalty` | 20 | 形态 - 趋势背离扣分 |

### 10.2 ScoringWeights 参数

| 参数 | 默认值 | 约束 |
|------|--------|------|
| `w_shape` | 0.4 | 形态权重 |
| `w_trend` | 0.4 | 趋势权重 |
| `w_vol` | 0.2 | 波动权重 |
| **总和** | 1.0 | `w_shape + w_trend + w_vol == 1.0` |

---

## 11. 使用示例

### 11.1 基本调用

```python
from domain.strategy.pinbar import PinbarStrategy
from core.entities import Bar, PinbarConfig, ScoringWeights

# 实例化策略
strategy = PinbarStrategy(ema_period=60, atr_period=14)

# 准备数据
current_bar = Bar(...)  # 当前闭合 K 线
history_bars = [...]    # 历史 K 线列表 (至少 60 根)

# 执行评估
signal = strategy.evaluate(
    current_bar=current_bar,
    history_bars=history_bars,
    max_sl_dist=0.035,  # 最大止损距离 3.5%
    weights=ScoringWeights(w_shape=0.4, w_trend=0.4, w_vol=0.2),
    higher_trend="LONG",  # MTF 大级别趋势
    pinbar_config=PinbarConfig()
)

if signal:
    print(f"发现信号：{signal.symbol} {signal.direction}")
    print(f"入场：{signal.entry_price}, 止损：{signal.stop_loss}, 目标：{signal.take_profit_1}")
    print(f"评分：{signal.score}, 等级：{signal.quality_tier}")
```

### 11.2 历史回测扫描

```python
# HistoryScanner 中逐根回放
for i, bar in enumerate(target_bars):
    # MTF 穿越式趋势校验
    higher_trend = scanner._compute_historical_trend(
        bar.timestamp, bar.close, higher_bars
    )

    # 调用策略引擎
    signal = strategy.evaluate(
        current_bar=bar,
        history_bars=history_window,
        max_sl_dist=max_sl_dist,
        weights=weights,
        higher_trend=higher_trend,
        pinbar_config=pinbar_config
    )

    if signal:
        signal.source = "history_scan"
        signals_found.append(signal)
```

---

## 12. 优化特性 (v2.0)

### 12.1 优化 1：软性过滤 (Soft Filter)

**优化前**：级联拒绝，任一维度不达标直接返回 `None`

**优化后**：评分累积，不达标仅给低分，由总分决定

```python
# 波动率过滤：不直接拒绝，给低分
if vol_ratio < volatility_atr_multiplier:
    base_vol_score *= 0.3  # 压缩到 30%
```

### 12.2 优化 2：信号分级 (Signal Tiers)

**优化前**：二元分类（有信号/无信号）

**优化后**：三级分类（A 级精品、B 级普通、C 级观察）

```python
# C 级信号仅记录不推送
if quality_tier == 'C':
    logger.info(f"观察到 C 级信号 (仅记录不推送)")
    continue
```

### 12.3 优化 3：动态止损 (Dynamic SL)

**优化前**：固定 3.5% 止损阈值

**优化后**：基于 ATR 波动率自适应调整

```python
dynamic_sl = 0.035 + (atr14 / entry_price) * 0.5
# 高波动市场自动放宽止损，低波动市场收紧
```

### 12.4 优化 4：十字星边界处理

**优化前**：十字星可能被误判为无效

**优化后**：识别 Doji 并放宽影线要求 40%

```python
if is_doji:
    effective_shadow_ratio *= 0.6  # 2.5 → 1.5
```

---

## 13. 边界情况处理

### 13.1 零值保护

```python
# 防止除以零
if ema60 == 0:
    ema_distance = 0.0
if atr14 == 0:
    volatility_atr = 0.0
if body_length == 0:
    shadow_ratio = 999.0  # 十字星特殊情况
```

### 13.2 数据不足处理

```python
if len(all_bars) < max(ema_period, atr_period + 1):
    return None  # 数据不足，无法计算指标
```

### 13.3 方向模糊处理

```python
# 上下影线都满足条件时，取更长的一方
if valid_long_shape and valid_short_shape:
    is_long = lower_shadow > upper_shadow
elif valid_long_shape:
    is_long = True
elif valid_short_shape:
    is_long = False
else:
    return None  # 无明确方向
```

---

## 14. 性能优化

### 14.1 EMA 预计算

```python
# 冷启动预热：预加载 100 根历史 K 线
await self._warmup_history()
# 解决 EMA60 需要 60 根历史才能计算的冷启动问题
```

### 14.2 滑动窗口

```python
# 只保留最近 100 根 K 线，防止内存无限增长
current_history.append(current_bar)
if len(current_history) > 100:
    current_history.pop(0)
```

---

## 15. 测试覆盖

### 15.1 单元测试要点

1. **形态识别**：验证各种 Pinbar 形态的识别准确性
2. **边界条件**：十字星、零长度、数据不足等边界情况
3. **评分计算**：验证各维度分数计算正确性
4. **质量分级**：验证 A/B/C 分级逻辑
5. **动态止损**：验证 ATR 波动率对止损的影响

### 15.2 集成测试要点

1. **实时流处理**：验证 WebSocket 实时 K 线触发逻辑
2. **历史扫描**：验证 HistoryScanner 回放准确性
3. **MTF 趋势校验**：验证大级别趋势匹配正确性
4. **推送逻辑**：验证 A/B 级推送、C 级不推送

---

## 16. 总结

Pinbar 策略是一个成熟、可配置、易扩展的交易信号检测引擎，核心特性：

- ✅ **纯领域设计**：零副作用，便于测试和维护
- ✅ **多维度评分**：形态 + 趋势 + 波动三重过滤
- ✅ **动态适应性**：基于 ATR 的自适应止损和波动率调整
- ✅ **质量分级**：A/B/C 三级分类，精准推送高价值信号
- ✅ **MTF 趋势过滤**：多时间框架校验，减少逆势信号
- ✅ **零执行**：严格遵守只监测不交易的安全底线
