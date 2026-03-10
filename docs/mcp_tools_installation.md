# MCP 工具安装指南

## 已安装的 MCP 工具

### 1. SQLite MCP Server ✅

**用途**: 数据库操作和查询

**配置**:
```json
{
  "sqlite": {
    "command": "uvx",
    "args": ["mcp-server-sqlite", "--db-path", "/Users/jiangwei/Documents/2026/project/monitor/radar.db"]
  }
}
```

**使用场景**:
- 创建回测任务表、优化结果表
- 查询历史回测数据
- 结果对比分析

---

### 2. OpenClaw MCP ✅

**用途**: 外部 API 连接

**配置**:
```json
{
  "openclaw": {
    "command": "openclaw",
    "args": ["acp", "--url", "ws://127.0.0.1:18789", "--token-file", "~/.openclaw/gateway.token", "--session", "agent:main:main"]
  }
}
```

**使用场景**:
- 连接币安 API 获取历史 K 线
- 连接其他数据源

---

### 3. FileSystem MCP ✅ (新增)

**用途**: 文件操作和批量管理

**配置**:
```json
{
  "filesystem": {
    "command": "node",
    "args": ["/opt/homebrew/lib/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js", "/Users/jiangwei/Documents/2026/project/monitor"]
  }
}
```

**使用场景**:
- 批量导出回测结果
- 配置文件生成
- 大量文件读取/写入

---

### 4. Puppeteer MCP ✅ (新增)

**用途**: 浏览器自动化和前端测试

**配置**:
```json
{
  "puppeteer": {
    "command": "node",
    "args": ["/opt/homebrew/lib/node_modules/@modelcontextprotocol/server-puppeteer/dist/index.js"]
  }
}
```

**使用场景**:
- 前端图表渲染测试
- 回测结果页面截图
- E2E 测试

---

## 安装命令记录

### 安装 uv (提供 uvx 命令)
```bash
brew install uv
```

### 安装 MCP 工具
```bash
npm install -g @modelcontextprotocol/server-puppeteer
npm install -g @modelcontextprotocol/server-filesystem
```

---

## 配置文件位置

MCP 配置文件位于：`~/.claude/mcp.json`

---

## 验证安装

### SQLite MCP
```bash
uvx mcp-server-sqlite --help
```

### FileSystem MCP
```bash
node /opt/homebrew/lib/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js /Users/jiangwei/Documents/2026/project/monitor
```

### Puppeteer MCP
```bash
node /opt/homebrew/lib/node_modules/@modelcontextprotocol/server-puppeteer/dist/index.js --help
```

---

## 在 FMZ 集成项目中的使用

### 示例 1: 使用 SQLite MCP 查询回测结果

```sql
-- 查询某优化任务的前 10 结果
SELECT * FROM optimization_results
WHERE optimization_id = 'opt-xxx'
ORDER BY total_return DESC
LIMIT 10;
```

### 示例 2: 使用 FileSystem MCP 导出结果

```
导出回测结果到 /Users/jiangwei/Documents/2026/project/monitor/exports/backtest_result.json
```

### 示例 3: 使用 Puppeteer MCP 截图

```
访问 http://localhost:5173/backtest/lab 并截图保存
```

---

## 注意事项

1. **Puppeteer 警告**: 安装的 `@modelcontextprotocol/server-puppeteer@2025.5.12` 已标记为不再支持，但基本功能仍可用。

2. **FileSystem 权限**: 配置中限制了只能访问 `/Users/jiangwei/Documents/2026/project/monitor` 目录。

3. **SQLite 数据库路径**: 确保 `radar.db` 文件存在，如不存在会在启动时自动创建。

---

*最后更新：2026-03-10*
