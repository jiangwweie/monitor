# 动态可配置打分机制 - 技术设计文档

**版本**: v1.0
**日期**: 2026-03-03
**状态**: 待开发

---

## 1. 系统架构

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端配置界面 (Web UI)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ ModeSelector│  │ Parameter   │  │ ScoreDistributionChart  │ │
│  │             │  │ Sliders     │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↕ HTTP (JSON)
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI 应用层 (web/api.py)                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ /api/config/scoring (GET)  - 获取打分配置                  │ │
│  │ /api/config/scoring (PUT)  - 更新打分配置                  │ │
│  │ /api/config/scoring/preview (POST) - 分数预览             │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              ↕                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Pydantic Models (请求/响应验证)                            │ │
│  │   - ScoringConfigReq                                      │ │
│  │   - ScoringConfigResponse                                 │ │
│  │   - ScorePreviewRequest                                   │ │
│  │   - ScorePreviewResponse                                  │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                    领域层 (domain/strategy/)                     │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ ScoringConfig (实体) - 配置数据的载体                       │ │
│  │   - mode: str                                             │ │
│  │   - classic_*: 经典模式参数                                │ │
│  │   - progressive_*: 累进模式参数                            │ │
│  │   - w_shape/w_trend/w_vol: 权重                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              ↕                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ IScoreStrategy (接口)                                     │ │
│  │   abstract def calculate(...) -> Tuple[int, Dict]         │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              ↕ 实现                             │
│  ┌───────────────┐ ┌─────────────────┐ ┌───────────────────┐  │
│  │ClassicStrategy│ │ProgressiveStra..│ │ CustomStrategy    │  │
│  │               │ │                 │ │                   │  │
│  │经典线性评分    │ │累进加分评分      │ │自定义公式评分      │  │
│  └───────────────┘ └─────────────────┘ └───────────────────┘  │
│                              ↕                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ ScoringStrategyFactory (工厂)                             │ │
│  │   def get_strategy(mode: str) -> IScoreStrategy           │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↕ 调用
┌─────────────────────────────────────────────────────────────────┐
│                  PinbarStrategy.evaluate()                      │
│  - 从 engine.scoring_config 读取配置                             │
│  - 通过工厂获取对应策略                                          │
│  - 调用 strategy.calculate(...)                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                    基础设施层 (infrastructure/)                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ SQLiteRepository                                           │ │
│  │   - get_secret("scoring_config") → JSON                   │ │
│  │   - set_secret("scoring_config", JSON)                    │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 模块依赖关系

```
domain/strategy/
├── __init__.py          # 导出所有公开类和函数
├── scoring_config.py    # ScoringConfig 实体定义
├── scoring_strategy.py  # IScoreStrategy 接口和实现策略
└── scoring_factory.py   # ScoringStrategyFactory 工厂类

core/entities.py
└── (现有文件，无需修改)

web/api.py
└── 新增打分配置相关接口

infrastructure/repo/sqlite_repo.py
└── (现有方法，直接复用)
```

---

## 2. 核心模块设计

### 2.1 ScoringConfig 实体

**文件**: `domain/strategy/scoring_config.py`

```python
"""
打分配置实体模块
"""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ScoringConfig:
    """
    打分配置实体 - 支持多模式

    所有参数可通过 /api/config/scoring 接口热配置
    """

    # ================================
    # 模式选择
    # ================================
    mode: Literal["classic", "progressive", "custom"] = "classic"

    # ================================
    # 经典模式参数
    # ================================
    # 影线比例：0.6→0 分，0.9→100 分
    classic_shadow_min: float = 0.6
    classic_shadow_max: float = 0.9

    # 实体比例：0.1→100 分，0.5→0 分
    classic_body_good: float = 0.1
    classic_body_bad: float = 0.5

    # 波动率：1.2x→0 分，3.0x→100 分
    classic_vol_min: float = 1.2
    classic_vol_max: float = 3.0

    # 趋势距离：0%→100 分，3%→0 分
    classic_trend_max_dist: float = 0.03

    # ================================
    # 累进模式参数
    # ================================
    # 基础分上限（每个维度）
    progressive_base_cap: float = 30.0

    # 影线奖励：超过 0.6 后每 +0.1 奖励 2 分
    progressive_shadow_threshold: float = 0.6
    progressive_shadow_bonus_rate: float = 20.0

    # 实体奖励：<10% 时每 -0.01 奖励 1 分
    progressive_body_bonus_threshold: float = 0.1
    progressive_body_bonus_rate: float = 100.0

    # 十字星固定奖励
    progressive_doji_bonus: float = 5.0

    # 影线/实体比奖励：超过 3 倍后每 +1 奖励 2 分
    progressive_shadow_body_ratio_threshold: float = 3.0
    progressive_shadow_body_ratio_bonus: float = 2.0

    # 波动率奖励：超过 2x 后每 +0.1 奖励 1.5 分
    progressive_vol_threshold: float = 2.0
    progressive_vol_bonus_rate: float = 15.0

    # 极端波动奖励：超过 3x 额外奖励
    progressive_extreme_vol_threshold: float = 3.0
    progressive_extreme_vol_bonus: float = 10.0

    # 趋势穿透奖励
    progressive_penetration_rate: float = 30.0

    # ================================
    # 权重配置 (所有模式通用)
    # ================================
    w_shape: float = 0.4
    w_trend: float = 0.3
    w_vol: float = 0.3

    def __post_init__(self):
        """验证权重和"""
        total = round(self.w_shape + self.w_trend + self.w_vol, 4)
        if abs(total - 1.0) > 0.0001:
            raise ValueError(f"权重总和必须等于 1.0，当前为：{total}")
```

---

### 2.2 IScoreStrategy 接口

**文件**: `domain/strategy/scoring_strategy.py`

```python
"""
打分策略接口定义
"""
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Optional
from core.entities import Bar


class IScoreStrategy(ABC):
    """打分策略接口"""

    @abstractmethod
    def calculate(
        self,
        current_bar: Bar,
        ema60: float,
        atr14: float,
        is_long: bool,
        config: 'ScoringConfig'
    ) -> Tuple[int, Dict[str, float]]:
        """
        计算得分

        :param current_bar: 当前 K 线
        :param ema60: EMA60 值
        :param atr14: ATR14 值
        :param is_long: 是否为做多方向
        :param config: 打分配置
        :return: (总分 0-100, {shape: xx, trend: xx, vol: xx})
        """
        pass


class ClassicScoreStrategy(IScoreStrategy):
    """
    经典线性打分策略

    保持现有 calculate_dynamic_score 函数的逻辑
    """

    def calculate(
        self,
        current_bar: Bar,
        ema60: float,
        atr14: float,
        is_long: bool,
        config: 'ScoringConfig'
    ) -> Tuple[int, Dict[str, float]]:
        """
        经典模式打分实现

        评分逻辑:
        1. 形态分：影线/总长比 (0.6→0, 0.9→100) + 实体/总长比 (0.1→100, 0.5→0)
        2. 趋势分：距离 EMA60 越近分越高 (0%→100, 3%→0)
        3. 波动分：K 线长度/ATR (1.2x→0, 3.0x→100)
        """
        body_length = abs(current_bar.open - current_bar.close)
        total_length = current_bar.high - current_bar.low

        if total_length == 0:
            return 0, {"shape": 0.0, "trend": 0.0, "vol": 0.0}

        # 有效影线长度
        if is_long:
            shadow_length = min(current_bar.open, current_bar.close) - current_bar.low
        else:
            shadow_length = current_bar.high - max(current_bar.open, current_bar.close)

        # === 1. 形态评分 ===
        shadow_ratio = shadow_length / total_length
        body_ratio = body_length / total_length

        # 影线/总长比 (config.classic_shadow_min→0, config.classic_shadow_max→100)
        s_shadow = min(100.0, max(0.0,
            (shadow_ratio - config.classic_shadow_min) /
            (config.classic_shadow_max - config.classic_shadow_min) * 100.0
        ))

        # 实体/总长比 (config.classic_body_good→100, config.classic_body_bad→0)
        s_body = min(100.0, max(0.0,
            (config.classic_body_bad - body_ratio) /
            (config.classic_body_bad - config.classic_body_good) * 100.0
        ))

        # 影线/实体比
        if body_length > 0:
            shadow_to_body = shadow_length / body_length
            s_ratio = min(100.0, max(0.0, (shadow_to_body - 1.5) / 2.5 * 100.0))
        else:
            s_ratio = 100.0

        shape_score = s_shadow * 0.4 + s_body * 0.3 + s_ratio * 0.3

        # === 2. 趋势评分 ===
        dist_to_ema = abs(current_bar.close - ema60) / ema60 if ema60 > 0 else 0
        s_trend = min(100.0, max(0.0,
            (config.classic_trend_max_dist - dist_to_ema) /
            config.classic_trend_max_dist * 100.0
        ))

        # === 3. 波动评分 ===
        vol_ratio = total_length / atr14 if atr14 > 0 else config.classic_vol_min
        s_vol = min(100.0, max(0.0,
            (vol_ratio - config.classic_vol_min) /
            (config.classic_vol_max - config.classic_vol_min) * 100.0
        ))

        # === 4. 加权总分 ===
        score_float = (
            shape_score * config.w_shape +
            s_trend * config.w_trend +
            s_vol * config.w_vol
        )

        score = int(round(min(100, max(0, score_float))))

        details = {
            "shape": round(shape_score, 2),
            "trend": round(s_trend, 2),
            "vol": round(s_vol, 2)
        }

        return score, details


class ProgressiveScoreStrategy(IScoreStrategy):
    """
    累进加分策略

    评分逻辑:
    1. 基础分 (0-30): 满足基本条件即可获得
    2. 奖励分 (0-40): 根据优秀程度额外奖励，上不封顶（但最终会被权重压缩）
    """

    def calculate(
        self,
        current_bar: Bar,
        ema60: float,
        atr14: float,
        is_long: bool,
        config: 'ScoringConfig'
    ) -> Tuple[int, Dict[str, float]]:
        """累进模式打分实现"""
        body_length = abs(current_bar.open - current_bar.close)
        total_length = current_bar.high - current_bar.low

        if total_length == 0:
            return 0, {"shape": 0.0, "trend": 0.0, "vol": 0.0}

        # 有效影线长度
        if is_long:
            shadow_length = min(current_bar.open, current_bar.close) - current_bar.low
        else:
            shadow_length = current_bar.high - max(current_bar.open, current_bar.close)

        body_ratio = body_length / total_length
        shadow_to_total = shadow_length / total_length

        # ================================
        # 1. 形态评分 (基础分 + 奖励分)
        # ================================

        # --- 基础分 (0-30) ---
        base_shape = 0.0

        # 实体占比 < config.classic_body_good 得满分
        if body_ratio < config.classic_body_good:
            base_shape += config.progressive_base_cap * 0.6
        else:
            base_shape += max(0, config.progressive_base_cap * 0.6 *
                (config.classic_body_bad - body_ratio) /
                (config.classic_body_bad - config.classic_body_good))

        # 影线占比 > config.progressive_shadow_threshold 得高分
        if shadow_to_total > config.progressive_shadow_threshold:
            base_shape += config.progressive_base_cap * 0.4
        else:
            base_shape += max(0, config.progressive_base_cap * 0.4 *
                shadow_to_total / config.progressive_shadow_threshold)

        base_shape = min(config.progressive_base_cap, base_shape)

        # --- 奖励分 (0-40) ---
        bonus_shape = 0.0

        # 影线长度奖励
        if shadow_to_total > config.progressive_shadow_threshold:
            bonus_shape += (shadow_to_total - config.progressive_shadow_threshold) * \
                config.progressive_shadow_bonus_rate

        # 实体极小奖励
        if body_ratio < config.progressive_body_bonus_threshold:
            bonus_shape += (config.progressive_body_bonus_threshold - body_ratio) * \
                config.progressive_body_bonus_rate

        # 十字星特别奖励
        if body_ratio < 0.05:
            bonus_shape += config.progressive_doji_bonus

        # 影线/实体比奖励
        if body_length > 0:
            shadow_to_body = shadow_length / body_length
            if shadow_to_body > config.progressive_shadow_body_ratio_threshold:
                bonus_shape += (shadow_to_body - config.progressive_shadow_body_ratio_threshold) * \
                    config.progressive_shadow_body_ratio_bonus

        shape_score = base_shape + min(40, bonus_shape)
        shape_score = min(100, shape_score)

        # ================================
        # 2. 趋势评分 (基础分 + 穿透奖励)
        # ================================

        dist_to_ema = abs(current_bar.close - ema60) / ema60 if ema60 > 0 else 0

        # --- 基础分 (0-30) ---
        base_trend = max(0, config.progressive_base_cap *
            (config.classic_trend_max_dist - dist_to_ema) /
            config.classic_trend_max_dist)
        base_trend = min(config.progressive_base_cap, base_trend)

        # --- 穿透奖励 (0-20) ---
        bonus_trend = 0.0

        if is_long:
            penetration = ema60 - current_bar.low
        else:
            penetration = current_bar.high - ema60

        if penetration > 0:
            penetration_ratio = penetration / total_length
            bonus_trend += penetration_ratio * config.progressive_penetration_rate
            bonus_trend = min(20, bonus_trend)

        trend_score = base_trend + bonus_trend
        trend_score = min(100, trend_score)

        # ================================
        # 3. 波动评分 (基础分 + 爆发奖励)
        # ================================

        vol_ratio = total_length / atr14 if atr14 > 0 else 0

        # --- 基础分 (0-30) ---
        base_vol = min(config.progressive_base_cap, max(0,
            config.progressive_base_cap *
            (vol_ratio - config.classic_vol_min) /
            (config.classic_vol_max - config.classic_vol_min)
        ))

        # --- 奖励分 (0-30) ---
        bonus_vol = 0.0

        if vol_ratio > config.progressive_vol_threshold:
            bonus_vol += (vol_ratio - config.progressive_vol_threshold) * \
                config.progressive_vol_bonus_rate

        if vol_ratio > config.progressive_extreme_vol_threshold:
            bonus_vol += config.progressive_extreme_vol_bonus

        # 低于阈值的惩罚
        if vol_ratio < config.classic_vol_min:
            base_vol *= 0.3

        vol_score = base_vol + min(30, bonus_vol)
        vol_score = min(100, vol_score)

        # ================================
        # 4. 加权总分
        # ================================
        score_float = (
            shape_score * config.w_shape +
            trend_score * config.w_trend +
            vol_score * config.w_vol
        )

        score = int(round(min(100, max(0, score_float))))

        details = {
            "shape": round(shape_score, 2),
            "trend": round(trend_score, 2),
            "vol": round(vol_score, 2)
        }

        return score, details


class CustomScoreStrategy(IScoreStrategy):
    """
    自定义公式策略（预留扩展点）

    当前版本暂时复用经典模式逻辑，未来可扩展为：
    - 用户自定义公式字符串解析执行
    - 机器学习模型打分
    """

    def calculate(
        self,
        current_bar: Bar,
        ema60: float,
        atr14: float,
        is_long: bool,
        config: 'ScoringConfig'
    ) -> Tuple[int, Dict[str, float]]:
        # 暂时复用经典模式
        return ClassicScoreStrategy().calculate(
            current_bar, ema60, atr14, is_long, config
        )
```

---

### 2.3 ScoringStrategyFactory 工厂类

**文件**: `domain/strategy/scoring_factory.py`

```python
"""
打分策略工厂
"""
from typing import Dict, Type
from .scoring_strategy import IScoreStrategy, ClassicScoreStrategy, \
    ProgressiveScoreStrategy, CustomScoreStrategy


class ScoringStrategyFactory:
    """打分策略工厂类"""

    _strategies: Dict[str, Type[IScoreStrategy]] = {
        "classic": ClassicScoreStrategy,
        "progressive": ProgressiveScoreStrategy,
        "custom": CustomScoreStrategy,
    }

    @classmethod
    def get_strategy(cls, mode: str) -> IScoreStrategy:
        """
        根据模式获取对应的打分策略实例

        :param mode: 打分模式 ("classic" | "progressive" | "custom")
        :return: 策略实例
        :raises: ValueError 当模式不存在时
        """
        strategy_class = cls._strategies.get(mode.lower())
        if not strategy_class:
            available_modes = list(cls._strategies.keys())
            raise ValueError(
                f"未知的打分模式：{mode}，可用模式：{available_modes}"
            )
        return strategy_class()

    @classmethod
    def register_strategy(cls, mode: str, strategy_class: Type[IScoreStrategy]):
        """
        注册新的打分策略（供未来扩展）

        :param mode: 模式名称
        :param strategy_class: 策略类
        """
        cls._strategies[mode.lower()] = strategy_class
```

---

## 3. 数据结构定义

### 3.1 类图

```
┌────────────────────────────────┐
│      ScoringConfig             │
├────────────────────────────────┤
│ + mode: str                    │
│ + classic_shadow_min: float    │
│ + classic_shadow_max: float    │
│ + progressive_base_cap: float  │
│ + progressive_shadow_threshold:│
│ ... (20+ 配置项)                │
│ + w_shape: float               │
│ + w_trend: float               │
│ + w_vol: float                 │
├────────────────────────────────┤
│ + __post_init__(): void        │
└────────────────────────────────┘
              ↕ 被使用
┌────────────────────────────────┐
│     IScoreStrategy             │
├────────────────────────────────┤
│ + calculate(...): Tuple[int,   │
│   Dict[str, float]]            │
└────────────────────────────────┘
              △ 实现
    ┌─────────┼─────────┬─────────┐
    │         │         │         │
┌───┴───┐ ┌───┴────┐ ┌──┴─────┐
│Classic│ │Progr.. │ │Custom  │
│Strategy│ │Strategy│ │Strategy│
└───────┘ └────────┘ └────────┘
```

### 3.2 配置 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "mode": {
      "type": "string",
      "enum": ["classic", "progressive", "custom"],
      "default": "classic"
    },
    "classic_shadow_min": {"type": "number", "minimum": 0.3, "maximum": 0.8},
    "classic_shadow_max": {"type": "number", "minimum": 0.7, "maximum": 1.0},
    "progressive_base_cap": {"type": "number", "minimum": 20, "maximum": 50},
    "progressive_shadow_threshold": {"type": "number", "minimum": 0.4, "maximum": 0.8},
    "w_shape": {"type": "number", "minimum": 0, "maximum": 1},
    "w_trend": {"type": "number", "minimum": 0, "maximum": 1},
    "w_vol": {"type": "number", "minimum": 0, "maximum": 1}
  },
  "required": ["mode", "w_shape", "w_trend", "w_vol"]
}
```

---

## 4. 打分算法详细公式

### 4.1 经典模式公式

```python
# 形态评分
shadow_score = (shadow_ratio - shadow_min) / (shadow_max - shadow_min) * 100
body_score = (body_bad - body_ratio) / (body_bad - body_good) * 100
ratio_score = (shadow_to_body - 1.5) / 2.5 * 100
shape_score = shadow_score * 0.4 + body_score * 0.3 + ratio_score * 0.3

# 趋势评分
trend_score = (trend_max_dist - dist_to_ema) / trend_max_dist * 100

# 波动评分
vol_score = (vol_ratio - vol_min) / (vol_max - vol_min) * 100

# 总分
total = shape_score * w_shape + trend_score * w_trend + vol_score * w_vol
```

### 4.2 累进模式公式

```python
# 形态评分
base_shape = min(30, 实体分 * 0.6 + 影线分 * 0.4)
bonus_shape = (shadow_ratio - 0.6) * 200 +
              (0.1 - body_ratio) * 100 +
              (body_ratio < 0.05 ? 5 : 0) +
              (shadow_to_body - 3) * 2
shape_score = base_shape + min(40, bonus_shape)

# 趋势评分
base_trend = min(30, (trend_max_dist - dist_to_ema) / trend_max_dist * 30)
bonus_trend = min(20, penetration_ratio * 30)
trend_score = base_trend + bonus_trend

# 波动评分
base_vol = min(30, (vol_ratio - vol_min) / (vol_max - vol_min) * 30)
bonus_vol = (vol_ratio - 2.0) * 15 + (vol_ratio > 3.0 ? 10 : 0)
vol_score = base_vol + min(30, bonus_vol)

# 总分
total = shape_score * w_shape + trend_score * w_trend + vol_score * w_vol
```

---

## 5. 配置热加载机制

### 5.1 启动流程

```
应用启动
    ↓
从 SQLite 加载配置
    ↓
解析 JSON → ScoringConfig
    ↓
绑定到 engine.scoring_config
    ↓
PinbarStrategy 从 engine 读取配置
    ↓
正常处理信号
```

### 5.2 配置更新流程

```
用户修改配置 (前端)
    ↓
PUT /api/config/scoring
    ↓
Pydantic 验证参数
    ↓
保存到 SQLite
    ↓
更新 engine.scoring_config
    ↓
新信号使用新配置计算
```

### 5.3 异常处理

```python
try:
    config = ScoringConfig(**json_data)
except ValidationError as e:
    logger.error(f"配置验证失败：{e}")
    # 使用上一次有效配置或默认配置
    config = get_last_valid_config() or ScoringConfig()
except Exception as e:
    logger.error(f"配置加载失败：{e}")
    # 使用默认配置
    config = ScoringConfig()
```

---

## 6. 数据库设计

### 6.1 SQLite Schema

复用现有的 `secrets` 表：

```sql
CREATE TABLE IF NOT EXISTS secrets (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 打分配置存储
INSERT OR REPLACE INTO secrets (key, value)
VALUES ('scoring_config', '{"mode": "progressive", "w_shape": 0.4, ...}');
```

### 6.2 配置键命名

| 配置项 | 键名 | 说明 |
|--------|------|------|
| 打分配置 | `scoring_config` | JSON 字符串 |
| 活动币种 | `active_symbols` | 已有 |
| 监控周期 | `monitor_intervals` | 已有 |
| Pinbar 参数 | `pinbar_config` | 已有 |

---

## 7. 测试策略

### 7.1 单元测试

```python
# test_scoring_strategy.py

def test_classic_score_shadow_ratio():
    """测试经典模式影线比例边界"""
    config = ScoringConfig(mode="classic")
    strategy = ClassicScoreStrategy()

    # 构造测试 K 线
    bar = create_bar(open=100, close=101, high=103, low=99)

    score, details = strategy.calculate(bar, ema60=100, atr14=2, is_long=True, config=config)

    # 影线比例 = 2/4 = 0.5，低于 0.6，应该低分
    assert details["shape"] < 50

def test_progressive_score_bonus():
    """测试累进模式奖励分"""
    config = ScoringConfig(mode="progressive")
    strategy = ProgressiveScoreStrategy()

    # 构造完美 Pinbar
    bar = create_bar(open=100, close=100.5, high=103, low=99)

    score, details = strategy.calculate(bar, ema60=100, atr14=2, is_long=True, config=config)

    # 应该获得高分
    assert score >= 80
    assert details["shape"] > 70

def test_weight_validation():
    """测试权重验证"""
    with pytest.raises(ValueError):
        ScoringConfig(w_shape=0.5, w_trend=0.3, w_vol=0.3)  # 总和!=1.0
```

### 7.2 集成测试

```python
# test_api_integration.py

async def test_update_scoring_config():
    """测试配置更新接口"""
    async with httpx.AsyncClient() as client:
        response = await client.put(
            "http://localhost:8000/api/config/scoring",
            json={
                "mode": "progressive",
                "w_shape": 0.4,
                "w_trend": 0.3,
                "w_vol": 0.3
            }
        )
        assert response.status_code == 200

async def test_invalid_weights():
    """测试非法权重拒绝"""
    async with httpx.AsyncClient() as client:
        response = await client.put(
            "http://localhost:8000/api/config/scoring",
            json={
                "mode": "classic",
                "w_shape": 0.5,
                "w_trend": 0.3,
                "w_vol": 0.3  # 总和 1.1
            }
        )
        assert response.status_code == 422
```

---

## 8. 性能考虑

### 8.1 基准测试目标

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 配置接口 P99 延迟 | < 100ms | Apache Bench |
| 打分计算开销 | < 1ms | timeit 模块 |
| 配置加载时间 | < 50ms | 启动日志 |

### 8.2 优化措施

1. **策略缓存**: 工厂类内部可缓存策略实例
2. **配置预编译**: ScoringConfig 验证后缓存计算所需的中间值
3. **避免重复计算**: 在 `evaluate()` 主函数中传递已计算的中间结果

---

## 9. 附录

### 9.1 参考文档

- [产品需求文档](./scoring_config_prd.md)
- [API 接口文档](./api/scoring_config_api.md) (待编写)
- [实体定义](../core/entities.py)

### 9.2 修订历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2026-03-03 | Claude | 初始版本 |
