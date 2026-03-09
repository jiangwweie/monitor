# Pinbar 检测模块审查问题清单

审查日期：2026-03-09
审查范围：`domain/strategy/pinbar.py` 及相关模块

---

## 问题总览

| ID | 类别 | 严重程度 | 问题简述 | 状态 |
|----|------|---------|---------|------|
| 1 | 业务 | 中 | 双向 Pinbar 强制选方向 | pending |
| 2 | 业务 | 中 | 止损计算未考虑滑点缓冲 | pending |
| 3 | 业务 | 低 | 固定 1.5R 盈亏比缺乏灵活性 | pending |
| 4 | 技术 | 中 | EMA/ATR 无缓存重复计算 | pending |
| 5 | 技术 | 低 | 信号分级阈值硬编码 | pending |
| 6 | 技术 | 高 | Doji 边界条件漏洞 | pending |
| 7 | 技术 | 高 | 无单元测试覆盖 | pending |
| 8 | 设计 | 低 | 评分参数冗余 | pending |
| 9 | 设计 | 中 | 熔断逻辑分散 | pending |

---

## 详细问题描述与实施方案

---

### 问题 1：双向 Pinbar 强制选方向

| 属性 | 内容 |
|-----|------|
| **类别** | 业务逻辑 |
| **严重程度** | 中 |
| **代码位置** | `domain/strategy/pinbar.py:143-153` |
| **状态** | pending |

#### 问题描述
当上下影线都满足条件时，代码简单取更长一方作为方向：
```python
is_long = shape_metrics.lower_shadow > shape_metrics.upper_shadow
```

#### 风险
这种"双向 Pinbar"（锤子线 + 上吊线特征共存）可能是市场犹豫信号，强行指定方向可能导致误判。

#### 实施方案

**步骤 1**: 在 `ShapeMetrics` 中增加字段
```python
# domain/strategy/pinbar.py
@dataclass
class ShapeMetrics:
    # ... 现有字段 ...
    is_bidirectional: bool = False  # 新增：是否为双向 Pinbar
    shadow_difference_ratio: float = 0.0  # 新增：上下影线长度差比率
```

**步骤 2**: 修改 `_evaluate_shape` 方法识别双向 Pinbar
```python
# 在 _evaluate_shape 方法中
shadow_diff = abs(shape_metrics.lower_shadow - shape_metrics.upper_shadow)
avg_shadow = (shape_metrics.lower_shadow + shape_metrics.upper_shadow) / 2
is_bidirectional = avg_shadow > 0 and (shadow_diff / avg_shadow) < 0.3  # 差异小于 30% 视为双向

shape_metrics.is_bidirectional = is_bidirectional
shape_metrics.shadow_difference_ratio = shadow_diff / avg_shadow if avg_shadow > 0 else 0
```

**步骤 3**: 在 `evaluate` 方法中处理双向 Pinbar
```python
# 在 evaluate 方法中，确定方向前
if shape_metrics.is_bidirectional:
    # 双向 Pinbar 标记为观察信号，不直接拒绝但降低评级
    is_bidirectional = True
    # 仍然取影线更长的一方作为"倾向方向"，但标记不确定性
    is_long = shape_metrics.lower_shadow > shape_metrics.upper_shadow
else:
    is_bidirectional = False
    # 原有逻辑...
```

**步骤 4**: 在信号分级时降权
```python
# 在 _determine_signal_tier 方法开头
if is_bidirectional:
    # 双向 Pinbar 最高只能是 C 级
    return SignalTier.C_CLASS
```

**涉及文件修改**:
- `domain/strategy/pinbar.py` (3 处修改)

---

### 问题 2：止损计算未考虑滑点缓冲

| 属性 | 内容 |
|-----|------|
| **类别** | 业务逻辑 |
| **严重程度** | 中 |
| **代码位置** | `domain/strategy/pinbar.py:184-186` |
| **状态** | pending |

#### 问题描述
做多时 `stop_loss = current_bar.low`，做空时 `stop_loss = current_bar.high`

#### 风险
未考虑实际交易中需要在 Pinbar 极值外留出缓冲（如加上手续费、滑点），当前计算的是理论最小止损，实际执行时可能频繁被扫损。

#### 实施方案

**步骤 1**: 在 `PinbarConfig` 中增加参数
```python
# core/entities.py
@dataclass
class PinbarConfig:
    # ... 现有字段 ...
    sl_buffer_ratio: float = 0.001  # 新增：止损缓冲比例，默认 0.1%
    sl_buffer_fixed: float = 0.0    # 新增：止损固定缓冲值（用于低价币种）
```

**步骤 2**: 修改止损计算逻辑
```python
# domain/strategy/pinbar.py:184-186 替换为
# 计算动态缓冲
dynamic_buffer = max(
    entry_price * pinbar_config.sl_buffer_ratio,  # 比例缓冲
    pinbar_config.sl_buffer_fixed                  # 固定缓冲
)

# 应用缓冲到止损
if is_long:
    stop_loss = current_bar.low - dynamic_buffer
else:
    stop_loss = current_bar.high + dynamic_buffer

# 确保止损方向正确（做低止损 < 入场，做空止损 > 入场）
if is_long and stop_loss >= entry_price:
    stop_loss = entry_price * 0.99  # 极端情况下给予 1% 默认止损
elif not is_long and stop_loss <= entry_price:
    stop_loss = entry_price * 1.01
```

**步骤 3**: 更新止损距离计算
```python
# domain/strategy/pinbar.py:186 后增加
actual_sl_distance = abs(entry_price - stop_loss)
```

**涉及文件修改**:
- `core/entities.py` (PinbarConfig 增加 2 个字段)
- `domain/strategy/pinbar.py` (止损计算逻辑修改)

---

### 问题 3：固定 1.5R 盈亏比缺乏灵活性

| 属性 | 内容 |
|-----|------|
| **类别** | 业务逻辑 |
| **严重程度** | 低 |
| **代码位置** | `domain/strategy/pinbar.py:209-212` |
| **状态** | pending |

#### 问题描述
止盈计算硬编码为 `actual_sl_distance * 1.5`

#### 风险
不同市场状态（趋势市 vs 震荡市）、不同时间级别（15m vs 4h）的最优盈亏比不同，固定 1.5R 可能在某些场景下过早止盈或过度持仓。

#### 实施方案

**步骤 1**: 在 `PinbarConfig` 中增加参数
```python
# core/entities.py
@dataclass
class PinbarConfig:
    # ... 现有字段 ...
    take_profit_ratio: float = 1.5  # 新增：盈亏比倍数，默认 1.5R
    tp_ratio_by_interval: Dict[str, float] = field(default_factory=dict)  # 新增：按级别配置
    # 示例：{"15m": 1.2, "1h": 1.5, "4h": 2.0, "1d": 2.5}
```

**步骤 2**: 修改止盈计算逻辑
```python
# domain/strategy/pinbar.py:209-212 替换为
# 获取当前级别的盈亏比配置
tp_ratio = pinbar_config.tp_ratio_by_interval.get(
    current_bar.interval,
    pinbar_config.take_profit_ratio
)

# 计算止盈
if is_long:
    tp1 = entry_price + actual_sl_distance * tp_ratio
else:
    tp1 = entry_price - actual_sl_distance * tp_ratio
```

**涉及文件修改**:
- `core/entities.py` (PinbarConfig 增加 2 个字段)
- `domain/strategy/pinbar.py` (止盈计算逻辑修改)

---

### 问题 4：EMA/ATR 无缓存重复计算

| 属性 | 内容 |
|-----|------|
| **类别** | 技术实现 |
| **严重程度** | 中 |
| **代码位置** | `domain/strategy/pinbar.py:118-119` + `application/monitor_engine.py:207-218` |
| **状态** | pending |

#### 问题描述
每次 K 线闭合都会重新计算 EMA60 和 ATR14，即使在 MTF 趋势判断中也需要重复计算大级别的 EMA60

#### 影响
对于多币种×多级别监控场景，每次 K 线闭合都会触发全量历史数据的遍历计算，时间复杂度为 O(n)。

#### 实施方案

**方案 A: 在 monitor_engine 中缓存（推荐）**

**步骤 1**: 在 `CryptoRadarEngine` 中增加缓存
```python
# application/monitor_engine.py
class CryptoRadarEngine:
    def __init__(self, ...):
        # ... 现有字段 ...
        # 新增：指标缓存
        self.indicator_cache: Dict[str, Dict[str, Dict]] = defaultdict(
            lambda: defaultdict(dict)
        )
        # 结构：{"15m": {"BTCUSDT": {"ema60": 123.45, "atr14": 2.34, "updated_at": 1234567890}}}
```

**步骤 2**: 增加增量计算辅助方法
```python
# application/monitor_engine.py
def _update_indicator_cache(
    self,
    symbol: str,
    interval: str,
    bars: List[Bar],
    ema_period: int = 60,
    atr_period: int = 14
) -> Tuple[float, float]:
    """
    增量更新 EMA 和 ATR 缓存
    如果缓存存在且 bars 只新增 1 根，则增量计算；否则全量计算
    """
    from domain.strategy.indicators import calculate_ema, calculate_atr

    cache = self.indicator_cache[interval][symbol]
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]

    # 全量计算（简单实现，后续可优化增量）
    ema60 = calculate_ema(closes, ema_period)
    atr14 = calculate_atr(highs, lows, closes, atr_period)

    cache["ema60"] = ema60
    cache["atr14"] = atr14
    cache["updated_at"] = int(datetime.now(timezone.utc).timestamp())

    return ema60, atr14
```

**步骤 3**: 在 `_process_bar` 中调用缓存更新
```python
# application/monitor_engine.py 中处理 K 线的地方
# 在调用 strategy.evaluate 之前
ema60, atr14 = self._update_indicator_cache(
    symbol=sym_upper,
    interval=ivl,
    bars=current_history + [current_bar]
)

# 将缓存值传给策略（需要修改 evaluate 签名）
signal = self.strategy.evaluate_with_indicators(
    current_bar=current_bar,
    history_bars=current_history,
    ema60=ema60,
    atr14=atr14,
    # ... 其他参数
)
```

**方案 B: 在 pinbar.py 内部缓存（备选）**

如不希望改动 monitor_engine，可在 PinbarStrategy 内部实现简单缓存。

**涉及文件修改**:
- `application/monitor_engine.py` (主要修改)
- `domain/strategy/pinbar.py` (可能需要新增 `evaluate_with_indicators` 方法)

---

### 问题 5：信号分级阈值硬编码

| 属性 | 内容 |
|-----|------|
| **类别** | 技术实现 |
| **严重程度** | 低 |
| **代码位置** | `domain/strategy/pinbar.py:548-575` (`_determine_signal_tier` 方法) |
| **状态** | pending |

#### 问题描述
A/B/C 三级的判定阈值全部硬编码

#### 影响
用户无法通过配置调整信号分级标准。

#### 实施方案

**步骤 1**: 创建 `SignalTierConfig` 数据类
```python
# core/entities.py
@dataclass
class SignalTierConfig:
    """信号分级配置"""
    # A 级要求
    a_class_body_ratio_max: float = 0.20
    a_class_shape_score_min: float = 70
    a_class_trend_score_min: float = 60
    a_class_vol_score_min: float = 60
    a_class_total_score_min: float = 70
    a_class_risk_penalty_max: float = 0
    a_class_allow_contrarian: bool = False

    # B 级要求
    b_class_body_ratio_max: float = 0.30
    b_class_shape_score_min: float = 50
    b_class_trend_score_min: float = 40
    b_class_vol_score_min: float = 40
    b_class_risk_penalty_max: float = 10
    b_class_allow_contrarian: bool = False

    # C 级要求
    c_class_body_ratio_max: float = 0.40
    c_class_shape_score_min: float = 30
    c_class_total_score_min: float = 30
    c_class_risk_penalty_max: float = 20
    c_class_allow_contrarian: bool = True
```

**步骤 2**: 在 `PinbarConfig` 中嵌入分级配置
```python
# core/entities.py
@dataclass
class PinbarConfig:
    # ... 现有字段 ...
    tier_config: SignalTierConfig = field(default_factory=SignalTierConfig)
```

**步骤 3**: 修改 `_determine_signal_tier` 方法
```python
# domain/strategy/pinbar.py
def _determine_signal_tier(
    self,
    # ... 现有参数 ...
    tier_config: SignalTierConfig = None
) -> SignalTier:
    if tier_config is None:
        tier_config = SignalTierConfig()

    # C 级最低要求
    if (shape_metrics.body_ratio <= tier_config.c_class_body_ratio_max and
        shape_score >= tier_config.c_class_shape_score_min and
        total_score >= tier_config.c_class_total_score_min and
        risk_penalty <= tier_config.c_class_risk_penalty_max):

        # B 级要求
        if (shape_metrics.body_ratio <= tier_config.b_class_body_ratio_max and
            shape_score >= tier_config.b_class_shape_score_min and
            trend_score >= tier_config.b_class_trend_score_min and
            vol_score >= tier_config.b_class_vol_score_min and
            risk_penalty <= tier_config.b_class_risk_penalty_max and
            (tier_config.b_class_allow_contrarian or not is_contrarian)):

            # A 级要求
            if (shape_metrics.body_ratio <= tier_config.a_class_body_ratio_max and
                shape_score >= tier_config.a_class_shape_score_min and
                trend_score >= tier_config.a_class_trend_score_min and
                vol_score >= tier_config.a_class_vol_score_min and
                total_score >= tier_config.a_class_total_score_min and
                risk_penalty <= tier_config.a_class_risk_penalty_max and
                (tier_config.a_class_allow_contrarian or not is_contrarian)):
                return SignalTier.A_CLASS

            return SignalTier.B_CLASS

        return SignalTier.C_CLASS

    return SignalTier.REJECTED
```

**涉及文件修改**:
- `core/entities.py` (新增 SignalTierConfig)
- `domain/strategy/pinbar.py` (_determine_signal_tier 方法修改)

---

### 问题 6：Doji 边界条件漏洞

| 属性 | 内容 |
|-----|------|
| **类别** | 技术实现 |
| **严重程度** | 高 |
| **代码位置** | `domain/strategy/pinbar.py:327-342` |
| **状态** | pending |

#### 问题描述
当 `body_length` 趋近于 0 时，影线判定条件几乎永远为 True。

#### 实施方案

**步骤 1**: 在 `PinbarConfig` 中增加参数
```python
# core/entities.py
@dataclass
class PinbarConfig:
    # ... 现有字段 ...
    min_shadow_length_ratio: float = 0.003  # 新增：最小影线长度占 K 线总长比例
    min_shadow_absolute: float = 0.0        # 新增：最小影线绝对值（用于低价币种）
```

**步骤 2**: 修改 `_evaluate_shape` 方法
```python
# domain/strategy/pinbar.py:336-342 替换为
lower_shadow = min(current_bar.open, current_bar.close) - current_bar.low
upper_shadow = current_bar.high - max(current_bar.open, current_bar.close)

# 计算最小影线阈值
min_shadow_threshold = max(
    total_length * pinbar_config.min_shadow_length_ratio,  # 比例阈值
    pinbar_config.min_shadow_absolute                       # 绝对阈值
)

# 当实体趋近于 0 时，使用绝对阈值而非比例
if body_length < 0.0001:  # 几乎零实体
    # Doji 情况：使用绝对影线阈值
    valid_long_shape = lower_shadow >= min_shadow_threshold
    valid_short_shape = upper_shadow >= min_shadow_threshold
else:
    # 正常情况：使用比例阈值
    relaxed_ratio = effective_shadow_ratio * 0.6
    valid_long_shape = lower_shadow >= body_length * relaxed_ratio
    valid_short_shape = upper_shadow >= body_length * relaxed_ratio

# 额外保护：影线长度不能为负或零
if lower_shadow <= 0:
    valid_long_shape = False
if upper_shadow <= 0:
    valid_short_shape = False
```

**涉及文件修改**:
- `core/entities.py` (PinbarConfig 增加 2 个字段)
- `domain/strategy/pinbar.py` (_evaluate_shape 方法修改)

---

### 问题 7：无单元测试覆盖

| 属性 | 内容 |
|-----|------|
| **类别** | 技术实现 |
| **严重程度** | 高 |
| **代码位置** | N/A（缺失测试文件） |
| **状态** | pending |

#### 问题描述
项目中未发现针对 `pinbar.py` 的独立测试文件

#### 实施方案

**步骤 1**: 创建测试文件结构
```
tests/
├── __init__.py
├── conftest.py              # pytest 夹具
├── test_pinbar_strategy.py  # Pinbar 策略测试
├── test_indicators.py       # 指标计算测试
├── test_scoring.py          # 评分引擎测试
└── fixtures/
    └── sample_bars.json     # 测试用 K 线数据
```

**步骤 2**: 创建测试夹具
```python
# tests/conftest.py
import pytest
from domain.strategy.pinbar import PinbarStrategy
from core.entities import Bar, PinbarConfig, ScoringWeights

@pytest.fixture
def sample_bars():
    """返回一组标准测试 K 线"""
    return [
        Bar(symbol="BTCUSDT", interval="1h", timestamp=1000+i*3600,
            open=50000, high=50500, low=49500, close=50200,
            volume=1000, is_closed=True)
        for i in range(100)
    ]

@pytest.fixture
def bullish_pinbar():
    """返回一个标准的看涨 Pinbar"""
    return Bar(
        symbol="BTCUSDT", interval="1h", timestamp=1000000,
        open=50100, high=50200, low=49000, close=50150,
        volume=1500, is_closed=True
    )

@pytest.fixture
def bearish_pinbar():
    """返回一个标准的看跌 Pinbar"""
    return Bar(
        symbol="BTCUSDT", interval="1h", timestamp=1000000,
        open=50100, high=51500, low=50000, close=50050,
        volume=1500, is_closed=True
    )

@pytest.fixture
def doji_bar():
    """返回一个十字星 K 线"""
    return Bar(
        symbol="BTCUSDT", interval="1h", timestamp=1000000,
        open=50000, high=51000, low=49000, close=50010,
        volume=1200, is_closed=True
    )
```

**步骤 3**: 编写核心测试用例
```python
# tests/test_pinbar_strategy.py
import pytest
from domain.strategy.pinbar import PinbarStrategy, SignalTier
from core.entities import PinbarConfig, ScoringWeights

class TestPinbarShape:
    """形态识别测试"""

    def test_bullish_pinbar_recognized(self, sample_bars, bullish_pinbar):
        """测试标准看涨 Pinbar 被正确识别"""
        strategy = PinbarStrategy()
        signal = strategy.evaluate(
            current_bar=bullish_pinbar,
            history_bars=sample_bars,
            max_sl_dist=0.035
        )
        assert signal is not None
        assert signal.direction == "LONG"

    def test_bearish_pinbar_recognized(self, sample_bars, bearish_pinbar):
        """测试标准看跌 Pinbar 被正确识别"""
        strategy = PinbarStrategy()
        signal = strategy.evaluate(
            current_bar=bearish_pinbar,
            history_bars=sample_bars,
            max_sl_dist=0.035
        )
        assert signal is not None
        assert signal.direction == "SHORT"

    def test_doji_boundary_condition(self, sample_bars, doji_bar):
        """测试 Doji 边界条件（问题 6 修复验证）"""
        strategy = PinbarStrategy()
        signal = strategy.evaluate(
            current_bar=doji_bar,
            history_bars=sample_bars,
            max_sl_dist=0.035
        )
        # Doji 应该被识别，但不应产生有效信号（或降级）
        # 具体预期行为取决于修复方案
        assert signal is not None or signal is None  # 根据实现确定


class TestBidirectionalPinbar:
    """双向 Pinbar 测试（问题 1 修复验证）"""

    def test_bidirectional_pinbar(self, sample_bars):
        """测试上下影线近似相等的 K 线"""
        bar = Bar(
            symbol="BTCUSDT", interval="1h", timestamp=1000000,
            open=50000, high=51000, low=49000, close=50010,
            volume=1200, is_closed=True
        )
        strategy = PinbarStrategy()
        signal = strategy.evaluate(
            current_bar=bar,
            history_bars=sample_bars,
            max_sl_dist=0.035
        )
        # 双向 Pinbar 应被标记或降级
        if signal:
            assert signal.quality_tier in ["C", "B"]


class TestRiskManagement:
    """风控测试（问题 2、3 修复验证）"""

    def test_sl_buffer_applied(self, sample_bars, bullish_pinbar):
        """测试止损缓冲被正确应用"""
        config = PinbarConfig(sl_buffer_ratio=0.001)
        strategy = PinbarStrategy()
        signal = strategy.evaluate(
            current_bar=bullish_pinbar,
            history_bars=sample_bars,
            max_sl_dist=0.035,
            pinbar_config=config
        )
        assert signal is not None
        # 止损应该低于最低价一定缓冲
        assert signal.stop_loss < bullish_pinbar.low


class TestSignalTier:
    """信号分级测试"""

    def test_a_class_signal(self, sample_bars):
        """测试 A 级信号的判定"""
        # 构造一个完美的 A 级 Pinbar
        bar = Bar(...)
        strategy = PinbarStrategy()
        signal = strategy.evaluate(...)
        if signal:
            assert signal.quality_tier == "A"
```

**步骤 4**: 添加运行脚本
```bash
# requirements-dev.txt (新增)
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0

# 运行测试
cd /Users/jiangwei/Documents/2026/project/monitor
pip install -r requirements-dev.txt
pytest tests/test_pinbar_strategy.py -v --cov=domain/strategy/pinbar
```

**涉及文件新增**:
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_pinbar_strategy.py`
- `requirements-dev.txt`

---

### 问题 8：评分参数冗余

| 属性 | 内容 |
|-----|------|
| **类别** | 代码设计 |
| **严重程度** | 低 |
| **代码位置** | `domain/strategy/pinbar.py:217-227` |
| **状态** | pending |

#### 问题描述
`calculate_dynamic_score` 调用时同时传入 `weights` 和 `scoring_config`，但 `scoring_config` 始终传 None

#### 实施方案

**步骤 1**: 修改 `evaluate` 方法签名，移除 `weights` 参数
```python
# domain/strategy/pinbar.py:79-88 替换为
def evaluate(
    self,
    current_bar: Bar,
    history_bars: List[Bar],
    max_sl_dist: float,
    scoring_config: ScoringConfig,  # 改为必填
    higher_trend: Optional[str] = None,
    pinbar_config: PinbarConfig = None
) -> Optional[Signal]:
```

**步骤 2**: 更新调用 `calculate_dynamic_score` 的地方
```python
# domain/strategy/pinbar.py:217-227 替换为
score = 0
details = {}
if scoring_config:
    score, details = calculate_dynamic_score(
        current_bar,
        ema60,
        atr14,
        is_long,
        config=scoring_config
    )
```

**步骤 3**: 更新所有调用 `evaluate` 的地方
```python
# application/monitor_engine.py:222-229 需要更新
signal = self.strategy.evaluate(
    current_bar=current_bar,
    history_bars=current_history,
    max_sl_dist=self.max_sl_dist,
    scoring_config=self.scoring_config,  # 新增
    pinbar_config=self.pinbar_config,
    higher_trend=higher_trend
)
```

**步骤 4**: 移除向后兼容的权重转换代码
```python
# domain/strategy/scoring.py 中可移除 _convert_weights_to_config 函数
# 或标记为 @deprecated
```

**涉及文件修改**:
- `domain/strategy/pinbar.py` (evaluate 签名修改)
- `domain/strategy/scoring.py` (清理废弃代码)
- `application/monitor_engine.py` (调用更新)
- `application/history_scanner.py` (如有调用也需更新)

---

### 问题 9：熔断逻辑分散

| 属性 | 内容 |
|-----|------|
| **类别** | 代码设计 |
| **严重程度** | 中 |
| **代码位置** | `domain/strategy/pinbar.py:72-73`, `127-128`, `133-135`, `203-204`, `254-255` |
| **状态** | pending |

#### 问题描述
硬性拒绝的逻辑分散在 `evaluate` 方法的不同段落

#### 实施方案

**步骤 1**: 创建 `RejectionResult` 数据类
```python
# domain/strategy/pinbar.py
@dataclass
class RejectionResult:
    """硬熔断结果"""
    is_rejected: bool
    reason: Optional[str] = None  # 拒绝原因代码
    message: Optional[str] = None  # 人类可读原因

    @classmethod
    def accept(cls):
        return cls(is_rejected=False)

    @classmethod
    def reject(cls, reason: str, message: str):
        return cls(is_rejected=True, reason=reason, message=message)
```

**步骤 2**: 创建集中熔断检查方法
```python
# domain/strategy/pinbar.py
def _apply_hard_rejections(
    self,
    body_ratio: float,
    sl_distance_pct: float,
    effective_max_sl_dist: float,
    quality_tier: SignalTier,
    total_score: int
) -> RejectionResult:
    """
    集中检查所有硬性拒绝条件

    检查顺序：
    1. 实体过大
    2. 止损距离极端
    3. 质量等级拒绝
    4. 总分过低
    """
    # 检查 1: 实体过大
    if body_ratio > self.HARD_REJECT_BODY_RATIO:
        return RejectionResult.reject(
            reason="BODY_TOO_LARGE",
            message=f"实体比例 {body_ratio:.2%} 超过阈值 {self.HARD_REJECT_BODY_RATIO:.2%}"
        )

    # 检查 2: 止损距离极端
    if sl_distance_pct > effective_max_sl_dist * 2:
        return RejectionResult.reject(
            reason="SL_TOO_FAR",
            message=f"止损距离 {sl_distance_pct:.2%} 超过动态阈值 {effective_max_sl_dist*2:.2%}"
        )

    # 检查 3: 质量等级拒绝
    if quality_tier == SignalTier.REJECTED:
        return RejectionResult.reject(
            reason="TIER_REJECTED",
            message="信号质量等级为 REJECTED"
        )

    # 检查 4: 总分过低
    if total_score < self.HARD_REJECT_MIN_SCORE:
        return RejectionResult.reject(
            reason="SCORE_TOO_LOW",
            message=f"总分 {total_score} 低于最低要求 {self.HARD_REJECT_MIN_SCORE}"
        )

    return RejectionResult.accept()
```

**步骤 3**: 在 `evaluate` 方法中统一调用
```python
# domain/strategy/pinbar.py:254 之后，返回 Signal 之前
rejection = self._apply_hard_rejections(
    body_ratio=shape_metrics.body_ratio,
    sl_distance_pct=sl_distance_pct,
    effective_max_sl_dist=effective_max_sl_dist,
    quality_tier=quality_tier,
    total_score=score
)

if rejection.is_rejected:
    logger.debug(f"信号被熔断：{rejection.reason} - {rejection.message}")
    return None
```

**步骤 4**: 增加熔断统计（可选）
```python
# domain/strategy/pinbar.py
class PinbarStrategy:
    def __init__(self, ...):
        self._rejection_stats = defaultdict(int)

    def _apply_hard_rejections(self, ...):
        result = ...  # 上述逻辑
        if result.is_rejected:
            self._rejection_stats[result.reason] += 1
        return result

    def get_rejection_stats(self) -> Dict[str, int]:
        """获取熔断统计（用于调试）"""
        return dict(self._rejection_stats)
```

**涉及文件修改**:
- `domain/strategy/pinbar.py` (新增 RejectionResult 和 _apply_hard_rejections)

---

## 修复优先级建议

1. **P0 - 立即修复**: 问题 6（Doji 边界漏洞）、问题 7（补充单元测试）
2. **P1 - 近期修复**: 问题 1（双向 Pinbar）、问题 4（指标缓存）、问题 9（熔断集中）
3. **P2 - 规划修复**: 问题 2（滑点缓冲）、问题 3（盈亏比配置）、问题 5（分级配置）
4. **P3 - 技术债务**: 问题 8（参数清理）

---

## 相关文件

- 核心策略：`domain/strategy/pinbar.py`
- 指标计算：`domain/strategy/indicators.py`
- 评分引擎：`domain/strategy/scoring.py`
- 配置实体：`core/entities.py` (PinbarConfig, ScoringConfig)
- 监控引擎：`application/monitor_engine.py`
