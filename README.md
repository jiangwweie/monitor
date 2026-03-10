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

### 3. 实盘持仓管理 (User Positions)
- **精细化持仓看板**：提供独立的持仓 Tab，展示各币种的开单时间、持仓状态、未实现盈亏及仓位价值。
- **订单联动状态**：实时关联显示底层挂载的止盈价格/单号、止损价格/单号。

### 4. 系统热配置 (Settings)
- **多通道推送网关**：并行支持飞书机器人、企业微信 Webhook 通知，具备全局推送开关。
- **策略参数动态调整**：支持监控币对的无限拓扑添加，以及评分权重的阻尼条式联动调整。

---

## 技术架构

### 后端 (Infrastructure & Domain)
- **核心语言**：Python 3.10+
- **Web 框架**：FastAPI (异步高性能)
- **设计模式**：Clean Architecture / DDD (领域驱动设计)
- **数据持久化**：SQLite (轻量级本地存储)
- **外部集成**：Binance API (K 线、账户、持仓)

### 前端 (Command Center)
- **框架**：React 18 + TypeScript
- **构建工具**：Vite
- **UI 组件库**：Shadcn UI + Radix UI + Tailwind CSS
- **设计风格**：Apple-Style Minimalist (半透明毛玻璃、丝滑动画、微交互)

---

## 快速开始

### 方式一：Docker 部署（推荐）

#### A. 使用初始化脚本（推荐）

```bash
# 1. 运行初始化脚本（自动创建目录和配置文件）
./config/docker-init.sh

# 2. 编辑配置文件，填入币安 API 密钥
vi /Users/jiangwei/Documents/docker/monitor/.env

# 3. 启动服务
cd config
docker-compose up --build -d

# 4. 查看状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f
```

#### B. 手动部署

```bash
# 1. 确保宿主机目录存在
mkdir -p /Users/jiangwei/Documents/docker/monitor/{data,logs,config}

# 2. 复制并编辑配置文件
cp config/.env.example /Users/jiangwei/Documents/docker/monitor/.env
# 编辑 .env 填入币安 API 密钥

# 3. 启动服务
cd config
docker-compose up --build -d
```

#### 访问应用

- 前端地址：http://localhost:5174（或配置的 `FRONTEND_PORT`）
- 后端 API：http://localhost:8000（或配置的 `BACKEND_PORT`）
- API 文档：http://localhost:8000/docs

#### 停止服务

```bash
docker-compose down
```

#### 自定义端口

编辑 `/Users/jiangwei/Documents/docker/monitor/.env`：
```bash
BACKEND_PORT=9000      # 后端端口
FRONTEND_PORT=5176     # 前端端口
```

#### 数据持久化

所有数据持久化到宿主机目录 `/Users/jiangwei/Documents/docker/monitor/`：
- `data/radar.db` - SQLite 数据库
- `logs/backend.log` - 应用日志
- `.env` - 环境变量配置文件

详细 Docker 部署说明请参考 [config/README.Docker.md](config/README.Docker.md)

---

### 方式二：本地开发环境

#### 准备工作
请确保已安装 Python 3.10+ 和 Node.js 18+。

#### 步骤 1：创建配置文件

```bash
# 复制配置文件模板
cp .env.example .env

# 编辑 .env 填入币安 API 密钥
vi .env
```

#### 步骤 2：后端环境配置

```bash
# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt

# 启动后端（使用 scripts/start.sh 或直接运行）
./scripts/start.sh
# 或
python main.py
```

#### 步骤 3：前端环境配置

```bash
cd web_ui
npm install
npm run dev
```

#### 访问应用

- 前端地址：http://localhost:5173（或配置的 `FRONTEND_PORT`）
- 后端 API：http://localhost:8000（或配置的 `BACKEND_PORT`）
- API 文档：http://localhost:8000/docs

#### 使用启动/停止脚本

```bash
# 启动系统
./scripts/start.sh

# 停止系统
./scripts/stop.sh
```

---

## 项目结构

```text
monitor/
├── .env.example              # 环境变量配置模板
├── .env                      # 环境变量配置（本地开发）
├── scripts/
│   ├── start.sh              # 启动脚本
│   ├── stop.sh               # 停止脚本
│   └── migrate_secrets.py    # 数据库迁移脚本
├── config/
│   ├── .env.example          # Docker 配置模板
│   ├── docker-compose.yaml   # Docker 编排配置
│   ├── Dockerfile.backend    # 后端 Docker 镜像
│   ├── Dockerfile.frontend   # 前端 Docker 镜像
│   ├── nginx.conf            # Nginx 配置
│   ├── docker-init.sh        # Docker 初始化脚本
│   └── README.Docker.md      # Docker 部署指南
├── core/                     # 领域实体与模型 (Entities)
├── domain/                   # 业务逻辑与策略引擎 (Strategy, Risk)
├── infrastructure/           # 基础设施层 (API Client, DB Repo, Notify)
│   └── config/
│       └── env_loader.py     # 环境变量加载模块
├── application/              # 应用层（引擎、服务）
├── web/                      # 后端路由与 Web 接口 (API Endpoints)
├── web_ui/                   # 前端 React 项目
└── docs/                     # 系统设计文档与 API 契约
```

---

## 配置说明

### 私密配置（从 .env 文件读取）

以下配置从项目根目录的 `.env` 文件（本地开发）或 `/Users/jiangwei/Documents/docker/monitor/.env`（Docker 部署）读取：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BINANCE_API_KEY` | 币安 API Key（必填） | - |
| `BINANCE_API_SECRET` | 币安 API Secret（必填） | - |
| `GLOBAL_PUSH_ENABLED` | 全局推送开关 | true |
| `FEISHU_ENABLED` | 飞书推送开关 | false |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook 地址 | - |
| `WECOM_ENABLED` | 企业微信推送开关 | false |
| `WECOM_WEBHOOK_URL` | 企业微信 Webhook 地址 | - |
| `BACKEND_PORT` | 后端端口 | 8000 |
| `FRONTEND_PORT` | 前端端口 | 5173 |

### 可界面配置项

以下配置可通过前端设置页面修改：

- 监控币种列表
- 监控周期（15m/1h/4h/1d）
- Pinbar 形态参数
- 风控参数（杠杆、止损距离）
- 评分权重配置

---

## Docker 部署

详细 Docker 部署说明请参考 [config/README.Docker.md](config/README.Docker.md)

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

*Powered by Antigravity Architect - 2026*
