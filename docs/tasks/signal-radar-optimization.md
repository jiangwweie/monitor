# 信号雷达页面优化方案

**创建日期**: 2026-03-05
**优先级**: P0 - 高优先级

---

## 一、问题分析

### 1.1 页面布局问题
- 筛选条件区域布局拥挤，所有筛选器排布在同一行，缺乏层次感
- 操作按钮区域与筛选条件混在一起，视觉混乱
- 缺少明确的视觉分区

### 1.2 表头宽度问题
- 当前使用硬编码宽度 (如 `w-[160px]`、`w-[40px]`)
- 当通过"视图设置"显示/隐藏列时，剩余列宽度不会重新分配
- 导致表格要么过宽溢出，要么过窄留白

### 1.3 历史信号检查功能问题 (核心问题)

**前端问题：**
- 提交任务后只显示一个 toast 提示，用户无法在页面上看到任务进度
- 没有任务状态轮询机制，用户不知道后台是正在扫描还是已失败
- 扫描完成后没有自动刷新信号列表
- 用户完全不知道程序是否在运行、进度如何、是否完成

**后端现状：**
- 有完整的任务状态跟踪 (`HistoryScanTask`)
- 有进度百分比 (0-100%) 和状态消息
- 有任务状态查询接口 `/api/signals/history-check/{task_id}`
- 但前端没有利用这些接口获取实时反馈

---

## 二、优化方案

### 2.1 布局重构

**筛选区域分层设计：**

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔍 信号过滤与筛选                                                │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ [时间范围选择器]  │  [币种▼] [方向▼] [周期▼] [等级▼]       │ │
│ │ [查询按钮] [刷新按钮]                                       │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ ─────────────────────────────────────────────────────────────── │
│ [视图设置▼]  [历史信号检查]  [清空记录]        [批量删除按钮]  │
└─────────────────────────────────────────────────────────────────┘
```

**改进点：**
- 主筛选条件放在上层卡片内，视觉聚焦
- 次要操作 (视图设置、历史扫描) 放在下层分隔线外
- 批量操作按钮右对齐，与功能操作区分

### 2.2 表头宽度动态分配

**方案 A - CSS Grid:**
```css
.signal-table {
  display: grid;
  grid-template-columns:
    40px                    /* 复选框 */
    minmax(150px, 1.5fr)    /* 时间 - 弹性 */
    minmax(100px, 1fr)      /* 币种 - 弹性 */
    80px                    /* 方向 - 固定 */
    100px                   /* 评分 - 固定 */
    minmax(100px, 1fr)      /* 入场价 - 弹性 */
    80px                    /* 操作 - 固定 */
}
```

**方案 B - 动态计算:**
```typescript
const getColumnWidths = (columns: Record<string, boolean>) => {
  const visibleCols = Object.entries(columns)
    .filter(([_, visible]) => visible)
    .map(([key]) => key);

  const fixedWidthCols: Record<string, string> = {
    checkbox: '40px',
    timestamp: '160px',
    symbol: '120px',
    direction: '80px',
    action: '120px',
  };

  // 根据实际显示列动态生成 grid-template-columns
  return visibleCols.map(col =>
    col in fixedWidthCols ? fixedWidthCols[col] : 'minmax(80px, 1fr)'
  ).join(' ');
};
```

### 2.3 历史信号检查反馈优化 (核心)

**新增任务进度面板组件 `HistoryScanProgressPanel.tsx`:**

```typescript
interface TaskStatus {
  task_id: string;
  status: "running" | "completed" | "failed";
  progress: number;      // 0-100
  message: string;       // "正在拉取 K 线数据：500/1000"
  result?: {
    total_bars_scanned: number;
    signals_found: number;
    signals_saved: number;
  };
}
```

**轮询逻辑:**
```typescript
// 使用现有 usePolling hook
usePolling(
  async () => {
    const res = await fetch(
      `${API_BASE}/api/signals/history-check/${taskId}`
    );
    if (!res.ok) throw new Error("Status fetch failed");
    return await res.json();
  },
  {
    interval: 1000,  // 1 秒轮询
    enabled: isRunning,
    onSuccess: (data) => {
      if (data.status === "completed") {
        // 任务完成
        setIsRunning(false);
        // 自动刷新信号列表
        onRefreshSignals();
        // 显示完成通知
        toast.success(`扫描完成！发现 ${data.result.signals_found} 个信号`);
      } else if (data.status === "failed") {
        setIsRunning(false);
        toast.error(`扫描失败：${data.message}`);
      }
      // 更新进度状态
      setTaskStatus(data);
    }
  }
)
```

**进度面板 UI 设计:**
```
┌─────────────────────────────────────────────────────────┐
│ 📡 历史信号扫描                                         │
│ ─────────────────────────────────────────────────────── │
│ 任务 ID: scan-a1b2c3d4e5f6              [关闭×]        │
│                                                          │
│ ████████████░░░░░░░░░░░░░░░░░  45%                      │
│                                                          │
│ 状态：正在执行策略回放扫描...                            │
│ 已扫描 450 / 1000 根 K 线                                │
│                                                          │
│ 开始时间：2026-03-05 18:00:00                           │
│ 已运行：00:02:15                                        │
│                                                          │
│ ─────────────────────────────────────────────────────── │
│ 扫描配置：BTCUSDT | 1h | 2026-01-01 ~ 2026-03-05       │
└─────────────────────────────────────────────────────────┘
```

**任务完成后状态:**
```
┌─────────────────────────────────────────────────────────┐
│ ✅ 扫描完成                           [关闭×]           │
│ ─────────────────────────────────────────────────────── │
│ ██████████████████████████████  100%                   │
│                                                          │
│ 📊 扫描结果:                                            │
│ • 扫描 K 线总数：1,250 根                               │
│ • 发现信号数：23 个                                     │
│ • 成功入库：21 个 (2 个重复已跳过)                       │
│                                                          │
│ [查看这些信号 →]  [关闭]                                │
└─────────────────────────────────────────────────────────┘
```

### 2.4 交互流程优化

**当前流程 (有问题):**
```
用户点击"历史信号检查"
  → 填写表单
  → 点击开始
  → Toast 提示"任务已启动"
  → ❌ 无后续反馈，用户不知道发生了什么
```

**优化后流程:**
```
用户点击"历史信号检查"
  → 弹出配置对话框
  → 填写表单
  → 点击开始
  → 弹出进度面板 (固定在页面右下角)
  → 实时显示进度 (每 1 秒更新)
  → 任务完成 → 自动刷新信号列表 + Toast 通知
  → 进度面板显示完成状态和结果摘要
```

---

## 三、技术实现细节

### 3.1 前端文件修改清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `web_ui/src/components/SignalRadar.tsx` | 重构 | 布局调整、集成进度面板 |
| `web_ui/src/components/HistoryScanProgressPanel.tsx` | 新增 | 进度面板组件 |
| `web_ui/src/App.tsx` | 修改 | 传递刷新回调 |
| `web_ui/src/hooks/usePolling.ts` | 复用 | 已有轮询 hook |

### 3.2 后端接口 (已有，无需修改)

```python
# 提交任务
POST /api/signals/history-check
Body: { start_date, end_date, symbol, interval }
Response: { status: "accepted", task_id: "xxx" }

# 查询进度
GET /api/signals/history-check/{task_id}
Response: {
  task_id: "xxx",
  status: "running" | "completed" | "failed",
  progress: 45,
  message: "正在扫描 450/1000 根 K 线",
  result: { ... }  # 完成后返回
}
```

### 3.3 状态管理

```typescript
// SignalRadar 组件内状态
const [historyScanTasks, setHistoryScanTasks] = useState<Map<string, TaskStatus>>(new Map());
const [isProgressPanelOpen, setIsProgressPanelOpen] = useState(false);
const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

// 提交任务后
const handleSubmitHistoryScan = async () => {
  const res = await fetch(...);
  const data = await res.json();

  // 立即打开进度面板
  setActiveTaskId(data.task_id);
  setIsProgressPanelOpen(true);

  // 轮询逻辑自动开始
}
```

---

## 四、优先级与排期

### P0 - 必须修复 (本次实施)
- [x] 历史信号检查进度反馈
- [x] 任务完成后自动刷新信号列表
- [ ] 表头宽度动态调整

### P1 - 高优先级 (后续)
- [ ] 布局视觉优化
- [ ] 筛选条件分组
- [ ] 添加"信号来源"筛选

### P2 - 中优先级 (后续)
- [ ] 多任务并发管理
- [ ] 任务列表历史
- [ ] 可取消进行中的任务

### P3 - 低优先级 (可选)
- [ ] 列宽拖拽调整
- [ ] 信号分布图表
- [ ] 保存筛选预设

---

## 五、验收标准

### 历史信号检查功能
- [ ] 提交任务后立即显示进度面板
- [ ] 进度条实时更新 (延迟 < 2 秒)
- [ ] 状态文本清晰描述当前阶段
- [ ] 任务完成时自动刷新信号列表
- [ ] 有成功/失败通知反馈
- [ ] 进度面板可手动关闭

### 表格显示
- [ ] 显示/隐藏列时表头宽度自动适应
- [ ] 表格不出现横向滚动条 (在合理分辨率下)
- [ ] 各列内容不截断、不溢出

---

## 六、备注

- 后端 `HistoryScanner` 逻辑完整，进度跟踪机制完善，无需修改
- 前端已有 `usePolling` hook 可直接复用
- UI 组件库 (Shadcn) 的 `Progress`、`Card`、`Badge` 组件可直接使用
- 保持与现有代码风格一致 (TypeScript + Tailwind CSS)
