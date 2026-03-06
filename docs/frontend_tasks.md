# 前端重构任务提示词

## 任务说明

你负责前端界面重构工作。请按照 DDD 理念和按需加载原则完成以下任务。

## 任务列表

### 任务 1：信号列表页查询功能改造

**文件**: `web_ui/src/components/SignalRadar.tsx`

**需求**:
1. 查询条件与查询动作解耦 - 改变筛选条件时不触发请求
2. 点击"查询"按钮才发起后端请求
3. 支持分页（默认 20 条/页）
4. 提供分页组件（页数选择、单页大小选择）

**实现要点**:
```tsx
// 1. 状态定义
const [filters, setFilters] = useState({
  symbol: "ALL",
  direction: "ALL",
  interval: "ALL",
  tier: "ALL",
  dateRange: undefined
});

const [pagination, setPagination] = useState({
  page: 1,
  size: 20,
  total: 0
});

const [queryTrigger, setQueryTrigger] = useState(0);  // 查询触发器

// 2. 筛选条件变更 - 不触发请求
const handleFilterChange = (key, value) => {
  setFilters(prev => ({ ...prev, [key]: value }));
};

// 3. 查询按钮点击
const handleApplyFilters = () => {
  setQueryTrigger(prev => prev + 1);  // 仅更新触发器
};

// 4. 监听触发器执行查询
useEffect(() => {
  if (queryTrigger > 0) {
    fetchSignals();
  }
}, [queryTrigger]);

// 5. 分页变更
const handlePageChange = (newPage) => {
  setPagination(prev => ({ ...prev, page: newPage }));
  setQueryTrigger(prev => prev + 1);
};

const handleSizeChange = (newSize) => {
  setPagination(prev => ({ ...prev, size: newSize, page: 1 }));
  setQueryTrigger(prev => prev + 1);
};
```

**UI 组件**:
- 使用现有的 `Pagination` 组件或创建新的分页组件
- 单页大小选择器：10/20/50/100 选项

---

### 任务 2：持仓页刷新功能

**文件**: `web_ui/src/components/Positions.tsx`

**需求**:
1. 添加"刷新"按钮
2. 点击刷新时调用 `/api/positions/refresh`
3. 支持外部触发刷新（从 App.tsx 传递 trigger）

**实现要点**:
```tsx
interface PositionsProps {
  refreshTrigger?: number;  // 外部刷新触发器
  onPositionsLoad?: (positions: any[]) => void;
}

export function Positions({ refreshTrigger, onPositionsLoad }: PositionsProps) {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(false);

  // 监听刷新触发
  useEffect(() => {
    if (refreshTrigger > 0) {
      fetchPositions();
    }
  }, [refreshTrigger]);

  // 手动刷新
  const fetchPositions = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/positions/refresh');
      const data = await res.json();
      setPositions(data.positions);
      onPositionsLoad?.(data.positions);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="flex justify-between">
        <h3>活跃持仓列表</h3>
        <Button onClick={() => fetchPositions()}>
          <RefreshCw /> 刷新
        </Button>
      </div>
      {/* 持仓列表 */}
    </>
  );
}
```

---

### 任务 3：仪表盘数据字段调整

**文件**: `web_ui/src/components/Dashboard.tsx`

**需求**:
调整账户数据展示为以下三个字段：
1. 钱包余额（初始保证金额）
2. 总计未实现盈亏
3. 保证金余额（= 钱包余额 + 未实现盈亏）

**实现要点**:
```tsx
interface DashboardProps {
  dashboardData: {
    wallet_balance: number;        // 新字段
    total_unrealized_pnl: number;  // 新字段
    margin_balance: number;        // 新字段
    current_positions_count: number;
    positions: any[];
  } | null;
}

// UI 展示
<div className="grid grid-cols-3">
  <div>
    <p className="text-sm text-zinc-500">钱包余额</p>
    <p className="text-2xl font-bold">${dashboardData.wallet_balance.toFixed(2)}</p>
  </div>
  <div>
    <p className="text-sm text-zinc-500">总计未实现盈亏</p>
    <p className={dashboardData.total_unrealized_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}>
      ${dashboardData.total_unrealized_pnl.toFixed(2)}
    </p>
  </div>
  <div>
    <p className="text-sm text-zinc-500">保证金余额</p>
    <p className="text-2xl font-bold">${dashboardData.margin_balance.toFixed(2)}</p>
  </div>
</div>
```

---

### 任务 4：App.tsx 按需加载改造

**文件**: `web_ui/src/App.tsx`

**需求**:
1. 移除全局的 signals 状态和轮询
2. 移除全局的 dashboardData 轮询（保留 systemStatus）
3. 各页面组件自行管理数据加载
4. 传递刷新触发器给子组件

**实现要点**:
```tsx
// 移除全局 signals 状态
// const [signals, setSignals] = useState([]);  // 删除

// 移除全局 dashboardData 轮询
// const { data: dashboardData } = usePolling(...);  // 删除或保留用于 SystemStatus

// 子组件按需加载
<SignalRadar
  // 不再传递 signals，组件自行加载
  onSignalsChange={handleSignalsChange}  // 可选：用于全局同步
/>

<Dashboard
  // 组件自行加载仪表盘数据
  onDashboardLoad={handleDashboardLoad}
/>

<Positions
  refreshTrigger={positionRefreshTrigger}
  onPositionsLoad={handlePositionsLoad}
/>
```

---

### 任务 5：新增分页组件（如现有组件不可用）

**文件**: `web_ui/src/components/Pagination.tsx`（新建）

**需求**:
- 显示当前页码/总页数
- 上一页/下一页按钮
- 页码跳转输入
- 单页大小选择器（10/20/50/100）

---

## 开发规范

### TypeScript
- 所有组件使用 TypeScript
- 定义 Props 接口
- 定义 API 响应类型

```tsx
interface Signal {
  id: number;
  symbol: string;
  interval: string;
  direction: string;
  score: number;
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  timestamp: number;
  quality_tier: string;
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}
```

### 代码风格
- 使用函数组件 + Hooks
- 使用 Shadcn UI 组件库
- 保持现有设计风格（深色模式支持）

### 错误处理
```tsx
try {
  const res = await fetch(apiUrl);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  // 处理数据
} catch (error) {
  toast.error("操作失败", {
    description: error instanceof Error ? error.message : "请检查网络"
  });
}
```

---

## 验收标准

### 功能验收
- [ ] 信号列表页初始不加载数据
- [ ] 设置筛选条件后，点击查询才请求
- [ ] 分页组件正常工作（翻页、改页大小）
- [ ] 查询条件改变时，页码重置为 1
- [ ] 持仓页刷新按钮触发实时查询
- [ ] 仪表盘展示新字段

### 代码验收
- [ ] TypeScript 类型定义完整
- [ ] 无 ESLint 错误
- [ ] 组件可复用性良好
- [ ] 加载状态明确
- [ ] 错误处理完善

---

## 完成后

1. 运行 `npm run lint` 检查代码
2. 运行 `npm run build` 确保编译通过
3. 准备与后端联调
