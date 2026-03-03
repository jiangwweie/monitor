# Pinbar 信号检测优化 v2.0

## 优化概述

本次优化将四层**级联拒绝过滤**（Cascade Rejection）改为**评分累积模式**（Score Accumulation），并引入**信号质量分级**（Signal Tiers）机制。

### 优化目标

1. **减少信号漏报** - 原级联过滤过于严格，大量"边缘但有效"的 Pinbar 被漏掉
2. **提高信号质量** - 通过分级制度，让用户能区分精品信号和普通信号
3. **保持参数热加载** - 所有形态识别参数仍可通过 `/api/config` 接口动态调整

---

## 核心变更

### 变更前：级联拒绝模式

```
K 线闭合 → 形态过滤 (不满足→拒绝) → 趋势过滤 (不满足→拒绝) →
         波动率过滤 (不满足→拒绝) → 止损过滤 (不满足→拒绝) → 评分 → 信号
```

### 变更后：评分累积模式

```
K 线闭合 → 形态度量 → 趋势度量 → 波动率度量 → 风险度量 →
         综合评分 → 质量分级 (A/B/C) → 信号 (仅 C 级不推送)
```

---

## 四层过滤优化详情

### 第一层：形态识别优化

**原逻辑**：
- 实体 > 25% → 直接拒绝
- 影线 < 2.5×实体 → 直接拒绝

**新逻辑**：
- 实体 > 50% → 硬性拒绝
- 实体 25%~50% → 继续，形态分降低
- 影线比例不足 → 放宽到 60% 阈值，允许边缘信号进入评分系统

**代码变更**：
```python
# 原逻辑
if body_length > total_length * pinbar_config.body_max_ratio:
    return None

# 新逻辑
if body_ratio > 0.50:  # HARD_REJECT_BODY_RATIO
    return None
# 否则继续，让评分系统处理
```

### 第二层：趋势过滤优化

**原逻辑**：
- Hard 模式：逆势信号直接拒绝
- Soft 模式：允许逆势，评分 -15 分

**新逻辑**：
- 全部改为 soft 模式（hard 模式保留但可通过配置切换）
- 逆势信号只扣分，不拒绝

**代码变更**：
```python
# 原逻辑
if pinbar_config.mtf_trend_filter_mode == "hard":
    return None  # 逆势直接拒绝

# 新逻辑
is_contrarian = False
if higher_trend and direction_str != higher_trend:
    if pinbar_config.mtf_trend_filter_mode == "hard":
        return 0.0, is_divergent, True  # 返回 0 分
    else:
        is_contrarian = True  # 标记为逆势，后续扣分
```

### 第三层：波动率过滤优化

**原逻辑**：
- K 线总长 < 1.2×ATR → 直接拒绝

**新逻辑**：
- 低于阈值 → 波动分压缩到 30%，不拒绝

**代码变更**：
```python
# 原逻辑
if total_length <= pinbar_config.volatility_atr_multiplier * atr14:
    return None

# 新逻辑
vol_ratio = total_length / atr14
base_vol_score = min(100.0, max(0.0, (vol_ratio - 1.2) / 1.8 * 100.0))
if vol_ratio < volatility_atr_multiplier:
    base_vol_score *= 0.3  # 压缩到 30%
```

### 第四层：止损风控优化

**原逻辑**：
- 止损距离 > 动态阈值 → 直接拒绝

**新逻辑**：
- 超出阈值 → 计算风险扣分
- 仅当超过阈值 2 倍时才硬性拒绝

**代码变更**：
```python
# 原逻辑
if sl_distance_pct > effective_max_sl_dist:
    return None

# 新逻辑
risk_penalty = self._calculate_risk_penalty(sl_distance_pct, effective_max_sl_dist)
if sl_distance_pct > effective_max_sl_dist * 2:
    return None  # 仅极端情况拒绝
```

---

## 信号质量分级 (Signal Tiers)

### 分级标准

| 等级 | 要求 | 处理方式 |
|------|------|----------|
| A 级 (精品) | 实体≤20%, 形态分≥70, 趋势分≥60, 波动分≥60, 总分≥70, 无风险扣分，非逆势 | 推送 + 高亮标记 |
| B 级 (普通) | 实体≤30%, 形态分≥50, 趋势分≥40, 波动分≥40, 风险扣分≤10, 非逆势 | 正常推送 |
| C 级 (观察) | 实体≤40%, 形态分≥30, 总分≥30, 风险扣分≤20 | 仅记录，不推送 |
| 拒绝 | 不满足 C 级要求或总分<20 | 直接丢弃 |

### 分级代码

```python
def _determine_signal_tier(self, ...) -> SignalTier:
    # C 级最低要求
    if (shape_metrics.body_ratio <= 0.40 and
        shape_score >= 30 and total_score >= 30 and risk_penalty <= 20):

        # B 级要求
        if (shape_metrics.body_ratio <= 0.30 and
            shape_score >= 50 and trend_score >= 40 and
            vol_score >= 40 and risk_penalty <= 10 and
            not is_contrarian):

            # A 级要求
            if (shape_metrics.body_ratio <= 0.20 and
                shape_score >= 70 and trend_score >= 60 and
                vol_score >= 60 and total_score >= 70 and
                risk_penalty == 0 and not is_contrarian):
                return SignalTier.A_CLASS

            return SignalTier.B_CLASS

        return SignalTier.C_CLASS

    return SignalTier.REJECTED
```

---

## 评分系统详解

### 形态评分 (Shape Score, 0-100)

```python
# 影线/总长比 (0.6→0 分，0.9→100 分)
s_shadow = (shadow_to_total - 0.6) / 0.3 * 100

# 实体/总长比 (越小越好：0.1→100 分，0.5→0 分)
s_body = (0.5 - body_to_total) / 0.4 * 100

# 影线/实体比 (越高越好)
s_ratio = (shadow_to_body - 1.5) / 2.5 * 100

# 综合得分
shape_score = s_shadow * 0.4 + s_body * 0.3 + s_ratio * 0.3
```

### 趋势评分 (Trend Score, 0-100)

```python
# 基础分：距离 EMA60 越近分越高
base_trend_score = (0.03 - dist_to_ema) / 0.025 * 100

# 背离扣分
if is_divergent:
    base_trend_score -= 20

# MTF 逆势扣分
if is_contrarian:
    base_trend_score -= 15
```

### 波动评分 (Vol Score, 0-100)

```python
# 1.2x→0 分，3.0x→100 分
base_vol_score = (vol_ratio - 1.2) / 1.8 * 100

# 低于阈值压缩到 30%
if vol_ratio < volatility_atr_multiplier:
    base_vol_score *= 0.3
```

### 风险扣分 (Risk Penalty)

```python
if sl_distance_pct <= effective_max_sl_dist:
    return 0.0  # 安全范围内，不扣分

excess_ratio = sl_distance_pct / effective_max_sl_dist
if excess_ratio <= 1.2:
    return (excess_ratio - 1.0) * 50  # 超出 0-20%，扣 0-10 分
elif excess_ratio <= 1.5:
    return 10 + (excess_ratio - 1.2) * 100  # 超出 20-50%，扣 10-40 分
else:
    return 40 + (excess_ratio - 1.5) * 120  # 超出 50% 以上，额外重罚
```

---

## 推送策略变更

### 原逻辑
所有有效信号统一推送

### 新逻辑
```python
# 根据信号质量分级决定推送策略
quality_tier = getattr(signal, 'quality_tier', 'B')

if quality_tier == 'C':
    logger.info(f"📝 观察到 C 级信号：{signal} (仅记录不推送)")
    continue  # C 级信号只记录，不推送

# A/B 级信号推送
tier_prefix = "🌟【精品信号】" if quality_tier == 'A' else "📢【普通信号】"
markdown_message = f"{tier_prefix}\n\n{markdown_message}"
await self.notifier.send_markdown(markdown_message)
```

### 推送消息增强

推送消息现在包含信号等级标记：

```
🌟【精品信号】

**🚨 发现新交易信号 (Pinbar+EMA60)** [🌟 精品]
**交易对**: #BTCUSDT
**级别**: 1h | **方向**: 🟢 LONG
...
- 信号等级：`A 级`
```

---

## 参数热加载兼容性

所有形态识别参数保持通过 `PinbarConfig` dataclass 管理，可通过 `/api/config` 接口热更新：

```python
# PinbarConfig 参数列表
body_max_ratio: float = 0.25           # 实体最大比例
shadow_min_ratio: float = 2.5          # 影线最小比例
volatility_atr_multiplier: float = 1.2 # 波幅 ATR 乘数过滤
doji_threshold: float = 0.05           # 十字星阈值
doji_shadow_bonus: float = 0.6         # 十字星影线比例放宽系数
mtf_trend_filter_mode: str = "soft"    # MTF 趋势过滤模式
dynamic_sl_enabled: bool = True        # 是否启用动态止损
dynamic_sl_base: float = 0.035         # 动态止损基准值
dynamic_sl_atr_multiplier: float = 0.5 # ATR 对止损的贡献系数
shape_divergence_penalty: int = 20     # 形态 - 趋势背离扣分
```

---

## 预期效果

| 指标 | 优化前 | 优化后 | 说明 |
|------|--------|--------|------|
| 信号检出率 | 基准 | +30%~50% | 边缘信号不再被漏掉 |
| A 级信号推送 | 无区分 | 高亮标记 | 用户可快速识别精品 |
| C 级信号骚扰 | 正常推送 | 仅记录 | 降低低质量信号打扰 |
| 参数可调性 | ✅ 支持 | ✅ 支持 | 保持热加载兼容性 |

---

## 后续优化方向

1. **延迟确认机制** - 对波动率不足但形态良好的信号，等下一根 K 线确认
2. **动态自适应阈值** - 根据市场状态（横盘/趋势）动态调整过滤阈值
3. **回测分析工具** - 分析 C 级信号的历史表现，优化分级阈值

---

## 相关文件

- 策略引擎：`domain/strategy/pinbar.py`
- 评分引擎：`domain/strategy/scoring.py`
- 实体定义：`core/entities.py`
- 监控引擎：`application/monitor_engine.py`
- 流程文档：`docs/pinbar_detection_flow.md`
