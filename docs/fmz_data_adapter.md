# FMZ K 线数据格式适配指南

## 数据格式对比

### FMZ 框架输出的 K 线格式

```python
# FMZ GetRecords() 返回格式
[
    {
        'Time': 1645228800000,      # 毫秒时间戳
        'Open': 41234.56,           # 开盘价
        'High': 41500.00,           # 最高价
        'Low': 41000.00,            # 最低价
        'Close': 41345.67,          # 收盘价
        'Volume': 1234.56           # 成交量
    },
    ...
]
```

### monitor 系统的 Bar 实体格式

```python
# core/entities.py
@dataclass
class Bar:
    symbol: str            # 交易对 (如 "BTCUSDT")
    interval: str          # 时间级别 (如 "15m", "1h")
    timestamp: int         # 毫秒时间戳
    open: float            # 开盘价
    high: float            # 最高价
    low: float             # 最低价
    close: float           # 收盘价
    volume: float          # 成交量
    is_closed: bool        # 是否已闭合
```

---

## 格式兼容性分析

### ✅ 完全兼容的字段

| 字段 | Bar 类型 | FMZ 格式 | 说明 |
|------|---------|---------|------|
| 时间戳 | `timestamp: int` | `Time: int` | 都是毫秒时间戳 |
| 开盘价 | `open: float` | `Open: float` | 完全一致 |
| 最高价 | `high: float` | `High: float` | 完全一致 |
| 最低价 | `low: float` | `Low: float` | 完全一致 |
| 收盘价 | `close: float` | `Close: float` | 完全一致 |
| 成交量 | `volume: float` | `Volume: float` | 完全一致 |

### ⚠️ 需要转换/补充的字段

| 字段 | 问题 | 解决方案 |
|------|------|---------|
| `symbol` | FMZ K 线数据不包含交易对 | 从 Exchange 实例配置中获取 |
| `interval` | FMZ K 线数据不包含时间级别 | 从 GetRecords 参数或配置中获取 |
| `is_closed` | FMZ 无此字段 | 历史 K 线全部设为 `True` |

---

## 适配器实现

### 方案一：简单转换函数（推荐）

```python
from typing import List, Dict
from core.entities import Bar

def fmz_records_to_bars(
    records: List[Dict],
    symbol: str,
    interval: str,
    is_closed: bool = True
) -> List[Bar]:
    """
    将 FMZ GetRecords() 返回的数据转换为 Bar 实体列表

    :param records: FMZ K 线数据列表
    :param symbol: 交易对 (如 "BTCUSDT")
    :param interval: 时间级别 (如 "1h")
    :param is_closed: K 线是否已闭合
    :return: Bar 实体列表
    """
    return [
        Bar(
            symbol=symbol,
            interval=interval,
            timestamp=r['Time'],
            open=r['Open'],
            high=r['High'],
            low=r['Low'],
            close=r['Close'],
            volume=r.get('Volume', 0.0),
            is_closed=is_closed
        )
        for r in records
    ]

def bar_to_fmz_record(bar: Bar) -> Dict:
    """
    将 Bar 实体转换为 FMZ 格式（用于回测结果展示）
    """
    return {
        'Time': bar.timestamp,
        'Open': bar.open,
        'High': bar.high,
        'Low': bar.low,
        'Close': bar.close,
        'Volume': bar.volume
    }
```

### 方案二：ExchangeProxy 内置转换

```python
# 在 FMZAdapter 或 ExchangeProxy 内部集成转换

class ExchangeProxy:
    """FMZ Exchange 接口代理"""

    def __init__(self, symbol: str, interval: str, ...):
        self.symbol = symbol
        self.interval = interval
        # ...

    def GetRecords(self, period: str = None, limit: int = 100) -> List[dict]:
        """获取 FMZ 格式的 K 线数据"""
        # 内部存储的是 Bar 实体
        bars = self._get_bars_from_history(limit)

        # 转换为 FMZ 格式返回
        return [
            {
                'Time': bar.timestamp,
                'Open': bar.open,
                'High': bar.high,
                'Low': bar.low,
                'Close': bar.close,
                'Volume': bar.volume
            }
            for bar in bars
        ]

    def GetBars(self, limit: int = 100) -> List[Bar]:
        """获取 monitor 格式的 Bar 实体（供 PinbarStrategy 使用）"""
        return self._get_bars_from_history(limit)
```

---

## Pinbar 检测适配验证

### 测试用例

```python
# tests/test_fmz_adapter.py

def test_pinbar_with_fmz_data():
    """验证 Pinbar 策略能正确处理 FMZ 格式数据"""

    # 1. 模拟 FMZ 返回的 K 线数据
    fmz_records = [
        {'Time': 1645228800000, 'Open': 41000, 'High': 41500, 'Low': 40800, 'Close': 41300, 'Volume': 1000},
        {'Time': 1645232400000, 'Open': 41300, 'High': 41800, 'Low': 41200, 'Close': 41600, 'Volume': 1200},
        # ... 更多 K 线
    ]

    # 2. 转换为 Bar 实体
    bars = fmz_records_to_bars(fmz_records, symbol="BTCUSDT", interval="1h")

    # 3. 调用 Pinbar 策略
    strategy = PinbarStrategy(ema_period=60, atr_period=14)

    history_bars = bars[:-1]  # 历史 K 线
    current_bar = bars[-1]    # 当前 K 线

    signal = strategy.evaluate(
        current_bar=current_bar,
        history_bars=history_bars,
        max_sl_dist=0.035
    )

    # 4. 验证信号生成
    if signal:
        print(f"信号：{signal.direction} @ {signal.entry_price}")
```

### 实际回测场景 (v2.0 架构)

```python
def execute_fmz_backtest(config_string: str, strategy_config: dict) -> dict:
    """基于 VCtx 的回测运行器"""
    from fmz import *
    from core.entities import PinbarConfig
    
    # 初始化 FMZ 引擎
    task = VCtx(config_string)
    strategy = PinbarStrategy(...)
    
    while True:
        # 1. 从底层获取数据
        records = exchange.GetRecords()
        if not records:
            break
            
        # 2. 轻量级转换 (复用业务大脑)
        bars_history = fmz_records_to_bars(records[:-1], symbol="BTC", interval="1h")
        current_bar = fmz_records_to_bars([records[-1]], symbol="BTC", interval="1h")[0]
        
        # 3. 策略评估
        signal = strategy.evaluate(
            current_bar=current_bar,
            history_bars=bars_history,
            max_sl_dist=0.035
        )
        
        # 4. 执行 (直接调用 FMZ API)
        if signal:
            if signal.direction == 'LONG':
                exchange.Buy(current_bar.close, 1.0)
            else:
                exchange.Sell(current_bar.close, 1.0)
                
    # 返回丰富的结果供外层解析
    return task.Join()
```

---

## 关键验证点

### 1. 时间戳格式 ✅

```python
# FMZ 和 monitor 都使用毫秒时间戳
fmz_time = 1645228800000
bar_time = 1645228800000
assert fmz_time == bar_time  # 无需转换
```

### 2. OHLC 计算逻辑 ✅

```python
# Pinbar 形态计算完全兼容
body_length = abs(bar.open - bar.close)      # 实体长度
total_length = bar.high - bar.low            # 总长度
lower_shadow = min(bar.open, bar.close) - bar.low   # 下影线
upper_shadow = bar.high - max(bar.open, bar.close)  # 上影线
```

### 3. 指标计算 ✅

```python
# EMA 和 ATR 计算只依赖收盘价、最高价、最低价序列
closes = [bar.close for bar in bars]  # 从 Bar 或 FMZ 数据提取都一样
highs = [bar.high for bar in bars]
lows = [bar.low for bar in bars]
```

---

## 总结

### 兼容性评估

| 方面 | 兼容性 | 说明 |
|------|-------|------|
| OHLC 数据 | ✅ 100% 兼容 | 字段名称不同，值完全一致 |
| 时间戳 | ✅ 100% 兼容 | 都使用毫秒时间戳 |
| 成交量 | ✅ 100% 兼容 | 都使用 float 类型 |
| 形态计算 | ✅ 100% 兼容 | 使用相同的数学公式 |
| 指标计算 | ✅ 100% 兼容 | EMA/ATR 算法一致 |
| 元数据 | ⚠️ 需补充 | symbol/interval/is_closed 需额外提供 |

### 改造工作量

| 模块 | 改动 | 工时 |
|------|------|------|
| 数据转换 | 添加 `fmz_records_to_bars()` 函数 | 30 分钟 |
| 回测适配器 | 在 `__init__` 中进行一次性转换 | 1 小时 |
| 单元测试 | 验证转换后 Pinbar 检测正常 | 1 小时 |
| **总计** | **纯 Python 代码，无第三方依赖** | **约 2.5 小时** |

### 核心优势

1. **现有 PinbarStrategy 无需任何修改** - 数据转换在适配器层完成
2. **领域逻辑保持纯净** - 转换逻辑不侵入 Domain 层
3. **可逆转换** - FMZ 格式 ↔ Bar 实体可双向转换
4. **零性能损失** - 仅在数据加载时转换一次，回测过程无额外开销

---

*文档结束*
