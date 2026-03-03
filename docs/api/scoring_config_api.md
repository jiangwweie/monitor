# 打分配置 API 接口文档

**版本**: v1.0
**日期**: 2026-03-03
**状态**: 待开发

---

## 1. 接口概述

本节定义动态可配置打分机制的所有 RESTful API 接口。

### 1.1 基础信息

| 项目 | 说明 |
|------|------|
| Base URL | `http://localhost:8000` |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |
| 认证方式 | 无（内网部署） |

### 1.2 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/config/scoring` | GET | 获取打分配置 |
| `/api/config/scoring` | PUT | 更新打分配置 |
| `/api/config/scoring/preview` | POST | 分数预览 |

---

## 2. 获取打分配置

### 2.1 接口定义

```http
GET /api/config/scoring
```

### 2.2 请求参数

无

### 2.3 响应格式

**成功响应 (200 OK):**

```json
{
  "mode": "progressive",
  "classic_shadow_min": 0.6,
  "classic_shadow_max": 0.9,
  "classic_body_good": 0.1,
  "classic_body_bad": 0.5,
  "classic_vol_min": 1.2,
  "classic_vol_max": 3.0,
  "classic_trend_max_dist": 0.03,
  "progressive_base_cap": 30.0,
  "progressive_shadow_threshold": 0.6,
  "progressive_shadow_bonus_rate": 20.0,
  "progressive_body_bonus_threshold": 0.1,
  "progressive_body_bonus_rate": 100.0,
  "progressive_doji_bonus": 5.0,
  "progressive_vol_threshold": 2.0,
  "progressive_vol_bonus_rate": 15.0,
  "progressive_extreme_vol_threshold": 3.0,
  "progressive_extreme_vol_bonus": 10.0,
  "progressive_penetration_rate": 30.0,
  "w_shape": 0.4,
  "w_trend": 0.3,
  "w_vol": 0.3
}
```

**字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | string | 打分模式："classic" \| "progressive" \| "custom" |
| `classic_*` | float | 经典模式参数 |
| `progressive_*` | float | 累进模式参数 |
| `w_shape` | float | 形态评分权重 (0-1) |
| `w_trend` | float | 趋势评分权重 (0-1) |
| `w_vol` | float | 波动评分权重 (0-1) |

---

## 3. 更新打分配置

### 3.1 接口定义

```http
PUT /api/config/scoring
Content-Type: application/json
```

### 3.2 请求参数

**Request Body:**

```json
{
  "mode": "progressive",
  "classic_shadow_min": 0.65,
  "classic_shadow_max": 0.85,
  "progressive_base_cap": 35.0,
  "progressive_shadow_threshold": 0.65,
  "progressive_shadow_bonus_rate": 25.0,
  "w_shape": 0.45,
  "w_trend": 0.30,
  "w_vol": 0.25
}
```

**字段说明:**

所有字段均为可选 (optional)，未传入的字段保持原值。

| 字段 | 类型 | 必填 | 默认值 | 可调范围 | 说明 |
|------|------|------|--------|----------|------|
| `mode` | string | 否 | "classic" | classic/progressive/custom | 打分模式 |
| `classic_shadow_min` | float | 否 | 0.6 | 0.3 - 0.8 | 影线比例最小值 |
| `classic_shadow_max` | float | 否 | 0.9 | 0.7 - 1.0 | 影线比例最大值 |
| `classic_body_good` | float | 否 | 0.1 | 0.01 - 0.3 | 实体比例优秀阈值 |
| `classic_body_bad` | float | 否 | 0.5 | 0.3 - 0.7 | 实体比例差阈值 |
| `classic_vol_min` | float | 否 | 1.2 | 0.8 - 2.0 | 波动率最小值 |
| `classic_vol_max` | float | 否 | 3.0 | 2.0 - 5.0 | 波动率最大值 |
| `classic_trend_max_dist` | float | 否 | 0.03 | 0.01 - 0.1 | 趋势距离最大值 |
| `progressive_base_cap` | float | 否 | 30.0 | 20 - 50 | 基础分上限 |
| `progressive_shadow_threshold` | float | 否 | 0.6 | 0.4 - 0.8 | 影线奖励阈值 |
| `progressive_shadow_bonus_rate` | float | 否 | 20.0 | 10 - 50 | 影线奖励倍率 |
| `progressive_body_bonus_threshold` | float | 否 | 0.1 | 0.05 - 0.2 | 实体奖励阈值 |
| `progressive_body_bonus_rate` | float | 否 | 100.0 | 50 - 200 | 实体奖励倍率 |
| `progressive_doji_bonus` | float | 否 | 5.0 | 0 - 20 | 十字星奖励分 |
| `progressive_vol_threshold` | float | 否 | 2.0 | 1.2 - 3.0 | 波动率奖励起点 |
| `progressive_vol_bonus_rate` | float | 否 | 15.0 | 5 - 30 | 波动率奖励倍率 |
| `progressive_extreme_vol_threshold` | float | 否 | 3.0 | 2.0 - 4.0 | 极端波动阈值 |
| `progressive_extreme_vol_bonus` | float | 否 | 10.0 | 5 - 20 | 极端波动奖励 |
| `progressive_penetration_rate` | float | 否 | 30.0 | 10 - 50 | 穿透奖励倍率 |
| `w_shape` | float | 否 | 0.4 | 0 - 1 | 形态权重 |
| `w_trend` | float | 否 | 0.3 | 0 - 1 | 趋势权重 |
| `w_vol` | float | 否 | 0.3 | 0 - 1 | 波动权重 |

### 3.3 响应格式

**成功响应 (200 OK):**

```json
{
  "status": "success",
  "message": "打分配置已热更新",
  "config": {
    "mode": "progressive",
    "w_shape": 0.45,
    "w_trend": 0.30,
    "w_vol": 0.25
  }
}
```

**失败响应 (422 Unprocessable Entity):**

```json
{
  "detail": [
    {
      "loc": ["body", "w_shape"],
      "msg": "ensure this value is greater than or equal to 0",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

**失败响应 (400 Bad Request):**

```json
{
  "detail": "权重总和必须等于 1.0，当前总和为：1.15"
}
```

---

## 4. 分数预览接口

### 4.1 接口定义

```http
POST /api/config/scoring/preview
Content-Type: application/json
```

### 4.2 请求参数

**Request Body:**

```json
{
  "config": {
    "mode": "progressive",
    "w_shape": 0.4,
    "w_trend": 0.3,
    "w_vol": 0.3,
    "classic_shadow_min": 0.6,
    "classic_shadow_max": 0.9
  },
  "symbol": "BTCUSDT",
  "interval": "1h",
  "limit": 500
}
```

**字段说明:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config` | ScoringConfig | 是 | 打分配置对象 |
| `symbol` | string | 否 | 回测币种，默认 "BTCUSDT" |
| `interval` | string | 否 | 回测周期，默认 "1h" |
| `limit` | int | 否 | 回测 K 线数量，默认 500 |

### 4.3 响应格式

**成功响应 (200 OK):**

```json
{
  "status": "success",
  "data": {
    "total_bars": 500,
    "signals_found": 45,
    "score_distribution": {
      "0-20": 5,
      "20-40": 8,
      "40-60": 12,
      "60-80": 15,
      "80-100": 5
    },
    "tier_distribution": {
      "A": 3,
      "B": 10,
      "C": 12,
      "REJECTED": 20
    },
    "sample_signals": [
      {
        "timestamp": 1741000000000,
        "direction": "LONG",
        "score": 85,
        "shape_score": 88,
        "trend_score": 82,
        "vol_score": 75,
        "quality_tier": "A"
      }
    ]
  }
}
```

**字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_bars` | int | 回测 K 线数量 |
| `signals_found` | int | 命中信号数量 |
| `score_distribution` | object | 分数分布直方图数据 |
| `tier_distribution` | object | 信号等级分布 |
| `sample_signals` | array | 样本信号详情 |

---

## 5. Pydantic 模型定义

### 5.1 请求模型

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal, Dict, Any


class ScoringConfigReq(BaseModel):
    """打分配置更新请求体"""

    mode: Optional[Literal["classic", "progressive", "custom"]] = None

    # 经典模式参数
    classic_shadow_min: Optional[float] = Field(None, ge=0.3, le=0.8)
    classic_shadow_max: Optional[float] = Field(None, ge=0.7, le=1.0)
    classic_body_good: Optional[float] = Field(None, ge=0.01, le=0.3)
    classic_body_bad: Optional[float] = Field(None, ge=0.3, le=0.7)
    classic_vol_min: Optional[float] = Field(None, ge=0.8, le=2.0)
    classic_vol_max: Optional[float] = Field(None, ge=2.0, le=5.0)
    classic_trend_max_dist: Optional[float] = Field(None, ge=0.01, le=0.1)

    # 累进模式参数
    progressive_base_cap: Optional[float] = Field(None, ge=20.0, le=50.0)
    progressive_shadow_threshold: Optional[float] = Field(None, ge=0.4, le=0.8)
    progressive_shadow_bonus_rate: Optional[float] = Field(None, ge=10.0, le=50.0)
    progressive_body_bonus_threshold: Optional[float] = Field(None, ge=0.05, le=0.2)
    progressive_body_bonus_rate: Optional[float] = Field(None, ge=50.0, le=200.0)
    progressive_doji_bonus: Optional[float] = Field(None, ge=0.0, le=20.0)
    progressive_vol_threshold: Optional[float] = Field(None, ge=1.2, le=3.0)
    progressive_vol_bonus_rate: Optional[float] = Field(None, ge=5.0, le=30.0)
    progressive_extreme_vol_threshold: Optional[float] = Field(None, ge=2.0, le=4.0)
    progressive_extreme_vol_bonus: Optional[float] = Field(None, ge=5.0, le=20.0)
    progressive_penetration_rate: Optional[float] = Field(None, ge=10.0, le=50.0)

    # 权重配置
    w_shape: Optional[float] = Field(None, ge=0.0, le=1.0)
    w_trend: Optional[float] = Field(None, ge=0.0, le=1.0)
    w_vol: Optional[float] = Field(None, ge=0.0, le=1.0)

    @model_validator(mode='after')
    def check_weights_sum(self) -> 'ScoringConfigReq':
        """验证权重总和为 1.0（仅当三个权重都传入时）"""
        w_shape = self.w_shape
        w_trend = self.w_trend
        w_vol = self.w_vol

        if w_shape is not None and w_trend is not None and w_vol is not None:
            total = round(w_shape + w_trend + w_vol, 4)
            if abs(total - 1.0) > 0.0001:
                raise ValueError(f"权重总和必须等于 1.0，当前总和为：{total}")

        return self


class ScorePreviewRequest(BaseModel):
    """分数预览请求体"""

    config: Dict[str, Any]
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    limit: int = Field(500, ge=100, le=2000)
```

### 5.2 响应模型

```python
from pydantic import BaseModel
from typing import Dict, List, Literal


class ScoringConfigResponse(BaseModel):
    """打分配置响应体"""

    mode: Literal["classic", "progressive", "custom"]
    classic_shadow_min: float
    classic_shadow_max: float
    classic_body_good: float
    classic_body_bad: float
    classic_vol_min: float
    classic_vol_max: float
    classic_trend_max_dist: float
    progressive_base_cap: float
    progressive_shadow_threshold: float
    progressive_shadow_bonus_rate: float
    progressive_body_bonus_threshold: float
    progressive_body_bonus_rate: float
    progressive_doji_bonus: float
    progressive_vol_threshold: float
    progressive_vol_bonus_rate: float
    progressive_extreme_vol_threshold: float
    progressive_extreme_vol_bonus: float
    progressive_penetration_rate: float
    w_shape: float
    w_trend: float
    w_vol: float


class ScorePreviewResponse(BaseModel):
    """分数预览响应体"""

    status: str
    data: Dict[str, Any]
```

---

## 6. 错误码说明

### 6.1 HTTP 状态码

| 状态码 | 说明 | 处理建议 |
|--------|------|----------|
| 200 | 成功 | - |
| 400 | 请求参数错误 | 检查权重和等约束条件 |
| 422 | 参数验证失败 | 检查字段类型和范围 |
| 500 | 服务器内部错误 | 检查日志 |
| 503 | 服务不可用 | 等待服务恢复 |

### 6.2 业务错误码

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| `权重总和必须等于 1.0` | w_shape + w_trend + w_vol != 1.0 | 调整权重值 |
| `未知的打分模式：xxx` | mode 字段值不在枚举范围内 | 使用 classic/progressive/custom |
| `参数 xxx 超出范围` | 参数值不在允许范围内 | 参考字段的可调范围 |

---

## 7. 使用示例

### 7.1 cURL 示例

```bash
# 获取当前配置
curl -X GET http://localhost:8000/api/config/scoring

# 更新配置（切换到累进模式）
curl -X PUT http://localhost:8000/api/config/scoring \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "progressive",
    "w_shape": 0.4,
    "w_trend": 0.3,
    "w_vol": 0.3
  }'

# 分数预览
curl -X POST http://localhost:8000/api/config/scoring/preview \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "mode": "progressive",
      "w_shape": 0.4,
      "w_trend": 0.3,
      "w_vol": 0.3
    },
    "symbol": "BTCUSDT",
    "interval": "1h",
    "limit": 500
  }'
```

### 7.2 Python 示例

```python
import httpx

async def update_scoring_config():
    async with httpx.AsyncClient() as client:
        # 获取配置
        resp = await client.get("http://localhost:8000/api/config/scoring")
        config = resp.json()
        print(f"当前模式：{config['mode']}")

        # 更新配置
        update_data = {
            "mode": "progressive",
            "progressive_shadow_threshold": 0.65,
            "progressive_shadow_bonus_rate": 25.0,
            "w_shape": 0.45,
            "w_trend": 0.30,
            "w_vol": 0.25
        }
        resp = await client.put(
            "http://localhost:8000/api/config/scoring",
            json=update_data
        )
        if resp.status_code == 200:
            print("配置更新成功")
        else:
            print(f"更新失败：{resp.text}")
```

### 7.3 TypeScript 示例

```typescript
// 获取配置
async function getScoringConfig() {
  const res = await fetch('http://localhost:8000/api/config/scoring');
  return await res.json();
}

// 更新配置
async function updateScoringConfig(config: Partial<ScoringConfig>) {
  const res = await fetch('http://localhost:8000/api/config/scoring', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    throw new Error(`更新失败：${res.statusText}`);
  }
  return await res.json();
}

// 使用示例
try {
  await updateScoringConfig({
    mode: 'progressive',
    w_shape: 0.4,
    w_trend: 0.3,
    w_vol: 0.3,
  });
} catch (error) {
  console.error(error);
}
```

---

## 8. 附录

### 8.1 相关文件

- [产品需求文档](./scoring_config_prd.md)
- [技术设计文档](./scoring_config_technical_design.md)
- [前端 UI 开发文档](./frontend/scoring_config_ui.md)

### 8.2 修订历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2026-03-03 | Claude | 初始版本 |
