# 动态可配置打分机制 - 实施总览

**版本**: v1.0
**日期**: 2026-03-03
**状态**: 文档已完成，待开发

---

## 1. 文档索引

### 1.1 完整文档列表

| 文档 | 路径 | 说明 |
|------|------|------|
| 📋 产品需求文档 (PRD) | [`docs/scoring_config_prd.md`](./scoring_config_prd.md) | 需求背景、用户故事、功能需求、验收标准 |
| 🏗️ 技术设计文档 | [`docs/scoring_config_technical_design.md`](./scoring_config_technical_design.md) | 系统架构、核心模块、数据结构、算法公式 |
| 📡 API 接口文档 | [`docs/api/scoring_config_api.md`](./api/scoring_config_api.md) | 接口定义、请求/响应格式、错误码、示例 |
| 🎨 前端 UI 开发文档 | [`docs/frontend/scoring_config_ui.md`](./frontend/scoring_config_ui.md) | UI 布局、组件设计、Hooks 实现、交互时序 |

### 1.2 文档关系图

```
                    实施总览 (本文档)
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌─────────┐     ┌──────────┐     ┌──────────┐
   │  PRD    │────▶│Technical │◀────│   API    │
   │(需求)   │     │ (设计)   │     │ (接口)   │
   └────┬────┘     └────┬─────┘     └────┬─────┘
        │               │                │
        └───────────────┼────────────────┘
                        │
                        ▼
                 ┌──────────┐
                 │  Frontend│
                 │   (UI)   │
                 └──────────┘
```

---

## 2. 功能概述

### 2.1 核心功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 打分模式切换 | classic / progressive / custom | P0 |
| 经典模式参数配置 | 7 个可调参数 | P0 |
| 累进模式参数配置 | 11 个可调参数 | P0 |
| 权重配置 | w_shape + w_trend + w_vol = 1.0 | P0 |
| 配置持久化 | SQLite 存储，重启不丢失 | P0 |
| 分数预览 | 实时预览分数分布 | P1 |

### 2.2 打分模式对比

| 特性 | 经典模式 | 累进模式 | 自定义模式 |
|------|---------|---------|-----------|
| 评分逻辑 | 线性映射 | 基础分 + 奖励分 | 可定义 |
| 边缘信号 | 40-50 分 | 45-55 分 | 自定义 |
| 精品信号 | 70-80 分 | 75-90 分 | 自定义 |
| 适用场景 | 稳定市场 | 趋势市场 | 特殊需求 |
| 参数数量 | 7 个 | 11 个 | 自定义 |

---

## 3. 实施计划

### 3.1 任务分解

#### 后端任务 (Backend)

| ID | 任务 | 预计工时 | 依赖 |
|----|------|----------|------|
| B1 | 创建 `ScoringConfig` 实体 | 0.5h | - |
| B2 | 创建 `IScoreStrategy` 接口 | 1h | B1 |
| B3 | 实现 `ClassicScoreStrategy` | 1h | B2 |
| B4 | 实现 `ProgressiveScoreStrategy` | 2h | B2 |
| B5 | 创建 `ScoringStrategyFactory` | 0.5h | B2-B4 |
| B6 | 修改 `calculate_dynamic_score` 使用策略工厂 | 1h | B5 |
| B7 | 扩展 `/api/config/scoring` 接口 (GET/PUT) | 1h | B1 |
| B8 | 创建 `/api/config/scoring/preview` 接口 | 2h | B6 |
| B9 | 单元测试 + 集成测试 | 2h | B3-B8 |
| **总计** | | **10h** | |

#### 前端任务 (Frontend)

| ID | 任务 | 预计工时 | 依赖 |
|----|------|----------|------|
| F1 | 创建组件目录结构 | 0.5h | - |
| F2 | 实现 `ModeSelector` 组件 | 1h | - |
| F3 | 实现 `WeightConfig` + `WeightSlider` | 1.5h | - |
| F4 | 实现 `ParameterSlider` 通用组件 | 1h | - |
| F5 | 实现 `ClassicModePanel` | 1h | F4 |
| F6 | 实现 `ProgressiveModePanel` | 1.5h | F4 |
| F7 | 实现 `ScoreDistributionChart` | 2h | - |
| F8 | 实现 `useScoringConfig` Hook | 1h | - |
| F9 | 实现 `useScorePreview` Hook | 1h | B8 |
| F10 | 集成测试 + UI 调试 | 2h | F2-F9 |
| **总计** | | **12.5h** | |

### 3.2 里程碑

```
Week 1
├── Day 1-2: 后端核心 (B1-B6) ✅
├── Day 3: 后端 API (B7-B8) ✅
├── Day 4: 后端测试 (B9) ✅
├── Day 5-6: 前端组件 (F1-F7) ✅
└── Day 7: 前端集成 + 联调 (F8-F10) ✅
```

---

## 4. 技术约束

### 4.1 后端约束

| 约束 | 说明 |
|------|------|
| Python 3.10+ | 使用 dataclass 和 Pydantic v2 |
| 零依赖 | `domain/strategy/` 模块不能引入第三方库 |
| 向后兼容 | 默认使用经典模式，保持原有行为 |
| 性能要求 | 打分计算额外开销 < 1ms |

### 4.2 前端约束

| 约束 | 说明 |
|------|------|
| React 18+ | 使用函数组件 + Hooks |
| TypeScript | 严格类型检查 |
| Tailwind CSS | 使用项目现有 UI 组件库 |
| 响应式 | 支持桌面/平板/移动端 |

---

## 5. 质量保障

### 5.1 测试覆盖率要求

| 模块 | 覆盖率要求 |
|------|-----------|
| domain/strategy/ | ≥ 90% |
| web/api.py (打分相关) | ≥ 85% |
| web_ui/src/components/scoring/ | ≥ 80% |

### 5.2 代码审查清单

**后端审查要点:**
- [ ] 所有配置参数有边界验证
- [ ] 权重和验证逻辑正确
- [ ] 策略工厂模式正确实现
- [ ] 异常处理完善（配置错误时使用默认值）
- [ ] 配置持久化到 SQLite

**前端审查要点:**
- [ ] 所有滑块有范围限制
- [ ] 权重和实时验证并提示
- [ ] 防抖优化正确实现
- [ ] 加载状态和错误处理
- [ ] 深色模式适配

---

## 6. 使用子代理并行开发

### 6.1 子代理任务分配

可以使用以下命令启动子代理并行开发：

```bash
# 后端开发代理
claude --agent "Backend Implementation" \
  --prompt "根据技术设计文档 (docs/scoring_config_technical_design.md) 和 API 接口文档 (docs/api/scoring_config_api.md)，
            实现后端打分配置化功能。

            任务清单:
            1. 创建 domain/strategy/scoring_config.py - ScoringConfig 实体
            2. 创建 domain/strategy/scoring_strategy.py - IScoreStrategy 接口和实现
            3. 创建 domain/strategy/scoring_factory.py - 策略工厂
            4. 修改 domain/strategy/scoring.py - 集成策略工厂
            5. 扩展 web/api.py - 新增打分配置 API
            6. 编写单元测试

            约束:
            - 严格遵循文档中的类定义和接口签名
            - 保持向后兼容
            - 所有配置参数必须有边界验证"

# 前端开发代理
claude --agent "Frontend Implementation" \
  --prompt "根据前端 UI 开发文档 (docs/frontend/scoring_config_ui.md)，
            实现打分配置中心前端组件。

            任务清单:
            1. 创建组件目录 web_ui/src/components/scoring/
            2. 实现所有子组件 (ModeSelector, WeightConfig, 等)
            3. 实现 hooks (useScoringConfig, useScorePreview)
            4. 集成到应用路由

            约束:
            - 使用 TypeScript
            - 遵循项目现有代码风格
            - 实现响应式布局
            - 适配深色模式"
```

### 6.2 子代理输出验收

**后端代理输出验收:**
- [ ] 所有文件创建完成
- [ ] 单元测试通过
- [ ] API 接口可正常调用
- [ ] 配置可持久化和热加载

**前端代理输出验收:**
- [ ] 所有组件渲染正常
- [ ] 滑块可正常调节
- [ ] 权重和验证工作正常
- [ ] 预览图表可正常显示

---

## 7. 验收标准

### 7.1 功能验收

| ID | 验收项 | 测试方法 |
|----|--------|----------|
| ACC-01 | 模式切换正常 | 切换模式后查看新信号分数 |
| ACC-02 | 经典模式参数可调 | 调整参数后分数变化符合公式 |
| ACC-03 | 累进模式参数可调 | 调整参数后分数变化符合公式 |
| ACC-04 | 权重验证正常 | 权重和!=1 时提示错误 |
| ACC-05 | 配置持久化 | 重启后配置保持 |
| ACC-06 | 预览功能正常 | 调整参数后预览实时更新 |

### 7.2 性能验收

| ID | 验收项 | 目标值 |
|----|--------|--------|
| PERF-01 | 配置接口 P99 延迟 | < 100ms |
| PERF-02 | 打分计算额外开销 | < 1ms |
| PERF-03 | 预览接口响应时间 | < 5s (500 根 K 线) |

---

## 8. 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 配置参数过多，用户困惑 | 中 | 中 | 提供预设推荐值 |
| 累进模式公式复杂，难调试 | 低 | 低 | 增加详细日志 |
| 预览接口性能问题 | 中 | 中 | 限制最大 K 线数量 |
| 前端组件状态管理复杂 | 低 | 低 | 使用成熟 Hooks 模式 |

---

## 9. 后续扩展

### 9.1 短期扩展 (v1.1)

- [ ] 增加更多打分模式（如机器学习模型）
- [ ] 支持按币种/周期保存独立配置
- [ ] 配置版本管理和回滚

### 9.2 长期扩展 (v2.0)

- [ ] AI 辅助参数推荐
- [ ] 配置分享和导入导出
- [ ] 回测对比工具集成

---

## 10. 附录

### 10.1 相关文档

- [项目主文档](../../README.md)
- [API 契约文档](./api_contract.md)
- [Pinbar 优化 v2.0](./pinbar_optimization_v2.md)

### 10.2 联系方式

- 项目仓库：https://github.com/monitor/monitor
- 问题反馈：提交 Issue

### 10.3 修订历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2026-03-03 | Claude | 初始版本 |
