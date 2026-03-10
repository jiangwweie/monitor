# FMZ 回测框架集成 - 参数优化模块补充设计

## 文档信息

- **版本**: v1.0
- **创建日期**: 2026-03-10
- **作者**: System Architect
- **状态**: 设计稿
- **关联文档**: [fmz_backtest_integration_plan.md](./fmz_backtest_integration_plan.md)

---

## 1. 概述

### 1.1 设计目标

本补充设计文档针对参数优化模块，解决主设计中缺失的关键细节：

| 问题领域 | 主设计状态 | 本设计补充 |
|---------|-----------|-----------|
| 配置验证保护 | ❌ 缺失 | ✅ 完整的边界保护机制 |
| 任务队列管理 | ❌ 缺失 | ✅ 并发控制和优先级策略 |
| 优化目标体系 | ⚠️ 简单提及 | ✅ 单目标/多目标/自定义 |
| 防止过拟合 | ❌ 缺失 | ✅ 样本外验证和稳定性分析 |
| 结果管理 | ❌ 缺失 | ✅ 版本管理和对比机制 |

### 1.2 核心约束

```
【资源保护红线】
- 单次优化任务最大参数组合数：10,000
- 单用户并发任务数上限：3
- 全局并发回测数上限：10
- 单个回测最大 K 线数：50,000
- 优化任务最长执行时间：4 小时

【数据隔离原则】
- 用户只能访问自己的优化历史
- 优化任务与回测任务共享队列但独立计数
- 敏感配置（API 密钥）不参与优化
```

---

## 2. 参数验证和保护机制

### 2.1 参数范围配置结构

```yaml
# 参数范围配置示例
optimization_config:
  # 基础回测配置
  base_config:
    symbol: "BTCUSDT"
    interval: "1h"
    start_date: "2024-01-01"
    end_date: "2024-12-31"
    initial_balance: 10000

  # 待优化参数定义
  parameters:
    - name: "risk_pct"
      display_name: "单笔风险比例"
      type: "float"
      min: 0.005
      max: 0.05
      step: 0.005
      default: 0.02

    - name: "max_sl_dist"
      display_name: "最大止损距离"
      type: "float"
      min: 0.02
      max: 0.08
      step: 0.005
      default: 0.035

    - name: "pinbar_config.shadow_min_ratio"
      display_name: "影线最小比例"
      type: "float"
      min: 1.5
      max: 4.0
      step: 0.5
      default: 2.5

  # 优化目标配置
  objective:
    type: "single"  # "single" | "multi" | "custom"
    metric: "total_return"  # 优化指标
    direction: "maximize"   # "maximize" | "minimize"

  # 约束条件（可选）
  constraints:
    - metric: "max_drawdown"
      operator: "<="
      value: 20.0
    - metric: "win_rate"
      operator: ">="
      value: 40.0
```

### 2.2 参数验证规则

```yaml
验证规则:
  参数数量限制:
    - 最多可配置参数：8 个
    - 推荐参数数量：≤ 4 个
    - 原因：每增加 1 个参数，组合数呈指数增长

  取值范围限制:
    - float 类型：min/max 差值不超过 100 倍
    - int 类型：max - min 不超过 100
    - 离散值：最多 10 个可选项

  组合数保护:
    - 计算公式：Π(每个参数的取值数量)
    - 硬性上限：10,000 组合
    - 预警阈值：5,000 组合
    - 超出处理：拒绝执行并要求缩减范围

  时间范围保护:
    - 最短回测周期：7 天
    - 最长回测周期：2 年
    - 预估执行时间 = 组合数 × 平均单回测耗时 (秒)
    - 超出 4 小时的任务被拒绝
```

### 2.3 验证流程

```
┌─────────────────────────────────────────────────────────────┐
│                    用户提交优化配置                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 参数格式验证                                        │
│  - 检查参数类型是否合法                                      │
│  - 检查 min <= default <= max                               │
│  - 检查 step 是否合理                                        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 组合数计算和验证                                    │
│  - 计算总组合数 = Π(参数取值数量)                            │
│  - 如果 > 10,000 → 拒绝                                      │
│  - 如果 > 5,000 → 警告，要求确认                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 预估执行时间                                        │
│  - 基于历史数据估算单回测耗时                                │
│  - 预估总时间 = 组合数 × 平均耗时                           │
│  - 如果 > 4 小时 → 拒绝                                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 资源可用性检查                                      │
│  - 检查当前队列长度                                          │
│  - 检查用户并发任务数                                        │
│  - 预估等待时间 = 队列长度 × 平均执行时间                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  验证通过 → 创建优化任务                                      │
│  验证失败 → 返回具体错误信息                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 任务队列和并发控制

### 3.1 任务优先级定义

```python
class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0    # 系统级任务（如回归测试）
    HIGH = 1        # 付费用户 / 紧急分析
    NORMAL = 2      # 普通用户回测
    LOW = 3         # 批量优化任务
```

### 3.2 任务队列架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        任务提交入口                              │
│              (POST /api/backtest/optimize)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      验证中间件                                  │
│    - 参数验证                                                   │
│    - 用户配额检查                                                │
│    - 组合数保护                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Redis 任务队列                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ priority=0  │  │ priority=1  │  │ priority=2  │  ...        │
│  │  紧急队列   │  │  高优队列   │  │  普通队列   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    任务调度器 (Scheduler)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  调度策略：                                              │   │
│  │  1. 优先处理高优先级队列                                 │   │
│  │  2. 同优先级 FIFO 处理                                    │   │
│  │  3. 检查并发限制 (全局/单用户)                            │   │
│  │  4. 分配空闲工作节点                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     工作节点池 (Workers)                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐               │
│  │Worker-1 │ │Worker-2 │ │Worker-3 │ │   ...   │               │
│  │ (回测)  │ │ (回测)  │ │ (回测)  │ │         │               │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘               │
│                                                                    │
│  并发限制：                                                        │
│  - 全局最大并发：10 个回测任务                                     │
│  - 单用户最大并发：3 个任务                                        │
│  - 优化任务占用：1 个优化任务 = 1 个并发槽位                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 任务状态机

```
                    ┌──────────────┐
                    │   pending    │ ← 任务创建，等待调度
                    └──────┬───────┘
                           │ 调度器分配
                           ▼
                    ┌──────────────┐
                    │   queued     │ ← 已入队，等待执行
                    └──────┬───────┘
                           │ 开始执行
                           ▼
                    ┌──────────────┐
              ┌──── │    running   │
              │     └──────┬───────┘
              │            │ 进度更新
              │            ▼
              │     ┌──────────────┐
              │     │   progress   │ ← 执行中 (0-100%)
              │     └──────┬───────┘
              │            │
         用户取消          │ 执行完成
              │            ▼
              │     ┌──────────────┐
              │     │  completed   │ ← 正常完成
              │     └──────────────┘
              │
              │ 执行错误/超时
              ▼
       ┌──────────────┐
       │    failed    │ ← 执行失败
       └──────────────┘
```

### 3.4 并发控制策略

```python
# 并发控制配置
CONCURRENCY_CONFIG = {
    # 全局限制
    "global": {
        "max_concurrent_backtests": 10,    # 最大并发回测数
        "max_concurrent_optimizations": 2, # 最大并发优化任务数
        "max_queue_size": 100,             # 最大队列长度
    },

    # 单用户限制
    "per_user": {
        "max_concurrent_tasks": 3,         # 单用户最大并发数
        "max_daily_optimizations": 10,     # 每日优化任务上限
        "max_daily_backtests": 50,         # 每日回测任务上限
    },

    # 优化任务特殊限制
    "optimization": {
        "max_parameter_combinations": 10000,  # 最大参数组合数
        "max_estimated_duration_hours": 4,    # 最大预估执行时间
        "require_confirmation_above": 5000,   # 超过此组合数需确认
    },
}
```

---

## 4. 优化目标体系

### 4.1 单目标优化

```yaml
# 支持的单目标指标
single_objective_metrics:
  # 收益类
  - name: "total_return"
    display: "总收益率"
    direction: "maximize"

  - name: "annualized_return"
    display: "年化收益率"
    direction: "maximize"

  # 风险类
  - name: "max_drawdown"
    display: "最大回撤"
    direction: "minimize"

  - name: "volatility"
    display: "收益率波动率"
    direction: "minimize"

  # 风险调整后收益
  - name: "sharpe_ratio"
    display: "夏普比率"
    direction: "maximize"

  - name: "sortino_ratio"
    display: "索提诺比率"
    direction: "maximize"

  - name: "calmar_ratio"
    display: "卡尔玛比率"
    direction: "maximize"

  # 交易质量
  - name: "win_rate"
    display: "胜率"
    direction: "maximize"

  - name: "profit_factor"
    display: "盈亏比"
    direction: "maximize"

  - name: "avg_trade_duration"
    display: "平均持仓时间"
    direction: "minimize"  # 或根据策略类型调整
```

### 4.2 多目标优化（帕累托前沿）

```yaml
# 多目标优化配置
multi_objective_config:
  # 目标组合预设
  presets:
    - name: "收益 - 风险平衡"
      objectives:
        - metric: "total_return"
          weight: 0.5
          direction: "maximize"
        - metric: "max_drawdown"
          weight: 0.5
          direction: "minimize"

    - name: "稳定收益"
      objectives:
        - metric: "sharpe_ratio"
          weight: 0.6
          direction: "maximize"
        - metric: "win_rate"
          weight: 0.4
          direction: "maximize"

    - name: "自定义组合"
      objectives:
        # 用户自定义指标和权重
        - metric: "user_defined"
          weight: "user_defined"
          direction: "user_defined"

  # 帕累托前沿输出
  pareto_front_output:
    enabled: true
    max_solutions: 50  # 最多返回的帕累托最优解数量
    visualization: true  # 生成帕累托前沿图
```

### 4.3 自定义目标函数

```python
# 自定义目标函数模板
CUSTOM_OBJECTIVE_FUNCTION_TEMPLATE = """
# 用户可定义自己的目标函数
# 输入：回测结果字典
# 输出：标量分数（越大越好）

def custom_objective(backtest_result: dict) -> float:
    '''
    自定义优化目标函数

    Args:
        backtest_result: 包含以下字段
        - summary: {total_return, max_drawdown, win_rate, sharpe_ratio, ...}
        - trades: 交易明细列表
        - equity_curve: 权益曲线数据

    Returns:
        优化目标分数（越大表示越好）
    '''
    summary = backtest_result['summary']

    # 示例：综合评分公式
    score = (
        summary['total_return'] * 0.4 +          # 40% 权重给收益
        summary['sharpe_ratio'] * 10 * 0.3 +     # 30% 权重给夏普比率
        summary['win_rate'] * 0.3 +              # 30% 权重给胜率
        (-summary['max_drawdown']) * 0.2         # 回撤惩罚
    )

    return score
"""
```

---

## 5. 防止过拟合机制

### 5.1 样本外验证设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    样本外验证流程                                │
└─────────────────────────────────────────────────────────────────┘

步骤 1: 数据划分
┌──────────────────────────────────────────────────────────────┐
│  总数据: 2024-01-01 ~ 2024-12-31                             │
│                                                              │
│  ┌─────────────────────┬─────────────────────┐              │
│  │    训练集 (70%)      │    测试集 (30%)      │              │
│  │  2024-01-01 ~ 09-07 │  2024-09-08 ~ 12-31 │              │
│  │   (参数优化用)       │  (验证用)           │              │
│  └─────────────────────┴─────────────────────┘              │
└──────────────────────────────────────────────────────────────┘

步骤 2: 训练集优化
┌──────────────────────────────────────────────────────────────┐
│  在训练集上运行参数优化 → 得到最优参数组合                    │
│  输出：Top-N 参数组合列表                                     │
└──────────────────────────────────────────────────────────────┘

步骤 3: 测试集验证
┌──────────────────────────────────────────────────────────────┐
│  将 Top-N 参数组合在测试集上回测                               │
│  检查：训练集表现 vs 测试集表现                               │
│  如果差异过大 → 标记为"可能过拟合"                            │
└──────────────────────────────────────────────────────────────┘

步骤 4: 结果输出
┌──────────────────────────────────────────────────────────────┐
│  对每个参数组合输出：                                          │
│  - 训练集收益 / 测试集收益                                    │
│  - 收益衰减率 = (训练 - 测试) / 训练                          │
│  - 过拟合风险等级：低 / 中 / 高                               │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 过拟合检测规则

```yaml
过拟合检测规则:
  收益衰减检测:
    - 规则：测试集收益 < 训练集收益 × 50%
    - 触发：标记为"高度过拟合风险"
    - 建议：重新选择参数范围或增加训练数据

  参数敏感性检测:
    - 规则：参数微调导致收益大幅波动
    - 计算：相邻参数的收益变化率
    - 触发：变化率 > 20% 标记为"参数敏感"
    - 建议：选择参数曲面上的"平稳区域"

  交易次数检测:
    - 规则：总交易次数 < 30
    - 触发：标记为"统计显著性不足"
    - 建议：延长回测周期或调整策略参数

  市场状态检测:
    - 规则：仅在特定市场状态（单边上涨/下跌）表现好
    - 计算：不同市场状态下的收益分布
    - 触发：分布极度不均时标记
    - 建议：添加市场状态过滤或分别优化
```

### 5.3 参数稳定性分析

```yaml
参数稳定性分析:
  分析方法:
    - 参数曲面分析：绘制参数 - 收益 3D 曲面图
    - 敏感性热力图：展示参数变化对收益的影响
    - 最优区域识别：找出"收益高原"而非"收益高峰"

  输出内容:
    - 参数稳定性评分 (0-100)
    - 推荐参数（稳定性优先）
    - 风险参数（敏感性高）

  可视化:
    - 2D 热力图（2 参数时）
    - 3D 曲面图（2 参数时）
    - 等高线图（多参数时）
```

---

## 6. 结果管理和对比

### 6.1 优化结果数据结构

```yaml
# 单次优化任务结果结构
OptimizationResult:
  optimization_id: "opt-xxxx-xxxx"
  status: "completed"

  # 配置信息
  config:
    symbol: "BTCUSDT"
    interval: "1h"
    period: "2024-01-01 ~ 2024-12-31"
    objective: "total_return"

  # 参数空间定义
  parameters:
    - name: "risk_pct"
      values_tested: [0.01, 0.015, 0.02, 0.025, 0.03]

    - name: "max_sl_dist"
      values_tested: [0.025, 0.03, 0.035, 0.04]

  # 执行统计
  execution:
    total_combinations: 20
    completed_combinations: 20
    start_time: 1709999999
    end_time: 1710000999
    duration_seconds: 1000

  # 结果列表（按目标指标排序）
  results:
    - rank: 1
      params:
        risk_pct: 0.02
        max_sl_dist: 0.03
      metrics:
        total_return: 45.6
        max_drawdown: 12.3
        win_rate: 55.2
        sharpe_ratio: 1.85
        total_trades: 127
      out_of_sample:  # 样本外验证（如有）
        enabled: true
        oos_return: 38.2
        decay_rate: 0.162
      stability:
        score: 85
        risk_level: "low"

    - rank: 2
      params: {...}
      metrics: {...}
      ...

  # 统计分析
  analysis:
    best_params: {...}
    worst_params: {...}
    parameter_importance:
      risk_pct: 0.65  # 该参数对结果影响程度
      max_sl_dist: 0.35
    correlation_matrix: {...}
```

### 6.2 结果对比功能

```yaml
结果对比功能:
  对比维度:
    - 多次优化任务对比
    - 同一任务不同参数组合对比
    - 不同市场阶段对比
    - 样本内 vs 样本外对比

  对比指标:
    - 收益类：总收益、年化收益、月均收益
    - 风险类：最大回撤、波动率
    - 质量类：夏普比率、胜率、盈亏比
    - 稳定性：参数敏感性、过拟合风险

  可视化输出:
    - 收益对比柱状图
    - 权益曲线叠加图
    - 参数 - 收益热力图
    - 帕累托前沿散点图
    - 雷达图（多维度对比）

  导出格式:
    - PDF 报告（完整分析）
    - Excel（数据明细）
    - CSV（原始数据）
    - JSON（机器可读）
```

### 6.3 版本管理

```yaml
版本管理设计:
  版本控制:
    - 每次优化任务生成唯一版本号
    - 支持给优化结果打标签（如"生产使用"）
    - 支持版本回滚（恢复到历史参数）

  变更追踪:
    - 记录参数修改历史
    - 记录性能变化趋势
    - 支持版本间差异对比

  命名规范:
    - opt-{symbol}-{interval}-{date}-{sequence}
    - 示例：opt-BTCUSDT-1h-20240310-001

  保留策略:
    - 最近 30 天的优化结果全部保留
    - 30 天前仅保留打标签的版本
    - 用户可手动标记"长期保留"
```

---

## 7. API 详细设计

### 7.1 创建优化任务

```yaml
POST /api/backtest/optimize

请求体:
  symbol: "BTCUSDT"
  interval: "1h"
  start_date: "2024-01-01"
  end_date: "2024-12-31"

  # 初始资金和风控
  initial_balance: 10000
  base_risk_pct: 0.02
  base_max_sl_dist: 0.035

  # 待优化参数
  parameters:
    - name: "risk_pct"
      values: [0.01, 0.015, 0.02, 0.025, 0.03]

    - name: "max_sl_dist"
      min: 0.02
      max: 0.05
      step: 0.005

    - name: "pinbar_config.shadow_min_ratio"
      values: [2.0, 2.5, 3.0]

  # 优化目标
  objective:
    type: "single"  # single | multi | custom
    metric: "total_return"
    direction: "maximize"

  # 约束条件（可选）
  constraints:
    - metric: "max_drawdown"
      operator: "<="
      value: 20.0

  # 高级选项
  advanced:
    out_of_sample_enabled: true
    out_of_sample_ratio: 0.3
    stability_analysis: true
    priority: "normal"
    notify_on_complete: true

响应:
  optimization_id: "opt-xxxx-xxxx"
  status: "queued"
  estimated_combinations: 75
  estimated_duration_minutes: 15
  queue_position: 3
  message: "任务已提交，预计等待 15 分钟后开始执行"
```

### 7.2 查询优化进度

```yaml
GET /api/backtest/optimize/{optimization_id}/progress

响应:
  optimization_id: "opt-xxxx-xxxx"
  status: "running"  # queued | running | completed | failed
  progress:
    overall: 45  # 总体进度 0-100%
    stage: "optimizing"  # validating | optimizing | validating_oos | analyzing
    completed_combinations: 34
    total_combinations: 75
    current_combination:
      risk_pct: 0.02
      max_sl_dist: 0.03
      result: { total_return: 32.5, ... }
  execution:
    started_at: 1709999999
    elapsed_seconds: 450
    estimated_remaining_seconds: 550
    combinations_per_minute: 4.5
  queue_info:  # 如果还在排队
    position: 2
    estimated_start_time: 1710000500
```

### 7.3 获取优化结果

```yaml
GET /api/backtest/optimize/{optimization_id}/result

响应:
  optimization_id: "opt-xxxx-xxxx"
  status: "completed"
  config: {...}
  results:
    summary:
      total_combinations: 75
      successful: 75
      failed: 0
      best_total_return: 52.3
      best_sharpe_ratio: 2.1

    top_results:
      - rank: 1
        params: {...}
        metrics: {...}
        stability_score: 85

      - rank: 2
        params: {...}
        metrics: {...}
        stability_score: 92

    analysis:
      parameter_importance: {...}
      correlation_matrix: {...}
      overfitting_risk: "low"
      recommended_params: {...}

  # 完整结果（可分页或分批获取）
  all_results:
    total: 75
    page: 1
    page_size: 20
    data: [...]
```

### 7.4 结果对比

```yaml
POST /api/backtest/optimize/compare

请求体:
  optimization_ids:
    - "opt-xxxx-001"
    - "opt-xxxx-002"
    - "opt-xxxx-003"
  comparison_metrics:
    - "total_return"
    - "max_drawdown"
    - "sharpe_ratio"

响应:
  comparison_table:
    headers: ["指标", "opt-001", "opt-002", "opt-003"]
    rows:
      - ["总收益 (%)", "52.3", "48.1", "55.7"]
      - ["最大回撤 (%)", "12.5", "10.2", "18.3"]
      - ["夏普比率", "2.10", "2.35", "1.85"]
      - ["胜率 (%)", "55.2", "52.1", "58.3"]

  visualizations:
    equity_curves_url: "/api/charts/equity/compare?ids=..."
    bar_chart_url: "/api/charts/bar/compare?ids=..."
```

### 7.5 取消优化任务

```yaml
POST /api/backtest/optimize/{optimization_id}/cancel

响应:
  optimization_id: "opt-xxxx-xxxx"
  status: "cancelled"
  cancelled_at: 1710000000
  partial_results:
    completed_combinations: 20
    total_combinations: 75
    partial_data_available: true
    message: "已完成 20/75 个组合的计算，可在结果页面查看部分数据"
```

---

## 8. 数据库扩展设计

### 8.1 优化任务表

```sql
-- 参数优化任务表
CREATE TABLE IF NOT EXISTS optimization_tasks (
    optimization_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,

    -- 状态
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | queued | running | completed | failed | cancelled
    progress INTEGER DEFAULT 0,

    -- 基础配置
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    initial_balance REAL NOT NULL,

    -- 优化配置 (JSON)
    parameters_json TEXT NOT NULL,      -- 待优化参数定义
    objective_json TEXT NOT NULL,       -- 优化目标
    constraints_json TEXT,              -- 约束条件
    advanced_json TEXT,                 -- 高级选项

    -- 执行统计
    total_combinations INTEGER,
    completed_combinations INTEGER DEFAULT 0,
    started_at INTEGER,
    completed_at INTEGER,
    duration_seconds INTEGER,

    -- 结果摘要
    best_params_json TEXT,              -- 最优参数
    best_metrics_json TEXT,             -- 最优指标
    analysis_json TEXT,                 -- 分析结果

    -- 错误信息
    error_message TEXT,

    -- 元数据
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    priority TEXT DEFAULT 'normal',

    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_optimization_status ON optimization_tasks(status);
CREATE INDEX idx_optimization_user ON optimization_tasks(user_id);
CREATE INDEX idx_optimization_created ON optimization_tasks(created_at);
```

### 8.2 优化结果明细表

```sql
-- 参数优化结果明细表（每个参数组合一条记录）
CREATE TABLE IF NOT EXISTS optimization_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    optimization_id TEXT NOT NULL,

    -- 参数组合
    params_json TEXT NOT NULL,          -- {"risk_pct": 0.02, "max_sl_dist": 0.03}

    -- 回测指标
    total_return REAL,
    max_drawdown REAL,
    win_rate REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    profit_factor REAL,
    total_trades INTEGER,
    winning_trades INTEGER,
    avg_trade_return REAL,

    -- 样本外验证（如有）
    oos_enabled BOOLEAN DEFAULT FALSE,
    oos_total_return REAL,
    oos_decay_rate REAL,

    -- 稳定性分析
    stability_score REAL,
    sensitivity_score REAL,
    overfitting_risk TEXT,  -- low | medium | high

    -- 执行信息
    backtest_task_id TEXT,
    executed_at INTEGER,
    execution_time_seconds REAL,

    FOREIGN KEY (optimization_id) REFERENCES optimization_tasks(optimization_id)
);

CREATE INDEX idx_opt_result_opt_id ON optimization_results(optimization_id);
CREATE INDEX idx_opt_result_return ON optimization_results(total_return);
```

### 8.3 优化历史对比表

```sql
-- 优化版本对比表（用户手动标记的重要版本）
CREATE TABLE IF NOT EXISTS optimization_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    optimization_id TEXT NOT NULL,

    -- 版本信息
    version_name TEXT,                  -- 用户自定义版本名
    version_tag TEXT,                   -- 标签：production | testing | archived
    is_favorite BOOLEAN DEFAULT FALSE,  -- 是否收藏
    notes TEXT,                         -- 备注

    -- 应用状态
    is_applied BOOLEAN DEFAULT FALSE,   -- 是否已应用到实盘
    applied_at INTEGER,

    created_at INTEGER NOT NULL,

    FOREIGN KEY (optimization_id) REFERENCES optimization_tasks(optimization_id)
);
```

---

## 9. 监控和告警

### 9.1 系统监控指标

```yaml
系统监控指标:
  队列监控:
    - 当前队列长度
    - 平均等待时间
    - 队列积压告警阈值：> 50 任务

  执行监控:
    - 当前并发数
    - 任务完成速率（个/分钟）
    - 平均执行时间
    - 失败率

  资源监控:
    - CPU 使用率
    - 内存使用率
    - 磁盘 I/O

  用户监控:
    - 单用户任务提交频率
    - 异常高频提交检测
    - 配额使用情况
```

### 9.2 告警规则

```yaml
告警规则:
  任务执行失败:
    - 条件：单个优化任务失败率 > 20%
    - 动作：通知运维，暂停新用户提交

  队列积压:
    - 条件：队列长度 > 100 或 等待时间 > 2 小时
    - 动作：通知运维，考虑扩容

  资源耗尽:
    - 条件：内存使用率 > 90%
    - 动作：暂停新任务，清理缓存

  异常访问:
    - 条件：单用户 1 分钟内提交 > 10 个任务
    - 动作：临时限制该用户，发送警告
```

---

## 10. 总结

### 10.1 设计要点回顾

| 设计领域 | 核心方案 |
|---------|---------|
| 参数验证 | 组合数保护 + 时间预估 + 资源检查 |
| 任务队列 | Redis 优先级队列 + 并发限制 |
| 优化目标 | 单目标 / 多目标 / 自定义三模式 |
| 防止过拟合 | 样本外验证 + 参数稳定性分析 |
| 结果管理 | 版本控制 + 对比功能 + 持久化 |

### 10.2 与主设计的关系

```
主设计文档 (fmz_backtest_integration_plan.md)
│
├── 第 7 节：参数优化方案
│   ├── 7.1 网格搜索实现 ← 本设计补充详细验证和队列逻辑
│   └── 7.2 遗传算法优化 ← 本设计补充并发和结果管理
│
└── 本补充设计文档 ← 填充主设计缺失的关键细节
    ├── 参数验证和保护机制
    ├── 任务队列和并发控制
    ├── 优化目标体系
    ├── 防止过拟合机制
    ├── 结果管理和对比
    └── API 详细设计和数据库扩展
```

### 10.3 后续步骤建议

1. **评审本设计文档** - 确认所有边界条件和约束合理
2. **创建实现任务清单** - 基于本设计分解具体开发任务
3. **优先实现核心流程** - 先完成单目标网格搜索 + 基础验证
4. **迭代扩展功能** - 多目标优化、遗传算法等后续添加

---

*文档结束*
