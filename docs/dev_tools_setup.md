# 开发工具配置指南

本文档记录项目推荐的高效开发工具配置，包含 MCP Server、子代理使用策略等。

---

## ✅ 已完成配置

### 1. MCP SQLite Server

**用途**: 直接查询 radar.db 数据库，分析信号数据和系统状态

**配置文件** (`~/.claude/mcp.json`):
```json
{
  "mcpServers": {
    "sqlite": {
      "command": "/Users/jiangwei/Documents/2026/project/monitor/venv/bin/mcp-server-sqlite",
      "args": ["--db-path", "/Users/jiangwei/Documents/2026/project/monitor/radar.db"]
    }
  }
}
```

**已安装依赖**:
```bash
mcp-server-sqlite==2025.4.25
mcp==1.26.0
```

**使用方法**:
- 直接提问：「查询最近 10 条信号记录」
- 分析数据：「分析 A 级信号的胜率」
- 审计追踪：「查看今天的信号入库时间分布」

---

## 📋 推荐但需手动配置的工具

### 2. MCP Filesystem Server (需手动安装)

**用途**: 增强的文件浏览和编辑能力，支持安全范围内的文件操作

**安装命令**:
```bash
# 方式 1: 使用 npx (推荐)
npx -y @modelcontextprotocol/server-filesystem /Users/jiangwei/Documents/2026/project/monitor

# 方式 2: 使用 uvx (Python 生态)
uvx mcp-server-filesystem
```

**配置** (添加到 `~/.claude/mcp.json`):
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/jiangwei/Documents/2026/project/monitor"]
    }
  }
}
```

---

## 🚀 子代理并行使用策略

### 场景 1: 代码探索 (已演示)

**同时启动 3 个 Explore Agent**:
```
├─ Explore(quick)    → 探索前端组件结构
├─ Explore(medium)   → 探索后端策略逻辑
└─ Explore(thorough) → 探索数据流水线架构
```

**收益**: 原本需要 15 分钟的探索工作，现在 3 分钟内完成

### 场景 2: 新功能开发

**示例：添加新的信号过滤条件**

```
主对话 (你)          → 修改 domain/strategy/pinbar.py 核心逻辑
  ├─ Agent 1        → 更新前端 Settings.tsx 配置表单
  ├─ Agent 2        → 添加 API 路由 web/api.py
  └─ Explore Agent  → 查找所有使用 PinbarConfig 的位置
```

### 场景 3: Bug 修复

```
├─ Agent 1  → 分析错误日志，定位问题模块
├─ Agent 2  → 复现路径分析，编写测试用例
└─ Agent 3  → 修复方案验证，回归测试
```

### 场景 4: 代码审查

**使用 simplify skill**:
```
simplify: 审查关键模块代码质量
- 代码复用
- 潜在 bug
- 性能优化点
- 类型安全
```

---

## 📊 项目架构快速参考

### 后端目录结构
```
monitor/
├── core/              # 核心层：实体、接口、异常
├── domain/            # 领域层：策略、风控 (纯业务逻辑)
│   ├── strategy/      # pinbar.py, indicators.py, scoring.py
│   └── risk/          # sizer.py
├── application/       # 应用层：引擎编排
│   ├── monitor_engine.py
│   ├── history_scanner.py
│   └── chart_service.py
├── infrastructure/    # 基础设施层：外部适配器
│   ├── feed/          # binance_ws.py, binance_kline_fetcher.py
│   ├── reader/        # binance_api.py
│   ├── repo/          # sqlite_repo.py
│   └── notify/        # feishu.py, telegram.py, wecom.py
├── web/               # API 路由层
│   └── api.py
└── web_ui/            # React 前端
    └── src/
        ├── App.tsx
        └── components/
```

### 关键设计原则
- **Zero Execution**: 系统只读，从不下单
- **依赖倒置**: 领域层定义接口，基础设施层实现
- **并发隔离**: 通知多渠道并发，单渠道失败不影响整体
- **WAL 模式**: SQLite 支持并发读写
- **信号分级**: A 级精品、B 级普通、C 级观察

---

## 🔧 常用开发命令

### 后端
```bash
# 激活虚拟环境
source venv/bin/activate

# 运行后端服务
python main.py

# 查看日志
tail -f backend.log
```

### 前端
```bash
cd web_ui

# 开发服务器
npm run dev

# 类型检查 + 构建
npm run build

# Lint 检查
npm run lint
```

### Docker
```bash
# 启动全部服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 重启后端
docker-compose restart backend
```

---

## 📝 最佳实践

### 1. 使用 Explore Agent 而非手动搜索
- 快速定位文件：`Explore(quick)`
- 理解模块结构：`Explore(medium)`
- 追踪完整链路：`Explore(thorough)`

### 2. 并行化独立任务
- 前后端分离开发时同时推进
- 多个文件修改可分配给不同 Agent
- 代码编写和测试同步进行

### 3. 代码审查常态化
- 完成模块后使用 `simplify` skill 审查
- 重构前让 Agent 分析技术债务
- 新功能添加前检查是否有重复代码

### 4. 利用 MCP SQLite 分析数据
- 查询信号记录验证策略效果
- 分析胜率、盈亏比等关键指标
- 审计系统运行状态

---

## ⚠️ 注意事项

1. **MCP Server 依赖**: SQLite MCP Server 已安装在项目虚拟环境中，确保路径正确
2. **数据库路径**: 配置文件中的路径为绝对路径，移动项目需更新
3. **虚拟环境**: 确保 MCP Server 使用项目 venv 中的 Python
4. **权限**: MCP Server 只能访问指定数据库文件，不会越权

---

## 📚 相关文档

- [项目架构说明](../CLAUDE.md)
- [Pinbar 策略文档](../docs/pinbar_detection_flow.md)
- [通知模板](../docs/push.md)

---

*最后更新：2026-03-03*
