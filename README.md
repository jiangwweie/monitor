# monitor - 加密货币信号监测系统

![Project Status](https://img.shields.io/badge/status-active-brightgreen)
![Tech Stack](https://img.shields.io/badge/tech-Python%20%7C%20FastAPI%20%7C%20React-blue)
![License](https://img.shields.io/badge/policy-Zero%20Execution-red)

`monitor` 是一款专为加密货币交易者设计的、采用 Apple 极简主义设计风格的全栈监控与信号雷达系统。本系统基于"纯信号监测"原则，通过高频数据处理、多重时间框架（MTF）校验及动态权重评分逻辑，为交易决策提供精准的只读辅助。

---

## 核心设计理念

- **安全至上 (Zero Execution Policy)**：系统在底层彻底隔离了下单执行逻辑。`auto_order_status` 开关被硬编码锁定为 `OFF`，无论在 API 还是 UI 层面均不可篡改，确保系统仅作为信号观测与风控评估工具，绝不触碰真实资金执行。
- **动态加权评分 (Dynamic Scoring)**：采用形态 ($S_{shape}$)、趋势 ($S_{trend}$)、波动 ($S_{vol}$) 三位一体评分模型。用户可根据市场阶段实时调整权重比例。
- **多重时间框架 (MTF) 降噪**：内置高优先级趋势过滤逻辑。例如：15min 级别的信号必须符合 1h 级别的大趋势方向方可触发通过。
- **信号质量分级**：A/B/C 三级分类，精品信号高亮推送，普通信号正常推送，观察信号仅记录。

---

## 核心功能模块

### 1. 仪表盘 (Dashboard) - 全局指挥中心
- **系统遥测**：WebSocket 实时心跳监控、API 延迟以及系统运行时间 (Uptime)。
- **API 权重卫士**：实时监控币安 API 消耗百分比，配合每分钟重置机制，有效规避高频请求导致的 IP 封禁。
- **资产透视**：展示账户总资金、可用保证金及**总计未实现盈亏**。支持多币种实时价格轮播。

### 2. 信号雷达 (Signal Radar) - 高密决策矩阵
- **信号扫描池**：直观展示时间、级别 (15m/1h/4h/1d)、币种、方向及综合评分。
- **高级过滤与检索**：支持按币种、方向、时间窗口、分值线进行极速筛选；提供批量管理与记录清理功能。
- **细节深挖**：点击详情可穿透查看影线占比、EMA 距离、ATR 波动率等底层计算指标及 MTF 趋势校验状态。
- **历史回扫**：支持对指定时间段进行历史信号回测扫描，验证策略有效性。

### 3. 实盘持仓管理 (User Positions)
- **精细化持仓看板**：提供独立的持仓 Tab，展示各币种的开单时间、持仓状态、未实现盈亏及仓位价值。
- **订单联动状态**：实时关联显示底层挂载的止盈价格/单号、止损价格/单号。

### 4. 系统热配置 (Settings)
- **多通道推送网关**：并行支持飞书机器人、企业微信 Webhook 通知，具备全局推送开关。
- **策略参数动态调整**：支持监控币对的无限拓扑添加，以及评分权重的阻尼条式联动调整。
- **风控配置**：单笔风险比例、最大止损距离、杠杆上限、持仓数量上限。

---

## 技术架构

### 后端 (Infrastructure & Domain)
- **核心语言**：Python 3.10+
- **Web 框架**：FastAPI (异步高性能)
- **设计模式**：Clean Architecture / DDD (领域驱动设计)
- **数据持久化**：SQLite (轻量级本地存储，WAL 模式)
- **外部集成**：Binance API (K 线 WebSocket + REST)

### 前端 (Command Center)
- **框架**：React 19 + TypeScript
- **构建工具**：Vite
- **UI 组件库**：Shadcn UI + Radix UI + Tailwind CSS
- **设计风格**：Apple-Style Minimalist (半透明毛玻璃、丝滑动画、微交互)

### 架构分层
```
core/           # 最内层：实体、接口、异常（无外部依赖）
domain/         # 领域层：策略引擎、风控计算（纯业务逻辑）
application/    # 应用层：引擎编排、服务调度
infrastructure/ # 基础设施层：外部适配器、持久化、通知
web/            # Web 层：FastAPI 路由
web_ui/         # 前端：React SPA
```

---

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 确保宿主机目录存在
mkdir -p /Users/jiangwei/Documents/docker/monitor/{data,logs,config}

# 2. 构建并启动
cd monitor
docker-compose up --build -d

# 3. 查看日志
docker logs -f cryptoradar-backend
docker logs -f cryptoradar-frontend

# 4. 访问应用
# 前端：http://localhost:5174
# 后端 API：http://localhost:8000
# API 文档：http://localhost:8000/docs

# 5. 停止服务
docker-compose down
```

所有数据持久化到宿主机目录 `/Users/jiangwei/Documents/docker/monitor/`：
- `data/radar.db` - SQLite 数据库
- `logs/backend.log` - 应用日志
- `config/` - 配置文件导入/导出
- `.env` - 环境变量

### 方式二：本地开发环境

#### 准备工作
请确保已安装 Python 3.10+ 和 Node.js 18+。

#### 步骤 1：后端环境配置
```bash
# 进入项目目录
cd monitor

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt
```

#### 步骤 2：前端环境配置
```bash
cd web_ui
npm install
npm run dev
```

#### 步骤 3：启动系统
```bash
# 运行主程序
python main.py
```

---

## 项目结构

```text
monitor/
├── core/               # 领域实体与模型 (Entities, Interfaces, Exceptions)
├── domain/             # 业务逻辑与策略引擎 (Strategy, Risk, Services)
│   ├── strategy/       # Pinbar 策略、评分引擎、指标计算
│   └── risk/           # 仓位计算、组合风险
├── application/        # 应用编排 (Monitor Engine, History Scanner)
├── infrastructure/     # 基础设施 (Feed, Repo, Notify, Reader)
├── web/                # FastAPI 路由与接口
├── web_ui/             # React 前端项目
├── scripts/            # 维护脚本与测试工具
├── tests/              # 单元测试与集成测试
├── config/             # Docker、Nginx 配置文件
├── docs/               # 项目文档
│   ├── 项目结构说明.md
│   ├── Pinbar 策略详细设计.md
│   ├── 风控模块详细设计.md
│   └── 代码改进建议.md
├── logs/               # 运行日志
├── main.py             # 系统入口
├── requirements.txt    # Python 依赖
└── README.md           # 项目说明
```

---

## 策略说明

### Pinbar 形态识别

Pinbar（Pinocchio Bar）是一种经典的反转形态，特征为：
- **小实体**：开盘价与收盘价接近
- **长影线**：一侧影线显著长于另一侧
- **拒绝价格**：长影线表示价格在该方向被强烈拒绝

系统结合以下过滤条件提高信号质量：
1. **EMA60 趋势过滤**：只做顺势信号，逆势信号降分处理
2. **ATR 波动率过滤**：K 线波幅需达到 ATR 的 1.2 倍以上
3. **MTF 趋势校验**：小级别信号需符合大级别趋势方向
4. **动态止损**：基于 ATR 波动率自适应调整止损阈值

### 信号质量分级

| 等级 | 要求 | 推送策略 |
|------|------|----------|
| A 级 | 各项指标优秀 | 立即推送 + 高亮标记 |
| B 级 | 达到基准要求 | 正常推送 |
| C 级 | 边缘信号 | 仅记录入库，不推送 |

### 风控算仓逻辑

系统采用严格的风险控制机制：
1. **固定比例风险**：单笔交易风险不超过账户总额的 2%
2. **平均资金分配**：每笔交易最多占用 1/max_positions 资金
3. **杠杆熔断**：理论杠杆超过上限时自动压缩仓位
4. **组合风险聚合**：监控所有持仓的总风险敞口
5. **安全垫设计**：计算时预留 15% 的安全边际

---

## 文档索引

- [项目结构说明](docs/项目结构说明.md) - 详细的目录结构和模块说明
- [Pinbar 策略详细设计](docs/Pinbar 策略详细设计.md) - 策略逻辑、评分算法、配置参数
- [风控模块详细设计](docs/风控模块详细设计.md) - 仓位计算、风险聚合、熔断机制
- [代码改进建议](docs/代码改进建议.md) - 各模块的优化建议

---

## API 使用示例

### 获取信号列表
```bash
# 基本查询
curl http://localhost:8000/api/signals

# 分页查询
curl "http://localhost:8000/api/signals?page=1&size=20"

# 过滤查询
curl "http://localhost:8000/api/signals?symbols=ETHUSDT,BTCUSDT&directions=LONG&min_score=60"
```

### 创建历史扫描任务
```bash
curl -X POST http://localhost:8000/api/history/scan \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETHUSDT",
    "interval": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-03-01"
  }'
```

### 配置导入/导出
```bash
# 导出配置为 YAML
curl -X POST http://localhost:8000/api/config/export

# 从 YAML 导入配置
curl -X POST http://localhost:8000/api/config/import \
  -F "file=@config/exported_config_*.yaml"
```

**注意**：导出配置时，敏感信息（币安 API Key/Secret、飞书/企微 Webhook URL）会被置空，确保配置文件可以安全分享。

---

## 配置说明

### 环境变量 (.env)

```bash
# 币安 API 配置
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# 推送配置
FEISHU_WEBHOOK_URL=your_feishu_webhook
WECOM_WEBHOOK_URL=your_wecom_webhook

# 服务配置
BACKEND_PORT=8000
DB_DIR=.
LOG_DIR=logs
```

### 风控配置（可在前端热更新）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `risk_pct` | 0.02 (2%) | 单笔最大风险百分比 |
| `max_sl_dist` | 0.035 (3.5%) | 最大止损距离 |
| `max_leverage` | 20.0x | 杠杆上限 |
| `max_positions` | 4 | 最大持仓数量 |

---

## 常见问题

### WebSocket 频繁断开

**症状**：日志中出现大量 "Binance WebSocket 连接断开"

**解决方案**：
1. 检查网络连接稳定性
2. 检查防火墙是否阻止 WebSocket 连接
3. 确认 API 权重未超限
4. 系统会自动重连，等待片刻即可

### 信号未推送

**症状**：发现信号但没有收到通知

**排查步骤**：
1. 检查全局推送开关是否开启：前端 Settings → 推送配置
2. 检查飞书/企微 Webhook URL 是否正确配置
3. 确认信号质量等级（C 级信号不推送）
4. 查看后端日志 `logs/backend.log`

### 数据库锁定

**症状**：日志中出现 "database is locked"

**解决方案**：
1. 确认没有其他进程访问数据库
2. 检查 WAL 模式是否启用（系统默认启用）
3. 重启后端服务释放锁定的连接

---

## 安全提醒

⚠️ **重要提醒**：

1. 本系统仅为信号监测工具，**不提供任何交易执行功能**
2. 加密货币交易存在高风险，请谨慎评估自身风险承受能力
3. 请妥善保管币安 API Key，**不要开启提现和交易权限**
4. 系统配置的风险参数仅供参考，请根据自身情况调整
5. 历史回测结果不代表未来表现，请勿过度依赖

---

## 更新日志

### v1.2.0 (2024-03-10)

**新增**
- 支持信号质量分级（A/B/C 三级）
- 添加动态止损阈值（基于 ATR 波动率）
- 新增 MTF 趋势过滤软模式

**修复**
- 修复 Binance API 时间戳同步问题
- 修复风控配置属性访问错误
- 修复历史扫描与实时监控写入冲突（启用 WAL 模式）

**优化**
- 优化信号检测流程，减少重复计算
- 优化通知推送并发性能
- 优化冷启动预热（预加载 100 根历史 K 线）

### v1.1.0 (2024-02-15)

**新增**
- 添加历史信号扫描功能
- 支持配置导入导出
- 新增持仓详情查询接口
- 新增 K 线图表可视化

---

## 技术栈总览

| 模块 | 技术选型 |
|------|----------|
| 后端语言 | Python 3.10+ |
| Web 框架 | FastAPI (异步) |
| 数据库 | SQLite (WAL 模式) |
| 前端框架 | React 19 + TypeScript |
| UI 组件 | Shadcn UI + Tailwind CSS |
| 构建工具 | Vite |
| 图表库 | Lightweight Charts v5 |
| 外部 API | Binance Futures (WS + REST) |
| 部署方式 | Docker + Docker Compose |

---

*Powered by Antigravity Architect - 2026*
