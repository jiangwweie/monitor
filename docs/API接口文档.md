# CryptoRadar API 接口文档

## 文档说明

本文档描述了 CryptoRadar 信号监测系统的所有 REST API 接口。所有接口均基于 FastAPI 框架实现，返回 JSON 格式数据。

**基本信息**：
- **基础 URL**: `http://localhost:8000`
- **API 版本**: v1
- **认证方式**: 当前为内部系统，暂无需认证
- **数据格式**: JSON

---

## 标准响应格式

### 成功响应

```json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "timestamp": 1709971200000,
    "message": "可选的消息内容"
  }
}
```

### 错误响应

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "错误描述信息",
  "details": { ... }
}
```

---

## 目录

1. [系统状态](#1-系统状态)
2. [账户与持仓](#2-账户与持仓)
3. [信号管理](#3-信号管理)
4. [历史扫描](#4-历史扫描)
5. [市场数据](#5-市场数据)
6. [图表数据](#6-图表数据)
7. [配置管理](#7-配置管理)
8. [用户偏好](#8-用户偏好)

---

## 1. 系统状态

### 1.1 获取系统健康状态

获取系统的健康状态、连接状态、API 延迟和运行时间。

**接口**: `GET /api/system/status`

**请求参数**: 无

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "is_connected": true,
    "api_latency_ms": 45,
    "api_weight_usage": 12.5,
    "uptime": "3d 5h 42m"
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_connected` | boolean | WebSocket 连接状态 |
| `api_latency_ms` | integer | Binance API 请求延迟 (毫秒) |
| `api_weight_usage` | number | Binance API 权重消耗百分比 (0-100) |
| `uptime` | string | 系统运行时间 (格式：Xd Xh Xm) |

**错误码**:
- `503`: 服务不可用

---

## 2. 账户与持仓

### 2.1 获取账户仪表盘数据

获取账户总览数据，包括钱包余额、未实现盈亏、持仓数量等。

**接口**: `GET /api/account/dashboard`

**请求参数**: 无

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "wallet_balance": 10000.00,
    "total_unrealized_pnl": 256.80,
    "margin_balance": 10256.80,
    "current_positions_count": 2,
    "positions": [
      {
        "symbol": "ETHUSDT",
        "positionAmt": 1.5,
        "entryPrice": 3450.00,
        "unrealized_pnl": 125.50,
        "leverage": 10
      },
      {
        "symbol": "BTCUSDT",
        "positionAmt": -0.05,
        "entryPrice": 68000.00,
        "unrealized_pnl": 131.30,
        "leverage": 5
      }
    ]
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `wallet_balance` | number | 钱包余额 (USDT) |
| `total_unrealized_pnl` | number | 总计未实现盈亏 (USDT) |
| `margin_balance` | number | 保证金余额 (= wallet_balance + unrealized_pnl) |
| `current_positions_count` | integer | 当前持仓数量 |
| `positions` | array | 持仓列表 |

**持仓对象字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 交易对 |
| `positionAmt` | number | 持仓数量 (正数=做多，负数=做空) |
| `entryPrice` | number | 入场均价 |
| `unrealized_pnl` | number | 未实现盈亏 |
| `leverage` | integer | 杠杆倍数 |

**错误码**:
- `401`: API Key 无效
- `403`: IP 不被允许
- `503`: Binance API 不可用

---

### 2.2 获取钱包余额

获取账户钱包余额信息。

**接口**: `GET /api/account/wallet-balance`

**请求参数**: 无

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "wallet_balance": 10000.00
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

---

### 2.3 获取账户余额详情

获取完整的账户余额信息，包括可用余额等。

**接口**: `GET /api/account/balance`

**请求参数**: 无

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "total_wallet_balance": 10000.00,
    "available_balance": 7500.00,
    "total_unrealized_pnl": 256.80,
    "total_margin_balance": 10256.80
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

**错误码**:
- `400`: Binance API Key 未配置

---

### 2.4 获取持仓列表

获取所有持仓的详细信息。

**接口**: `GET /api/account/positions`

**请求参数**: 无

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "positions": [
      {
        "symbol": "ETHUSDT",
        "quantity": 1.5,
        "entry_price": 3450.00,
        "leverage": 10,
        "unrealized_pnl": 125.50,
        "position_value": 5175.00,
        "direction": "LONG"
      }
    ]
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

---

### 2.5 刷新持仓

实时刷新持仓数据，从 Binance API 获取最新状态。

**接口**: `GET /api/positions/refresh`

**请求参数**: 无

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "positions": [
      {
        "symbol": "ETHUSDT",
        "positionAmt": 1.5,
        "entryPrice": 3450.00,
        "unrealized_pnl": 130.20,
        "leverage": 10
      }
    ]
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

---

### 2.6 获取单个持仓详情

获取指定交易对的实盘持仓详情，包括止盈止损挂单。

**接口**: `GET /api/account/position/detail/{symbol}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 交易对，如 "ETHUSDT" |

**请求参数**: 无

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "symbol": "ETHUSDT",
    "direction": "LONG",
    "leverage": 10,
    "quantity": 1.5,
    "entry_price": 3450.00,
    "position_value": 5175.00,
    "unrealized_pnl": 125.50,
    "open_time": 1709884800000,
    "status": "OPEN",
    "take_profit_price": 3600.00,
    "take_profit_order_id": "12345678",
    "stop_loss_price": 3350.00,
    "stop_loss_order_id": "12345679"
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 交易对 |
| `direction` | string | 持仓方向 ("LONG" / "SHORT") |
| `leverage` | integer | 杠杆倍数 |
| `quantity` | number | 持仓数量 |
| `entry_price` | number | 入场均价 |
| `position_value` | number | 仓位价值 |
| `unrealized_pnl` | number | 未实现盈亏 |
| `open_time` | integer | 开单时间戳 (毫秒) |
| `status` | string | 持仓状态 ("OPEN" / "CLOSED") |
| `take_profit_price` | number | 止盈价格 (可选) |
| `take_profit_order_id` | string | 止盈单号 (可选) |
| `stop_loss_price` | number | 止损价格 (可选) |
| `stop_loss_order_id` | string | 止损单号 (可选) |

**错误码**:
- `404`: 持仓不存在

---

## 3. 信号管理

### 3.1 获取信号列表

分页、多维度查询历史信号记录。

**接口**: `GET /api/signals`

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string | 否 | - | 交易对列表，逗号分隔，如 "BTCUSDT,ETHUSDT" |
| `intervals` | string | 否 | - | 时间周期列表，逗号分隔，如 "15m,1h,4h" |
| `directions` | string | 否 | - | 方向列表，逗号分隔，如 "LONG,SHORT" |
| `start_time` | integer | 否 | - | 开始时间戳 (毫秒) |
| `end_time` | integer | 否 | - | 结束时间戳 (毫秒) |
| `min_score` | integer | 否 | - | 最低分数 |
| `max_score` | integer | 否 | - | 最高分数 |
| `source` | string | 否 | - | 信号来源："realtime" 或 "history_scan" |
| `quality_tier` | string | 否 | - | 信号等级："A"、"B" 或 "C" |
| `sort_by` | string | 否 | "timestamp" | 排序字段："timestamp" 或 "score" |
| `order` | string | 否 | "desc" | 排序方向："asc" 或 "desc" |
| `page` | integer | 否 | 1 | 页码，从 1 开始 |
| `size` | integer | 否 | 20 | 每页数量，最大 200 |

**响应示例**:
```json
{
  "items": [
    {
      "id": 1234,
      "symbol": "ETHUSDT",
      "interval": "1h",
      "direction": "LONG",
      "entry_price": 3500.00,
      "stop_loss": 3380.00,
      "take_profit_1": 3680.00,
      "timestamp": 1709971200000,
      "reason": "Pinbar+EMA60",
      "sl_distance_pct": 0.0343,
      "score": 75,
      "score_details": {
        "shape": 82.5,
        "trend": 68.0,
        "vol": 71.5,
        "quality_tier": "B",
        "risk_penalty": 0
      },
      "shadow_ratio": 3.25,
      "ema_distance": 1.25,
      "volatility_atr": 2.1,
      "source": "realtime",
      "is_contrarian": false,
      "is_shape_divergent": false,
      "quality_tier": "B"
    }
  ],
  "total": 156,
  "page": 1,
  "size": 20
}
```

**信号对象字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | integer | 数据库 ID |
| `symbol` | string | 交易对 |
| `interval` | string | 时间级别 ("15m"/"1h"/"4h"/"1d") |
| `direction` | string | 方向 ("LONG" / "SHORT") |
| `entry_price` | number | 入场价格 |
| `stop_loss` | number | 止损价格 |
| `take_profit_1` | number | 第一目标价位 |
| `timestamp` | integer | 信号时间戳 (毫秒) |
| `reason` | string | 命中理由 |
| `sl_distance_pct` | number | 止损距离百分比 |
| `score` | integer | 信号得分 (0-100) |
| `score_details` | object | 打分详情 |
| `shadow_ratio` | number | 影线/实体比 |
| `ema_distance` | number | 价格与 EMA60 距离 (%) |
| `volatility_atr` | number | K 线波幅/ATR 倍数 |
| `source` | string | 来源 ("realtime" / "history_scan") |
| `is_contrarian` | boolean | 是否 MTF 逆势 |
| `is_shape_divergent` | boolean | 是否形态背离 |
| `quality_tier` | string | 质量分级 ("A" / "B" / "C") |

**score_details 字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `shape` | number | 形态分 (0-100) |
| `trend` | number | 趋势分 (0-100) |
| `vol` | number | 波动分 (0-100) |
| `quality_tier` | string | 质量等级 |
| `risk_penalty` | number | 风险扣分 |

**错误码**:
- `400`: 参数格式错误
- `500`: 服务器内部错误

---

### 3.2 批量删除信号

批量删除指定的信号记录。

**接口**: `DELETE /api/signals`

**请求体**:
```json
{
  "signal_ids": [1, 2, 3, 4, 5]
}
```

**响应示例**:
```json
{
  "status": "success",
  "deleted_count": 5
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `signal_ids` | array | 要删除的信号 ID 列表 |

**错误码**:
- `400`: 请求体格式错误

---

### 3.3 清空所有信号

清空所有信号记录。

**接口**: `DELETE /api/signals/clear`

**请求参数**: 无

**响应示例**:
```json
{
  "status": "success",
  "deleted_count": 156
}
```

**错误码**:
- `500`: 服务器内部错误

---

## 4. 历史扫描

### 4.1 提交历史扫描任务

提交一个历史信号扫描任务，异步执行。

**接口**: `POST /api/signals/history-check`

**请求体**:
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-03-01",
  "symbol": "ETHUSDT",
  "interval": "1h"
}
```

**响应示例**:
```json
{
  "status": "accepted",
  "task_id": "scan-abc123def456",
  "message": "历史信号扫描任务已启动"
}
```

**字段说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `start_date` | string | 是 | 开始日期 (格式：YYYY-MM-DD) |
| `end_date` | string | 是 | 结束日期 (格式：YYYY-MM-DD) |
| `symbol` | string | 是 | 交易对，必须在激活列表中 |
| `interval` | string | 是 | 时间周期，必须在监控配置中 |

**约束条件**:
- `start_date` 必须早于 `end_date`
- `symbol` 必须在当前激活的币种列表中
- `interval` 必须在当前监控周期配置中

**错误码**:
- `400`: 参数验证失败或币种/周期不在配置中
- `503`: 历史扫描服务未初始化

---

### 4.2 获取扫描任务状态

轮询历史扫描任务的执行状态。

**接口**: `GET /api/signals/history-check/{task_id}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |

**响应示例 (进行中)**:
```json
{
  "task_id": "scan-abc123def456",
  "status": "running",
  "progress": 45,
  "message": "正在执行策略回放扫描...",
  "config": {
    "symbol": "ETHUSDT",
    "interval": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-03-01"
  }
}
```

**响应示例 (已完成)**:
```json
{
  "task_id": "scan-abc123def456",
  "status": "completed",
  "progress": 100,
  "message": "扫描完成：共 1440 根 K 线，发现 23 个信号",
  "config": {
    "symbol": "ETHUSDT",
    "interval": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-03-01"
  },
  "result": {
    "total_bars_scanned": 1440,
    "signals_found": 23,
    "signals_saved": 23
  }
}
```

**响应示例 (失败)**:
```json
{
  "task_id": "scan-abc123def456",
  "status": "failed",
  "progress": 100,
  "message": "扫描失败：网络超时",
  "result": {
    "error": "网络超时"
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |
| `status` | string | 任务状态 ("running" / "completed" / "failed") |
| `progress` | integer | 进度百分比 (0-100) |
| `message` | string | 当前状态描述 |
| `config` | object | 扫描配置 (symbol, interval, start_date, end_date) |
| `result` | object | 扫描结果 (完成后返回) |

**轮询建议**:
- 推荐每 2-3 秒轮询一次
- 当 `status` 为 "completed" 或 "failed" 时停止轮询

**错误码**:
- `404`: 任务不存在
- `503`: 历史扫描服务未初始化

---

## 5. 市场数据

### 5.1 获取实时价格

获取当前监控币种的实时价格。

**接口**: `GET /api/market/prices`

**请求参数**: 无

**响应示例**:
```json
{
  "ETHUSDT": 3520.50,
  "BTCUSDT": 68250.00,
  "SOLUSDT": 145.80,
  "BNBUSDT": 580.20
}
```

**说明**:
- 数据来源于引擎内存中维护的最新价格字典
- 出于性能考虑，不调用 Binance API
- 价格随 WebSocket K 线流实时更新

---

## 6. 图表数据

### 6.1 获取 K 线图表数据

获取指定交易对的 K 线和信号标记聚合数据，用于 TradingView 风格图表。

**接口**: `GET /api/chart/data/{symbol}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 交易对 |

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `interval` | string | 否 | "1h" | K 线周期 |
| `limit` | integer | 否 | 200 | K 线数量，最大 500 |
| `end_time` | integer | 否 | 当前时间 | 结束时间戳 (毫秒) |

**响应示例**:
```json
{
  "symbol": "ETHUSDT",
  "interval": "1h",
  "bars": [
    {
      "time": 1709884800,
      "open": 3450.00,
      "high": 3480.00,
      "low": 3420.00,
      "close": 3470.00,
      "volume": 12500
    }
  ],
  "signals": [
    {
      "time": 1709884800,
      "direction": "LONG",
      "score": 75,
      "entry_price": 3470.00,
      "stop_loss": 3380.00,
      "take_profit": 3605.00
    }
  ]
}
```

**字段说明**:

**K 线对象**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `time` | integer | 时间戳 (秒) |
| `open` | number | 开盘价 |
| `high` | number | 最高价 |
| `low` | number | 最低价 |
| `close` | number | 收盘价 |
| `volume` | number | 成交量 |

**信号对象**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `time` | integer | 时间戳 (秒) |
| `direction` | string | 方向 ("LONG" / "SHORT") |
| `score` | integer | 得分 |
| `entry_price` | number | 入场价 |
| `stop_loss` | number | 止损价 |
| `take_profit` | number | 止盈价 |

**错误码**:
- `400`: 参数错误
- `503`: 图表服务未初始化
- `500`: 服务器内部错误

---

## 7. 配置管理

### 7.1 获取完整配置

获取系统全部配置信息。

**接口**: `GET /api/config`

**请求参数**: 无

**响应示例**:
```json
{
  "system_enabled": true,
  "active_symbols": ["ETHUSDT", "BTCUSDT", "SOLUSDT"],
  "monitor_intervals": {
    "15m": { "use_trend_filter": true },
    "1h": { "use_trend_filter": true },
    "4h": { "use_trend_filter": false }
  },
  "risk_config": {
    "risk_pct": 0.02,
    "max_sl_dist": 0.035,
    "max_leverage": 20.0
  },
  "scoring_weights": {
    "w_shape": 0.4,
    "w_trend": 0.3,
    "w_vol": 0.3
  },
  "pinbar_config": {
    "body_max_ratio": 0.25,
    "shadow_min_ratio": 2.5,
    "volatility_atr_multiplier": 1.2,
    "doji_threshold": 0.05,
    "doji_shadow_bonus": 0.6,
    "mtf_trend_filter_mode": "soft",
    "dynamic_sl_enabled": true,
    "dynamic_sl_base": 0.035,
    "dynamic_sl_atr_multiplier": 0.5
  },
  "auto_order_status": "OFF",
  "push_config": {
    "global_enabled": true,
    "feishu_enabled": false,
    "wecom_enabled": false
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `system_enabled` | boolean | 系统运行开关 |
| `active_symbols` | array | 活跃交易对列表 |
| `monitor_intervals` | object | 监控周期配置 |
| `risk_config` | object | 风控配置 |
| `scoring_weights` | object | 评分权重配置 |
| `pinbar_config` | object | Pinbar 策略配置 |
| `auto_order_status` | string | 自动下单状态 (固定为 "OFF") |
| `push_config` | object | 推送配置 |

---

### 7.2 更新完整配置

热更新系统配置。

**接口**: `PUT /api/config`

**请求体**:
```json
{
  "system_enabled": true,
  "active_symbols": ["ETHUSDT", "BTCUSDT"],
  "monitor_intervals": {
    "15m": { "use_trend_filter": true },
    "1h": { "use_trend_filter": true }
  },
  "scoring_weights": {
    "w_shape": 0.4,
    "w_trend": 0.3,
    "w_vol": 0.3
  },
  "pinbar_config": {
    "body_max_ratio": 0.25,
    "shadow_min_ratio": 2.5,
    "volatility_atr_multiplier": 1.2
  },
  "risk_config": {
    "risk_pct": 0.02,
    "max_sl_dist": 0.035,
    "max_leverage": 20.0
  }
}
```

**说明**:
- 所有字段均为可选，仅更新传入的字段
- `auto_order_status` 的修改会被后端拒绝（安全锁）
- `exchange_settings` 和 `webhook_settings` 已废弃，请通过 `.env` 文件配置

**响应示例**:
```json
{
  "status": "success",
  "message": "Configuration hot-reloaded successfully"
}
```

**错误码**:
- `400`: 参数验证失败
- `500`: 服务器内部错误

---

### 7.3 获取系统配置

获取系统基础配置（启用状态、币种列表、监控周期）。

**接口**: `GET /api/config/system`

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "system_enabled": true,
    "active_symbols": ["ETHUSDT", "BTCUSDT"],
    "monitor_intervals": {
      "15m": { "use_trend_filter": true },
      "1h": { "use_trend_filter": true }
    }
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

---

### 7.4 获取币种配置

获取监控币种列表。

**接口**: `GET /api/config/symbols`

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "active_symbols": ["ETHUSDT", "BTCUSDT", "SOLUSDT"]
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

---

### 7.5 获取监控周期配置

获取各时间周期的监控设置。

**接口**: `GET /api/config/monitor`

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "monitor_intervals": {
      "15m": { "use_trend_filter": true },
      "1h": { "use_trend_filter": true },
      "4h": { "use_trend_filter": false }
    }
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

---

### 7.6 更新监控配置

热更新监控配置（币种列表和监控周期）。

**接口**: `PUT /api/config/monitor`

**请求体**:
```json
{
  "active_symbols": ["ETHUSDT", "BTCUSDT", "SOLUSDT"],
  "monitor_intervals": {
    "15m": { "use_trend_filter": true },
    "1h": { "use_trend_filter": true },
    "4h": { "use_trend_filter": false }
  }
}
```

**响应示例**:
```json
{
  "status": "success",
  "data": {},
  "meta": {
    "timestamp": 1709971200000,
    "message": "监控配置已热更新"
  }
}
```

**错误码**:
- `400`: 配置校验失败

---

### 7.7 获取风控配置

获取风控相关配置。

**接口**: `GET /api/config/risk`

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "risk_pct": 0.02,
    "max_sl_dist": 0.035,
    "max_leverage": 20.0
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 | 范围 |
|------|------|------|------|
| `risk_pct` | number | 单笔风险百分比 | 0.005 - 0.1 |
| `max_sl_dist` | number | 最大止损距离 | 0.01 - 0.1 |
| `max_leverage` | number | 最大杠杆倍数 | 1.0 - 125.0 |

---

### 7.8 更新风控配置

热更新风控配置。

**接口**: `PUT /api/config/risk`

**请求体**:
```json
{
  "risk_pct": 0.02,
  "max_sl_dist": 0.035,
  "max_leverage": 20.0
}
```

**响应示例**:
```json
{
  "status": "success",
  "data": {},
  "meta": {
    "timestamp": 1709971200000,
    "message": "风控配置已热更新"
  }
}
```

**错误码**:
- `400`: 参数超出范围

---

### 7.9 获取打分配置

获取评分系统的配置，包括模式和参数。

**接口**: `GET /api/config/scoring`

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "mode": "classic",
    "w_shape": 0.4,
    "w_trend": 0.3,
    "w_vol": 0.3,
    "classic_shadow_min": 0.6,
    "classic_shadow_max": 0.9,
    "classic_body_good": 0.1,
    "classic_body_bad": 0.5,
    "classic_vol_min": 1.2,
    "classic_vol_max": 3.0,
    "classic_trend_max_dist": 0.03
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | string | 打分模式 ("classic" / "progressive" / "custom") |
| `w_shape` | number | 形态权重 (0-1) |
| `w_trend` | number | 趋势权重 (0-1) |
| `w_vol` | number | 波动权重 (0-1) |

**经典模式参数**:
| 字段 | 类型 | 说明 | 范围 |
|------|------|------|------|
| `classic_shadow_min` | number | 影线比例最小值 | 0.3 - 0.8 |
| `classic_shadow_max` | number | 影线比例最大值 | 0.7 - 1.0 |
| `classic_body_good` | number | 实体比例优秀阈值 | 0.01 - 0.3 |
| `classic_body_bad` | number | 实体比例差阈值 | 0.3 - 0.7 |
| `classic_vol_min` | number | 波动率最小值 | 0.8 - 2.0 |
| `classic_vol_max` | number | 波动率最大值 | 2.0 - 5.0 |
| `classic_trend_max_dist` | number | 趋势距离最大值 | 0.01 - 0.1 |

**错误码**:
- `400`: 权重总和不等于 1.0

---

### 7.10 更新打分配置

热更新打分配置。

**接口**: `PUT /api/config/scoring`

**请求体**:
```json
{
  "mode": "classic",
  "w_shape": 0.4,
  "w_trend": 0.3,
  "w_vol": 0.3,
  "classic_shadow_min": 0.6,
  "classic_shadow_max": 0.9
}
```

**说明**:
- 仅更新传入的字段
- 如果同时更新了三个权重 (`w_shape`, `w_trend`, `w_vol`)，会自动验证总和为 1.0
- 如果只更新单个权重，会自动重新平衡其他两个权重

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "mode": "classic",
    "w_shape": 0.4,
    "w_trend": 0.3,
    "w_vol": 0.3
  },
  "meta": {
    "timestamp": 1709971200000,
    "message": "打分配置已热更新"
  }
}
```

**错误码**:
- `400`: 权重总和不等于 1.0 或模式无效

---

### 7.11 获取 Pinbar 配置

获取 Pinbar 形态识别参数配置。

**接口**: `GET /api/config/pinbar`

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "body_max_ratio": 0.25,
    "shadow_min_ratio": 2.5,
    "volatility_atr_multiplier": 1.2,
    "doji_threshold": 0.05,
    "doji_shadow_bonus": 0.6,
    "mtf_trend_filter_mode": "soft",
    "dynamic_sl_enabled": true,
    "dynamic_sl_base": 0.035,
    "dynamic_sl_atr_multiplier": 0.5
  },
  "meta": {
    "timestamp": 1709971200000
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 | 范围 |
|------|------|------|------|
| `body_max_ratio` | number | 实体最大比例 | 0.05 - 0.8 |
| `shadow_min_ratio` | number | 影线最小比例 | 1.0 - 10.0 |
| `volatility_atr_multiplier` | number | 波动率 ATR 乘数 | 0.5 - 5.0 |
| `doji_threshold` | number | 十字星阈值 | 0.01 - 0.2 |
| `doji_shadow_bonus` | number | 十字星影线放宽系数 | 0.1 - 1.0 |
| `mtf_trend_filter_mode` | string | MTF 过滤模式 ("soft" / "hard") | - |
| `dynamic_sl_enabled` | boolean | 启用动态止损 | - |
| `dynamic_sl_base` | number | 动态止损基准值 | 0.01 - 0.1 |
| `dynamic_sl_atr_multiplier` | number | ATR 贡献系数 | 0.0 - 2.0 |

---

### 7.12 更新 Pinbar 配置

热更新 Pinbar 配置。

**接口**: `PUT /api/config/pinbar`

**请求体**:
```json
{
  "body_max_ratio": 0.25,
  "shadow_min_ratio": 2.5,
  "volatility_atr_multiplier": 1.2,
  "doji_threshold": 0.05,
  "doji_shadow_bonus": 0.6,
  "mtf_trend_filter_mode": "soft",
  "dynamic_sl_enabled": true,
  "dynamic_sl_base": 0.035,
  "dynamic_sl_atr_multiplier": 0.5
}
```

**响应示例**:
```json
{
  "status": "success",
  "data": {},
  "meta": {
    "timestamp": 1709971200000,
    "message": "Pinbar 配置已热更新"
  }
}
```

---

## 8. 用户偏好

### 8.1 获取视图偏好

获取前端表格列的显示配置。

**接口**: `GET /api/preferences/view`

**响应示例**:
```json
{
  "signals_table_columns": {
    "symbol": true,
    "interval": true,
    "direction": true,
    "score": true,
    "quality_tier": true,
    "entry_price": false,
    "stop_loss": true
  }
}
```

---

### 8.2 更新视图偏好

保存前端表格列的显示配置。

**接口**: `PUT /api/preferences/view`

**请求体**:
```json
{
  "signals_table_columns": {
    "symbol": true,
    "interval": true,
    "direction": true,
    "score": true,
    "quality_tier": true,
    "entry_price": false,
    "stop_loss": true
  }
}
```

**响应示例**:
```json
{
  "status": "success"
}
```

---

## 错误码汇总

| 错误码 | 说明 |
|--------|------|
| `200` | 请求成功 |
| `202` | 请求已接受（异步任务） |
| `400` | 请求参数错误 |
| `401` | 未授权（API Key 无效） |
| `403` | 禁止访问（IP 限制） |
| `404` | 资源不存在 |
| `500` | 服务器内部错误 |
| `503` | 服务不可用 |

---

## Binance API 错误码

当后端调用 Binance API 失败时，会返回以下错误：

| 错误码 | 说明 |
|--------|------|
| `-1021` | 时间戳超出接收窗口（本地时间不同步） |
| `-2014` | API Key 格式错误 |
| `-2010` | 余额不足 |

---

## 使用示例

### cURL 示例

```bash
# 获取系统状态
curl http://localhost:8000/api/system/status

# 获取信号列表（带过滤）
curl "http://localhost:8000/api/signals?symbols=ETHUSDT,BTCUSDT&directions=LONG&min_score=60&page=1&size=20"

# 提交历史扫描任务
curl -X POST http://localhost:8000/api/signals/history-check \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-03-01",
    "symbol": "ETHUSDT",
    "interval": "1h"
  }'

# 更新风控配置
curl -X PUT http://localhost:8000/api/config/risk \
  -H "Content-Type: application/json" \
  -d '{
    "risk_pct": 0.02,
    "max_sl_dist": 0.035,
    "max_leverage": 20.0
  }'
```

### JavaScript (Fetch) 示例

```javascript
// 获取信号列表
async function getSignals() {
  const response = await fetch(
    'http://localhost:8000/api/signals?symbols=ETHUSDT&directions=LONG&min_score=60'
  );
  const data = await response.json();
  console.log(data);
}

// 提交历史扫描任务
async function submitHistoryScan() {
  const response = await fetch(
    'http://localhost:8000/api/signals/history-check',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_date: '2024-01-01',
        end_date: '2024-03-01',
        symbol: 'ETHUSDT',
        interval: '1h'
      })
    }
  );
  const { task_id } = await response.json();

  // 轮询任务状态
  while (true) {
    const statusResponse = await fetch(
      `http://localhost:8000/api/signals/history-check/${task_id}`
    );
    const status = await statusResponse.json();

    if (status.status === 'completed' || status.status === 'failed') {
      console.log('任务完成:', status);
      break;
    }

    console.log('任务进行中:', status.progress + '%');
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
}
```

### Python 示例

```python
import requests

# 获取信号列表
def get_signals():
    response = requests.get(
        'http://localhost:8000/api/signals',
        params={
            'symbols': 'ETHUSDT,BTCUSDT',
            'directions': 'LONG',
            'min_score': 60,
            'page': 1,
            'size': 20
        }
    )
    return response.json()

# 更新风控配置
def update_risk_config():
    response = requests.put(
        'http://localhost:8000/api/config/risk',
        json={
            'risk_pct': 0.02,
            'max_sl_dist': 0.035,
            'max_leverage': 20.0
        }
    )
    return response.json()

# 轮询历史扫描任务
def poll_history_task(task_id):
    while True:
        response = requests.get(
            f'http://localhost:8000/api/signals/history-check/{task_id}'
        )
        status = response.json()

        if status['status'] in ['completed', 'failed']:
            return status

        print(f"进度：{status['progress']}%")
        time.sleep(2)
```

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2024-03-10 | 初始版本，包含所有核心 API |

---

*文档最后更新：2024-03-10*
