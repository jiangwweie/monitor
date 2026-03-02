# 核心系统与监控中台 API 契约设计 (v4)

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

## 2.5 历史信号检查 (History Scan)

对指定币种、时间级别和日期区间执行历史 K 线拉取 + 策略回放。
由于扫描为耗时操作，接口采用 **异步任务模型 (Async Task Pattern)**：提交后立即返回 `task_id`，前端通过轮询获取进度。

### `POST /api/signals/history-check`
提交一次历史信号扫描任务。

**请求 Body:**
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-02-28",
  "symbol": "BTCUSDT",
  "interval": "1h"
}
```
*字段说明:*
- `start_date` / `end_date`: 日期字符串 (YYYY-MM-DD)，精确到日。
- `symbol`: 单选，必须来自当前系统已配置的 `active_symbols` 列表。
- `interval`: 单选，必须来自当前系统已配置的 `monitor_intervals` 键列表。

**响应 (202 Accepted):**
```json
{
  "status": "accepted",
  "task_id": "scan-uuid-abc123",
  "message": "历史信号扫描任务已启动"
}
```

**后端逻辑流:**
1. **数据采集层**: 调用币安 `GET /fapi/v1/klines` 按 `symbol` + `interval` + 日期范围拉取完整历史 K 线。
2. **策略检测层**: 全量复用 `PinbarDetector` 形态识别逻辑。
3. **MTF 趋势校验**: 若该 `interval` 在 `monitor_intervals` 中 `use_trend_filter == true`，则同步拉取对应高一级周期 K 线进行 EMA60 方向校验。
4. **动态评分层**: 全量复用当前 `ScoringWeights` 权重进行打分。
5. **持久化**: 命中信号存入数据库，`source` 字段标记为 `"history_scan"`（区别于实时监控的 `"realtime"`）。
6. **推送通知**: 扫描完成后触发飞书/企微汇总通知。

### `GET /api/signals/history-check/{task_id}`
轮询历史扫描任务的执行状态。

**响应 (200 OK) - 进行中:**
```json
{
  "task_id": "scan-uuid-abc123",
  "status": "running",
  "progress": 65,
  "message": "已扫描 650 / 1000 根K线"
}
```

**响应 (200 OK) - 已完成:**
```json
{
  "task_id": "scan-uuid-abc123",
  "status": "completed",
  "progress": 100,
  "result": {
    "total_bars_scanned": 1000,
    "signals_found": 12,
    "signals_saved": 12
  }
}
```

---

## 2.8 实时市场数据 (Market)

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

## 2.9 K 线图表数据聚合 (Chart Data)

为前端 K 线可视化模块提供融合了 OHLCV 数据与信号标记的一站式聚合接口。

### `GET /api/chart/data/{symbol}`
获取指定交易对的历史 K 线序列及对应时间段内的信号标记点。

**Path 参数:**
* `symbol` (string): 交易对，如 `BTCUSDT`

**Query 参数:**
* `interval` (string, 必填): 时间级别，如 `15m`, `1h`, `4h`, `1d`
* `limit` (int, 可选): 返回的 K 线根数，默认 `200`，最大 `1500`

**响应 (200 OK):**
```json
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "klines": [
    {
      "time": 1772323200,
      "open": 64050.00,
      "high": 64200.50,
      "low": 63980.00,
      "close": 64150.25,
      "volume": 1234.56
    }
  ],
  "markers": [
    {
      "time": 1772323200,
      "position": "belowBar",
      "color": "#22c55e",
      "shape": "arrowUp",
      "text": "LONG 85pts",
      "signal": {
        "direction": "LONG",
        "entry_price": 64050.00,
        "stop_loss": 63500.00,
        "take_profit_1": 65100.00,
        "score": 85,
        "source": "realtime"
      }
    }
  ]
}
```

**字段说明:**

| 字段 | 说明 |
|------|------|
| `klines[].time` | TradingView 规范的 **秒级** Unix 时间戳 (K 线开盘时间) |
| `markers[].time` | 与 `klines[].time` 精确对齐的秒级时间戳 |
| `markers[].position` | TradingView Marker 位置：`LONG` 信号 → `belowBar`，`SHORT` 信号 → `aboveBar` |
| `markers[].color` | `LONG` → `#22c55e` (绿)，`SHORT` → `#ef4444` (红) |
| `markers[].shape` | `LONG` → `arrowUp`，`SHORT` → `arrowDown` |
| `markers[].signal.source` | `"realtime"` 或 `"history_scan"`，供前端区分标记样式 |

**数据对齐规则:**
后端在生成 `markers` 时，必须将信号的毫秒时间戳 (`signal.timestamp`) **向下取整** 到其所属 K 线级别的开盘时间戳，然后转为秒级。对齐算法：
```
aligned_time_sec = (signal_timestamp_ms // interval_ms) * interval_ms // 1000
```
此规则确保 Marker 精准落在对应的 K 线柱上，而非落在 K 线之间的空白间隙。

**缓存策略:**
- 后端应对每个 `symbol + interval` 组合维护一份内存 LRU 缓存 (最多缓存 10 组)
- 缓存有效期设为该级别 K 线的一个周期时长 (如 `1h` → 3600秒)
- 命中缓存时仅需增量追加最新 K 线 + 重查 markers，避免重复调用 Binance `GET /fapi/v1/klines`
- 缓存未命中时走全量拉取路径，权重开销 = 5 (单次 klines 请求)

**错误响应 (400):**
```json
{
  "detail": "不支持的时间级别: 2h"
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
    "volatility_atr": false,
    "is_contrarian": false
  }
}
```

**响应 (200 OK):**
```json
{
  "status": "success"
}
```

---

## 附录 A: PinbarConfig 配置字段说明

### A.1 形态识别参数

| 字段 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `body_max_ratio` | float | 0.25 | 0.05-0.8 | 实体最大比例 (实体/全长) |
| `shadow_min_ratio` | float | 2.5 | 1.0-10.0 | 影线最小比例 (影线/实体) |
| `volatility_atr_multiplier` | float | 1.2 | 0.5-5.0 | 波幅 ATR 乘数过滤 |

### A.2 十字星优化参数 (新增)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `doji_threshold` | float | 0.05 | 十字星阈值 (实体/全长 < 5% 视为十字星) |
| `doji_shadow_bonus` | float | 0.6 | 十字星影线比例放宽系数 (2.5 × 0.6 = 1.5) |

**使用说明：**
当 K 线的 `body_ratio = body_length / total_length < doji_threshold` 时，系统视为十字星形态，
影线比例要求从 `shadow_min_ratio` 放宽至 `shadow_min_ratio × doji_shadow_bonus`。

### A.3 MTF 趋势过滤参数 (新增)

| 字段 | 类型 | 默认值 | 可选值 | 说明 |
|------|------|--------|--------|------|
| `mtf_trend_filter_mode` | string | "soft" | "soft", "hard" | 趋势过滤模式 |

**模式说明：**
- `"soft"` (推荐): 允许逆势信号，但评分时扣除 15 分
- `"hard"`: 逆势信号直接拒绝 (旧版逻辑)

### A.4 动态止损参数 (新增)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dynamic_sl_enabled` | bool | true | 是否启用动态止损阈值 |
| `dynamic_sl_base` | float | 0.035 | 动态止损基准值 (3.5%) |
| `dynamic_sl_atr_multiplier` | float | 0.5 | ATR 对止损的贡献系数 |

**计算公式：**
```
effective_max_sl_dist = dynamic_sl_base + (atr14 / entry_price) × dynamic_sl_atr_multiplier
上限 = max_sl_dist × 1.5
```

**行为说明：**
- 高波动市场：ATR 上升，止损阈值自动放宽，避免优质信号被过滤
- 低波动市场：ATR 下降，止损阈值收紧，保持风控严格性

---

## 附录 B: Signal 信号字段说明

### B.1 基础字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 交易对，如 `BTCUSDT` |
| `interval` | string | 时间级别，如 `15m`, `1h`, `4h`, `1d` |
| `direction` | string | "LONG" (做多) 或 "SHORT" (做空) |
| `entry_price` | float | 建议入场价格 |
| `stop_loss` | float | 绝对止损价格 |
| `take_profit_1` | float | 第一止盈价格 (1.5R 盈亏比) |
| `timestamp` | int | 信号触发时间戳 (毫秒) |
| `reason` | string | 信号触发原因，如 `Pinbar+EMA60` |
| `sl_distance_pct` | float | 止损距离百分比 |

### B.2 评分字段

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| `score` | int | 0-100 | 系统加权综合得分 |
| `score_details.shape` | float | 0-100 | 形态完美度得分 |
| `score_details.trend` | float | 0-100 | 趋势顺应度得分 |
| `score_details.vol` | float | 0-100 | 波动爆发得分 |

### B.3 分析指标

| 字段 | 类型 | 说明 |
|------|------|------|
| `shadow_ratio` | float | 影线占比 (主方向影线 / 实体) |
| `ema_distance` | float | 价格与 EMA60 的偏离比率 (%) |
| `volatility_atr` | float | 当前 K 线总波幅 / ATR(14) 倍数 |

### B.4 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 信号来源：`"realtime"` (实时监控) 或 `"history_scan"` (历史回扫) |
| `is_contrarian` | bool | 是否为逆势信号 (仅在 `mtf_trend_filter_mode="soft"` 模式下可能为 true) |

**`is_contrarian` 字段说明：**
- `false`: 顺大势信号，价格方向与 MTF 高级别趋势一致
- `true`: 逆大势信号，评分已扣除 15 分，前端可考虑用特殊样式标记

---

## 附录 C: 错误响应规范

### C.1 标准错误格式

```json
{
  "detail": "错误描述信息"
}
```

### C.2 常见错误码

| HTTP 状态码 | 场景 |
|-------------|------|
| 400 | 请求参数非法 (如日期格式错误、权重和不等于 1.0) |
| 401 / 403 | 币安 API Key 无效或权限不足 |
| 404 | 资源不存在 (如任务 ID 不存在) |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 (如历史扫描服务未初始化) |
