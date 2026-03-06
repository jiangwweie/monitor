# 信号雷达系统重构技术文档

## 一、需求概述

### 核心目标
1. **按需加载** - 各页面仅加载必要数据，减少首屏加载时间
2. **查询体验优化** - 信号列表支持条件查询、分页、批量操作
3. **持仓实时刷新** - 用户持仓页支持手动刷新
4. **仪表盘数据重构** - 按新业务需求调整展示字段

---

## 二、架构设计（DDD 理念）

### 分层结构
```
core/           # 核心实体层 - 纯数据载体，无业务逻辑
  entities.py   # Signal, Bar, PositionSizing 等实体
  interfaces.py # 仓储、通知器等抽象接口

domain/         # 领域层 - 纯业务逻辑，无 I/O
  strategy/     # PinbarStrategy, 信号评分逻辑
  risk/         # PositionSizer, 仓位计算逻辑
  service/      # 领域服务（如信号查询服务）

application/    # 应用层 - 编排协调，用例驱动
  monitor_engine.py   # 实时监控引擎
  history_scanner.py  # 历史扫描引擎
  signal_query_service.py  # 【新增】信号查询服务
  position_service.py    # 【新增】持仓查询服务

infrastructure/ # 基础设施层 - 外部适配器
  repo/         # SQLite 仓储实现
  feed/         # Binance 数据源
  notify/       # 推送通知

web/            # 接口适配层 - REST API / WebSocket
  api.py        # FastAPI 路由
```

### DDD 原则遵守
- **依赖倒置**：外层依赖内层接口，内层不感知外层
- **贫血模型**：实体仅含数据，业务逻辑在领域层
- **聚合根**：Signal、Position 作为聚合根，通过仓储访问
- **用例驱动**：应用层每个服务对应一个业务用例

---

## 三、功能拆分

### 任务 1：后端 - 信号列表分页与查询 API（应用层 + 接口层）

#### 1.1 新增 `SignalQueryService`（应用层）
**文件**: `application/signal_query_service.py`

**职责**: 封装信号查询的业务逻辑，处理分页、筛选、排序

```python
class SignalQueryService:
    def __init__(self, repo: IRepository):
        self.repo = repo

    async def query_signals(
        self,
        symbols: List[str] = None,
        intervals: List[str] = None,
        directions: List[str] = None,
        start_time: int = None,
        end_time: int = None,
        min_score: int = None,
        quality_tier: str = None,
        page: int = 1,
        size: int = 20,
        sort_by: str = "timestamp",
        order: str = "desc"
    ) -> PaginatedResult[Signal]:
        """分页查询信号"""
```

#### 1.2 仓储层扩展
**文件**: `infrastructure/repo/sqlite_repo.py`

**新增方法**:
```python
async def query_signals(
    self,
    filter: SignalFilter,
    page: int = 1,
    size: int = 20,
    sort_by: str = "timestamp",
    order: str = "desc"
) -> Tuple[List[Signal], int]:
    """返回 (信号列表，总数)"""
```

#### 1.3 API 路由改造
**文件**: `web/api.py`

**改动点**:
```python
@app.get("/api/signals")
async def get_signals(
    request: Request,
    symbols: Optional[str] = None,
    intervals: Optional[str] = None,
    directions: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    min_score: Optional[int] = None,
    quality_tier: Optional[str] = None,
    page: Optional[int] = 1,
    size: Optional[int] = 20,
    sort_by: Optional[str] = "timestamp",
    order: Optional[str] = "desc"
):
    # 使用 SignalQueryService 而非直接调用 repo
    service = request.app.state.signal_query_service
    result = await service.query_signals(...)
    return {
        "items": [signal.to_dict() for signal in result.items],
        "total": result.total,
        "page": page,
        "size": size
    }
```

---

### 任务 2：后端 - 持仓实时刷新 API（应用层 + 接口层）

#### 2.1 新增 `PositionService`（应用层）
**文件**: `application/position_service.py`

```python
class PositionService:
    def __init__(self, account_reader: IAccountReader, repo: IRepository):
        self.account_reader = account_reader
        self.repo = repo

    async def refresh_positions(self) -> List[Position]:
        """实时获取活跃持仓"""

    async def get_wallet_balance(self) -> float:
        """获取钱包余额（初始保证金）"""

    async def get_unrealized_pnl(self) -> float:
        """获取总计未实现盈亏"""
```

#### 2.2 新增 API 端点
**文件**: `web/api.py`

```python
@app.get("/api/positions/refresh")
async def refresh_positions(request: Request):
    """实时刷新持仓"""
    service = request.app.state.position_service
    positions = await service.refresh_positions()
    return {"positions": [p.to_dict() for p in positions]}

@app.get("/api/account/wallet-balance")
async def get_wallet_balance(request: Request):
    """获取钱包余额"""
    service = request.app.state.position_service
    balance = await service.get_wallet_balance()
    return {"wallet_balance": balance}
```

---

### 任务 3：后端 - 仪表盘数据重构（接口层）

#### 3.1 改造 `/api/account/dashboard` 返回值
**文件**: `web/api.py`

**旧结构**:
```json
{
  "total_wallet_balance": 10000,
  "available_balance": 8000,
  "total_unrealized_pnl": 500,
  "current_positions_count": 3,
  "positions": [...]
}
```

**新结构**:
```json
{
  "wallet_balance": 10000,        // 钱包余额（初始保证金）
  "total_unrealized_pnl": 500,    // 总计未实现盈亏
  "margin_balance": 10500,        // 保证金余额 = 钱包 + 未实现盈亏
  "current_positions_count": 3,
  "positions": [...]
}
```

---

### 任务 4：前端 - 按需加载架构（表现层）

#### 4.1 App.tsx 改造
**文件**: `web_ui/src/App.tsx`

**改动点**:
- 移除全局轮询 `dashboardData` 和 `signals`
- 各页面组件自行管理数据加载
- 通过回调传递刷新触发器

```tsx
// 移除全局的 signals 状态
// 移除全局的 dashboardData 轮询（保留 systemStatus 用于健康监控）

<SignalRadar
  onSignalsLoad={handleSignalsLoad}  // 按需加载
/>
<Dashboard
  onDashboardLoad={handleDashboardLoad}  // 按需加载
/>
<Positions
  refreshTrigger={positionRefreshTrigger}
  onPositionsLoad={handlePositionsLoad}
/>
```

#### 4.2 信号列表页改造
**文件**: `web_ui/src/components/SignalRadar.tsx`

**改动点**:
1. 移除自动查询，改为点击查询按钮触发
2. 添加分页状态管理
3. 查询条件与查询动作解耦

```tsx
const [signals, setSignals] = useState([]);
const [pagination, setPagination] = useState({ page: 1, size: 20, total: 0 });
const [filters, setFilters] = useState({ ... });  // 查询条件
const [queryTrigger, setQueryTrigger] = useState(0);  // 查询触发器

// 查询条件变更时不触发请求，仅更新 filters
const handleFilterChange = (key, value) => {
  setFilters(prev => ({ ...prev, [key]: value }));
};

// 点击查询按钮时触发
const handleQuery = () => {
  setQueryTrigger(prev => prev + 1);
};

// 监听触发器变化执行查询
useEffect(() => {
  if (queryTrigger > 0) {
    fetchSignals(filters, pagination.page, pagination.size);
  }
}, [queryTrigger]);

// 分页变更
const handlePageChange = (page) => {
  setPagination(prev => ({ ...prev, page }));
  setQueryTrigger(prev => prev + 1);
};

const handleSizeChange = (size) => {
  setPagination(prev => ({ ...prev, size, page: 1 }));
  setQueryTrigger(prev => prev + 1);
};
```

#### 4.3 持仓页改造
**文件**: `web_ui/src/components/Positions.tsx`

**改动点**:
- 添加刷新按钮
- 支持外部触发刷新

```tsx
const [positions, setPositions] = useState([]);
const [refreshTrigger, setRefreshTrigger] = useState(0);

// 监听刷新触发
useEffect(() => {
  if (refreshTrigger > 0) {
    fetchPositions();
  }
}, [refreshTrigger]);

// 手动刷新按钮
<Button onClick={() => setRefreshTrigger(prev => prev + 1)}>
  <RefreshCw /> 刷新
</Button>
```

#### 4.4 仪表盘改造
**文件**: `web_ui/src/components/Dashboard.tsx`

**改动点**:
- 调整账户数据展示结构

```tsx
// 新字段映射
const { wallet_balance, total_unrealized_pnl, margin_balance } = dashboardData;

<Card>
  <div>钱包余额（初始保证金）</div>
  <div>${wallet_balance.toFixed(2)}</div>

  <div>总计未实现盈亏</div>
  <div className={total_unrealized_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}>
    ${total_unrealized_pnl.toFixed(2)}
  </div>

  <div>保证金余额</div>
  <div>${margin_balance.toFixed(2)}</div>
</Card>
```

---

## 四、接口定义

### 4.1 信号查询 API
```
GET /api/signals
Query Params:
  - symbols: string (可选，逗号分隔)
  - intervals: string (可选)
  - directions: string (可选)
  - start_time: number (可选，时间戳毫秒)
  - end_time: number (可选)
  - min_score: number (可选)
  - quality_tier: string (可选，A/B/C)
  - page: number (默认 1)
  - size: number (默认 20)
  - sort_by: string (默认 timestamp)
  - order: string (默认 desc)

Response:
{
  "items": Signal[],
  "total": number,
  "page": number,
  "size": number
}
```

### 4.2 持仓刷新 API
```
GET /api/positions/refresh

Response:
{
  "positions": Position[]
}
```

### 4.3 钱包余额 API
```
GET /api/account/wallet-balance

Response:
{
  "wallet_balance": number
}
```

### 4.4 仪表盘数据 API（改造后）
```
GET /api/account/dashboard

Response:
{
  "wallet_balance": number,
  "total_unrealized_pnl": number,
  "margin_balance": number,
  "current_positions_count": number,
  "positions": Position[]
}
```

---

## 五、验收标准

### 后端验收
- [ ] `SignalQueryService` 单元测试通过率 100%
- [ ] 分页查询返回正确的 `total` 总数
- [ ] 默认查询条件（page=1, size=20）生效
- [ ] `/api/positions/refresh` 返回实时持仓
- [ ] `/api/account/dashboard` 返回新字段结构
- [ ] DDD 分层清晰，应用层不直接访问 repo

### 前端验收
- [ ] 首页不自动加载信号列表
- [ ] 信号列表页初始不请求，点击查询后请求
- [ ] 分页组件正常工作（翻页、改变页大小）
- [ ] 持仓页刷新按钮触发实时查询
- [ ] 仪表盘展示新字段（钱包余额、未实现盈亏、保证金余额）
- [ ] 各页面数据独立，无全局耦合

---

## 六、改进建议（审查阶段关注）

### 代码质量
1. **类型安全**：前端使用 TypeScript Interface 定义 API 响应结构
2. **错误处理**：统一错误处理中间件，避免重复 try-catch
3. **加载状态**：每个异步操作有明确的 loading 状态
4. **防抖处理**：查询按钮防止重复点击

### DDD 合规性
1. **领域纯净**：domain 层无任何 I/O、async 操作
2. **仓储抽象**：应用层依赖接口而非实现
3. **实体行为**：考虑将部分逻辑移入实体（如 Signal.scoreDisplay()）
4. **领域事件**：考虑引入事件总线解耦信号产生与通知

### 性能优化
1. **缓存策略**：配置数据使用 React Query 缓存
2. **虚拟滚动**：信号列表超 100 条时启用虚拟滚动
3. **WebSocket**：实时价格改用 WebSocket 推送
4. **并发请求**：仪表盘多个数据源使用 Promise.all

---

## 七、并行执行任务分配

### 前端窗口任务
**提示词**：见单独文档 `frontend_tasks.md`

### 后端窗口任务
**提示词**：见单独文档 `backend_tasks.md`

---

## 八、联调流程

1. 后端完成 API 改造，输出 Swagger 文档
2. 前端完成 UI 改造，使用 Mock 数据
3. 前后端对接 API，验证数据格式
4. 端到端测试所有用例
5. 代码审查，提出改进建议
6. 整改后重新验收
