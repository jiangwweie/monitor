### 第一阶段：脚手架与核心契约搭建 (The Skeleton)

**目标**：把项目的骨架搭好，定义好所有模块之间交流的“通用语言”。

- **Task 1.1: 初始化项目与配置体系**
  - 创建标准目录树（`core`, `domain`, `infrastructure`, `application`, `web`）。
  - 编写 `.env.example` 和 `config/settings.py`，管理全局静态环境变量。
  - 配置全局异步日志器 (`logging`)，确保所有模块输出统一格式的日志。
- **Task 1.2: 定义核心数据实体 (Entities)**
  - 编写 `core/entities.py`。
  - 实现轻量级的 `@dataclass`：`Bar` (K线), `Signal` (信号), `AccountInfo` (账户快照), `SizingRecommendation` (算仓建议)。
- **Task 1.3: 定义抽象接口契约 (Interfaces)**
  - 编写 `core/interfaces.py`。
  - 使用 `abc.ABC` 定义底层的抽象基类：`IDataFeed`, `IAccountReader`, `INotifier`, `IRepository`。

### 🟡 第二阶段：持久化与动态配置中心 (The Nervous System)

**目标**：让系统具备记忆能力，并支持在不重启的情况下热修改风控参数。

- **Task 2.1: 数据库表结构设计与初始化**
  - 编写 `infrastructure/db/schema.sql`，定义 `app_configs` (配置表) 和 `signals` (信号历史表)。
- **Task 2.2: 实现异步 SQLite 仓储 (Repository)**
  - 编写 `infrastructure/db/sqlite_repo.py`。
  - 实现基于 `aiosqlite` 的读写方法，特别是配置表的热更新 (`UPSERT`) 逻辑。
- **Task 2.3: 编写 Pydantic 配置模型**
  - 编写 `config/schemas.py`，严格定义 `RiskConfig` 和 `SystemConfig` 的取值边界 (使用 `Field(ge=..., le=...)`)。
- **Task 2.4: 搭建 Web API 控制台**
  - 编写 `web/api.py`。
  - 使用 FastAPI 实现 `GET /api/config` 和 `PUT /api/config`，供前端读取和修改 SQLite 中的参数。

### 🟠 第三阶段：策略与风控大脑 (The Brain)

**目标**：纯粹的数学与逻辑计算，完全不依赖外部网络，方便极速单元测试。

- **Task 3.1: 基础指标库封装**
  - 编写 `domain/strategy/indicators.py`。
  - 实现高效的 EMA (指数移动平均) 和 ATR (真实波幅) 计算逻辑。
- **Task 3.2: Pinbar 形态与规则引擎**
  - 编写 `domain/strategy/pinbar.py`。
  - 实现多重漏斗过滤：趋势判定 (价格与EMA60关系) -> 形态判定 (影线与实体比例) -> 波幅异常判定 (过滤天地针)。
- **Task 3.3: 只读风控算仓器 (Position Sizer)**
  - 编写 `domain/risk/sizer.py`。
  - 实现核心数学模型：根据当前余额、4-n 持仓逻辑、Pinbar 止损距离，推算出安全的 **建议杠杆** 与 **建议数量**。

### 🔵 第四阶段：基础设施适配器 (The Eyes & Hands)

**目标**：与币安服务器和本地系统进行物理交互（严格保持只读）。

- **Task 4.1: WebSocket 行情数据源**
  - 编写 `infrastructure/feed/binance_ws.py`。
  - 连接币安 WSS 接口，监听 15m K 线，组装闭合 K 线并生成 `Bar` 实体流。包含断线自动重连逻辑。
- **Task 4.2: 币安只读账户读取器**
  - 编写 `infrastructure/reader/binance_api.py`。
  - 封装 HTTP GET 请求，附带签名逻辑，仅调用 `/fapi/v2/account` 获取可用余额和钱包总额。

### 🟣 第五阶段：并发推送模块 (The Mouth)

**目标**：将计算好的决策卡片，稳定、快速地广播给你的手机或团队。

- **Task 5.1: 实现单一渠道推送器**
  - 编写 `infrastructure/notify/feishu.py` (飞书 Markdown 卡片)。
  - 编写 `infrastructure/notify/telegram.py` (TG 消息)。
- **Task 5.2: 实现并发广播器 (Broadcaster)**
  - 编写 `infrastructure/notify/broadcaster.py`。
  - 使用组合模式管理多个渠道，利用 `asyncio.gather` 并发发送，确保单个渠道超时不引发系统雪崩。

### 🔴 第六阶段：引擎调度与系统启动 (The Commander)

**目标**：把前面所有的零件拼装起来，按下启动按钮。

- **Task 6.1: 编写主监听引擎 (Monitor Engine)**
  - 编写 `application/monitor_engine.py`。
  - 串联业务流：接收 K 线 -> 拉取动态配置 -> 触发策略算信号 -> 触发风控算仓位 -> 异步存入数据库 -> 触发广播器推送。
- **Task 6.2: 依赖注入与入口组装**
  - 编写根目录的 `main.py`。
  - 实例化所有基础设施对象，组装主引擎，同时启动 FastAPI Web 服务和后台 K 线监听任务。