# 核心系统与监控中台 API 契约设计 (v3)

本文档定义了前端指挥中心 (Apple-Style SPA) 与后端风控计算引擎之间的通信契约。
系统已重命名为 `monitor` (加密货币信号监测系统)。
严格遵循 RESTful 风格，所有请求与响应内容均使用 JSON 格式。

---

## 1. 系统遥测与性能指标 (Telemetry)

用于前端仪表盘的实时状态监控，必须支撑 7x24 小时运行。

### `GET /api/system/status`
获取系统的健康状态与交易所 API 权重消耗。

**请求参数:**
*(无)*

**响应 (200 OK):**
```json
{
  "is_connected": true,
  "api_latency_ms": 120,
  "api_weight_usage": 45.5,
  "uptime": "12d 4h 3m"
}
```
*说明: `api_weight_usage` 表示当前币安 API 权重使用率 (0-100%)，前端需配合进度条展示，并在高占用时告警。*

---

## 1.5 交易所账户与持仓 (Dashboard)

获取真实的账户余额及持仓明细，用于在大屏展示真实账户状况。

### `GET /api/account/dashboard`
获取真实账户余额和持仓列表。验证 Key 是否只读与有效。

**请求参数:**
*(无)*

**响应 (200 OK):**
```json
{
  "status": "success",
  "data": {
    "total_wallet_balance": 15000.50,
    "available_balance": 14950.00,
    "total_balance": 15000.50,
    "available_margin": 14800.00,
    "total_unrealized_pnl": 150.5,
    "current_positions_count": 2,
    "positions": [
      {
        "symbol": "BTCUSDT",
        "positionAmt": 0.5,
        "entryPrice": 62000.0,
        "unrealized_pnl": 150.5,
        "leverage": 20
      }
    ]
  }
}
```

### `GET /api/account/position/detail/{symbol}`
获取指定交易对的实盘深度持仓信息及关联的止盈/止损委托单状态。
*功能定义*：配合前端新的“用户持仓” Tab 页面展示。

**请求参数:**
* Path: `symbol` (string): 交易对，如 `BTCUSDT`

**响应 (200 OK):**
```json
{
  "status": "success",
  "data": {
    "symbol": "BTCUSDT",
    "direction": "LONG",
    "leverage": 20.0,
    "quantity": 0.5,
    "entry_price": 62000.0,
    "position_value": 31000.0,
    "unrealized_pnl": 150.5,
    "open_time": 1716382000000,
    "status": "OPEN",
    "take_profit_price": 65000.0,
    "take_profit_order_id": "123456789",
    "stop_loss_price": 61000.0,
    "stop_loss_order_id": "987654321"
  }
}
```

**响应 (400 / 401 / 403 异常说明):**
```json
{
  "detail": "BINANCE API ERROR: Invalid API Key or IP not allowed. Ensure the key is Read-Only. (...)"
}
```

---

## 2. 信号过滤与查询 (Query)

支持复杂维度的历史信号检索。

### `GET /api/signals`
根据 `SignalFilter` 实体结构分页/条件查询信号列表。

**Query 参数 (可选):**
* `symbols` (string): 逗号分隔的交易对，如 `BTCUSDT,ETHUSDT`
* `intervals` (string): 逗号分隔的时间级别，如 `15m,1h,4h,1d`
* `directions` (string): 逗号分隔的方向，如 `LONG,SHORT`
* `start_time` (int): 毫秒时间戳起始 (例如最近1小时/24小时的时间戳)
* `end_time` (int): 毫秒时间戳结束
* `min_score` (int): 最低分数线 (0-100)
* `page` (int): 默认 1
* `size` (int): 默认 50

**响应 (200 OK):**
```json
{
  "total": 128,
  "items": [
    {
      "symbol": "BTCUSDT",
      "interval": "15m",
      "direction": "LONG",
      "entry_price": 64000.5,
      "stop_loss": 63000.0,
      "take_profit_1": 65500.75,
      "timestamp": 1716382000000,
      "reason": "Pinbar+EMA60",
      "sl_distance_pct": 0.015,
      "score": 85,
      "score_details": {
         "shape": 35.0,
         "trend": 25.0,
         "vol": 25.0
      },
      "shadow_ratio": 2.8,
      "ema_distance": 1.5,
      "volatility_atr": 120.5
    }
  ]
}
```

### `DELETE /api/signals`
批量或单笔删除历史信号。

**请求 Body:**
```json
{
  "signal_ids": ["uuid-1", "uuid-2"]
}
```

**响应 (200 OK):**
```json
{
  "deleted_count": 2
}
```

---

## 2.5 实时市场数据 (Market)

### `GET /api/market/prices`
获取当前监控币种的实时价格心跳。

**请求参数:**
*(无)*

**响应 (200 OK):**
```json
{
  "BTCUSDT": 64050.00,
  "ETHUSDT": 3450.25,
  "SOLUSDT": 145.50
}
```

---

## 3. 热加载动态配置 (Config)

用于后端引擎实时热加载的系统参数设置。

### `GET /api/config`
获取当前的系统所有配置参数。

**响应 (200 OK):**
```json
{
  "system_enabled": true,
  "active_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "monitor_intervals": {
    "15m": { "use_trend_filter": true },
    "1h": { "use_trend_filter": true },
    "4h": { "use_trend_filter": true }
  },
  "risk_config": {
    "risk_pct": 0.02,
    "max_sl_dist": 0.035,
    "max_leverage": 20.0
  },
  "scoring_weights": {
    "w_shape": 0.5,
    "w_trend": 0.3,
    "w_vol": 0.2
  },
  "exchange_settings": {
    "has_binance_key": true 
  },
  "webhook_settings": {
    "global_push_enabled": true,
    "feishu_enabled": true,
    "wecom_enabled": false,
    "has_feishu_secret": true,
    "has_wecom_secret": false
  },
  "auto_order_status": "OFF"
}
```
*说明: 接口不会下发明文 `secret`。`auto_order_status` 始终为 OFF，且前端必须置灰不可编辑（受后端底层锁定，彻底杜绝自动下单）。*

### `PUT /api/config`
全量/增量更新系统配置。所有传入字段必须通过 Pydantic 严格校验类型与边界。
**核心约束**：`scoring_weights` 中三个权重之和必须严格等于 1.0 ($W_{shape} + W_{trend} + W_{vol} = 1.0$)。`active_symbols` 支持多选传入。

**请求 Body:**
```json
{
  "active_symbols": ["BTCUSDT", "ETHUSDT"],
  "monitor_intervals": {
    "15m": { "use_trend_filter": true },
    "1h": { "use_trend_filter": true },
    "4h": { "use_trend_filter": false }
  },
  "scoring_weights": {
    "w_shape": 0.4,
    "w_trend": 0.4,
    "w_vol": 0.2
  },
  "exchange_settings": {
    "binance_api_key": "YOUR_API_KEY",
    "binance_api_secret": "YOUR_API_SECRET"
  },
  "webhook_settings": {
    "global_push_enabled": true,
    "feishu_enabled": true,
    "wecom_enabled": true,
    "feishu_secret": "encrypted_feishu_key",
    "wecom_secret": "encrypted_wecom_key"
  }
}
```

**响应 (200 OK):**
```json
{
  "status": "success",
  "message": "Configuration hot-reloaded successfully"
}
```
*说明: `webhook_settings.feishu_secret` 等敏感信息在前端通过 HTTPS 传输后，后端需在入库前进行单向加密或落本地 KMS 系统保护。*

---

## 4. 用户偏好设置 (User Preferences)

### `PUT /api/preferences/view`
用于持久化前端界面的自定义显示状态（例如信号列表中动态表头的列显示配置）。

**请求 Body:**
```json
{
  "signals_table_columns": {
    "timestamp": true,
    "symbol": true,
    "interval": true,
    "direction": true,
    "score": true,
    "entry_price": true,
    "shadow_ratio": false,
    "ema_distance": false,
    "volatility_atr": false
  }
}
```

**响应 (200 OK):**
```json
{
  "status": "success"
}
```
