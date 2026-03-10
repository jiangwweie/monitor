# FMZ 回测框架集成方案

## 文档信息

- **版本**: v2.0
- **修订内容**: 基于 FMZ Python 原生回测引擎 (VCtx) 的重构版本，剔除手工编写的模拟器。
- **状态**: 方案修订版

---

## 1. 执行摘要

### 1.1 项目背景

本项目旨在将现有的加密货币信号监测系统（monitor）与 FMZ 回测框架进行深度集成，使系统具备：
1. **历史策略回测**能力 - 验证 Pinbar 策略在不同市场阶段的表现
2. **参数优化**能力 - 自动寻找最优策略参数组合
3. **模拟交易**能力 - 在实盘前进行纸面推演

### 1.2 核心价值

| 当前能力 | 集成后新增能力 |
|---------|---------------|
| 实时信号监测 | 历史策略回测 |
| 信号入库记录 | 绩效统计分析 |
| 手动参数调整 | 自动化参数优化 |
| 只读信号推送 | 模拟交易验证 |

### 1.3 集成策略 (v2.0 升级版)

采用**原生 FMZ C++ 回测引擎为基底** + **Monitor 策略评价组件为逻辑内核**的双核驱动：
- **不修改**现有实时监控引擎的核心逻辑（完全物理隔离）。
- **完全复用**现有的 `PinbarStrategy.evaluate()` 作为 K 线计算大脑。
- **废弃**手工编写的低效 `AccountSimulator`。
- **引入**强大的 FMZ 原生 `VCtx` (Virtual Context) 对象，直接接管订单撮合、滑点计算、手续费统计和资金曲线生成，性能百倍提升。

---

## 2. 架构对比与重构分析

### 2.1 现有系统与 FMZ 回测引擎的融合点

FMZ 的 Python 本地引擎 (`backtest_python` 包) 提供了一个全局魔术对象 `exchange`，在这个上下文中跑回测，就好比真正在跑 FMZ 实盘机器人。

| 模块目标 | 之前 (v1.0 拟定) 的设计误区 | 现在 (v2.0 优化) 的设计方向 |
|------|-----------------------|-----------------------|
| 撮合与账户 | 手撸 `AccountSimulator` | FMZ `exchange` 原生 C++ 底层处理 |
| 数据流获取 | 自己调 API 拼接循环 | FMZ `exchange.GetRecords()` |
| 代码执行 | asyncio 事件循环内单线程阻塞 | **多独立进程 (ProcessPoolExecutor)** 完全隔离 |
| 结果分析 | 繁琐的代码组装 `equity_curve` | 调用 `task.Join()` 获取丰富的官方 JSON 数据字典 |

### 2.2 重构后的集成架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                         Web UI / API                             │
│         Dashboard | SignalRadar | BacktestLab | OptimizeLab      │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼  RESTful
┌──────────────────────────────────────────────────────────────────┐
│                       FastAPI Routes                             │
│  接收请求 (回测参数/品种/时间区间) -> 推入任务队列                     │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Application Manager                            │
│           BacktestService (管理数据库状态、管理进程池/队列)             │
└──────────────────────────────────────────────────────────────────┘
                                │  派发给多进程 Worker 执行，避免阻塞主引擎
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│            [ 独立 Python Process/Worker ] - FMZStrategyRunner    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 1. 初始化 `task = VCtx(config)` (FMZ 底层 C++ 引擎接管上下文) │ │
│  │                                                             │ │
│  │ 2. while True:                                              │ │
│  │    records = exchange.GetRecords()                          │ │
│  │    bars = fmz_records_to_bars(records)  ← 核心适配器         │ │
│  │    signal = PinbarStrategy.evaluate(bars) ← 复用业务大脑      │ │
│  │    if signal: exchange.Buy() / exchange.Sell()              │ │
│  │                                                             │ │
│  │ 3. 结束循环，提取结果：result_dict = task.Join()             │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                                │   提取原生数据并转化
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│            FMZResultParser (抽取 ProfitLogs/Snapshort)            │
│            持久化入库 SQLite -> 供前端图表渲染                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心机制实现设计

### 3.1 核心组件：`FMZStrategyRunner`

这个类必须运行在单独的进程中（因为 `VCtx` 及 `exchange.GetRecords()` 在无新数据时可能会阻塞，且是计算密集型）。

```python
"""
回测运行器：在独立进程中拉起 FMZ VCtx 上下文，跑完后返回结果。
"""
from fmz import *
from domain.strategy.pinbar import PinbarStrategy
from infrastructure.backtest.fmz_adapter import fmz_records_to_bars

def execute_fmz_backtest(config_string: str, strategy_config: dict) -> dict:
    """
    进程池执行函数。
    :param config_string: 类似 '''backtest start: 2024-01-01 end: 2024-02-01 ... '''
    :param strategy_config: PinbarStrategy 的具体配置字典
    """
    # 1. 启动 C++ 底层虚拟上下文
    task = VCtx(config_string)
    
    # 2. 实例化我们自己的策略大脑
    strategy = PinbarStrategy(...)
    
    # 3. 回测主循环
    while True:
        records = exchange.GetRecords()
        if not records:
            break
            
        # 数据转换 (轻量级)
        bars_history = fmz_records_to_bars(records[:-1], is_closed=True)
        current_bar = fmz_records_to_bars([records[-1]], is_closed=True)[0]
        
        # 让 monitor 的领域大脑进行判定
        signal = strategy.evaluate(
            current_bar=current_bar,
            history_bars=bars_history,
            max_sl_dist=strategy_config.get("max_sl_dist", 0.035)
        )
        
        # 命中信号，转换成 FMZ 原生动作
        if signal:
            account = exchange.GetAccount()
            trade_amount = (account['Balance'] * 0.1) / current_bar.close 
            
            if signal.direction == 'LONG':
                exchange.Buy(current_bar.close, trade_amount)
            else:
                exchange.Sell(current_bar.close, trade_amount)
                
    # 4. 回收结果
    result_dict = task.Join()
    return result_dict
```

### 3.2 提取结果：`FMZResultParser`

`task.Join()` 返回的字典极度丰富。解析器将专注提取以下数据：
1. **净值权益图 (Equity Curve)**：提取 JSON 字典中的 `ProfitLogs`。
2. **胜率与基本统计**：遍历 `task.Join()['RuntimeLogs']` 里自己打的 `Log`，结合 `Profit` 提取。

---

## 4. 后续需重写细化的子设计文档

1. **`03_api_detailed_design.md`**：需要在 JSON Request 中允许客户端设定滑点 (`SlipPoint`)、手续费 (`FeeMaker`/`FeeTaker`)，由后端拼接成 `config_string` 模板丢给 `VCtx`。
2. **`04_out_of_sample_validation.md`** (样本外验证)：只需在同一进程连续调两次 `execute_fmz_backtest`，第一次跑训练集，第二次跑测试集对比收益衰减。
3. **`05_result_comparison.md`**：直接对接 `FMZResultParser` 从 `ProfitLogs` 和 `Snapshort` 里抽取的内容。

---

## 5. 实施阶段与优先级调整

| 阶段 | 核心任务 | 难度评价 |
|------|-----------|---------|
| **Phase 1: FMZ 基建打通 (P0)** | 安装 `fmz` 包。<br>写一个单独的离线脚本证明跑通。 | 极高回报，只需 1 天证明可行性。 |
| **Phase 2: 进程池与服务 (P0)** | FastAPI 调用 `ProcessPoolExecutor`，结果存入 SQLite。| 保证回测不阻塞实时信号。 |
| **Phase 3: 止盈止损映射 (P1)** | Monitor 的 `Signal` 止盈止损转为 `exchange.SetStopLoss` | 必须保证逻辑和实盘一致。 |
| **Phase 4: G.A. 算法与优化 (P2)** | 在这个基座上加循环进行网格搜素/遗传算法。 | 调参层的纯粹业务。 |

*文档结束*
