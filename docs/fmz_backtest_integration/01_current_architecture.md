# 量化回测系统 - 当前架构 (Current Architecture)

## 1. 系统定位与演进状态 (v2.0)
目前系统已打通从 **API 接口** -> **后台多进程队列** -> **FMZ C++ 沙盒执行** -> **前端轻量级图表展示** 的主干流程。当前版本 (v2.0) 的核心设计选择是：
- 废弃了不可靠的纯 Python 手写撮合计算引擎。
- 原生使用 FMZ `VCtx` 核心虚拟底层引擎进行无损耗数据读取。
- 目前核心处于纯现货 (`Spot`) 业务测试级别。

## 2. 核心架构拓扑
### 2.1 Web UI & API 层
- **前端栈**: React + Vite + Tailwind + Shadcn UI
- **BacktestLab 组件**: 提交回测参数配置页（品种、起止时间、本金、划点与 Pinbar 细节指标设定）。
- **FastAPI 接口**: 
  - `POST /api/backtest/run` (新建任务)
  - `GET /api/backtest/tasks` (轮询列表)
  - `GET /api/backtest/task/{taskId}/result` (调出完成的结果)

### 2.2 任务调度与并发隔离 (Service Layer)
- **多进程隔离 (ProcessPoolExecutor)**: 
  FMZ 的底层 C++ 引擎（特别是 `exchange.GetRecords()`）在处理超大周期时是一个重度阻塞 CPU 密集型操作。为防止直接拖垮主系统实盘的 FastAPI asyncio 协程池，回测服务被严格下放到了完全独立的系统级进程池内并发执行。
- **任务状态机管控**: 在主程序的内存 / SQLite 管控任务的生命周期：`pending` -> `running` -> `completed` / `failed`。

### 2.3 执行引擎与大脑 (Execution Engine)
- **FMZStrategyRunner (`_execute_fmz_backtest_worker`)**:
  - 利用底层被注入到 Globals 的 `exchange` 指针，通过 `while True` 主循环，原生态抓取引擎推进的历史 K 线。
  - **组件完全复用**: 系统并未为了回测写第二套策略逻辑，而是用一层很薄的格式转化壳，把抓出来的历史 K 线适配给现网主用大脑 `PinbarStrategy.evaluate()` 处理信号。
  - 根据该无状态大脑的指令，抛出 `exchange.Buy() / exchange.Sell()`。
- **FMZResultParser**: 
  - 从 `task.Join()` 执行结束后的海量 JSON 字符中，去粗取精，分离和计算出供前台绘制的 `equityCurve` / `TradeLogs` / `Stats`。

## 3. 当前架构下存在的局限性 (Technical Debt)
1. **受限的现货原语**: 依然在采用原始纯正负库存的买卖（全仓比例重仓 `risk_amount = balance*0.1`进出）。缺乏对保证金隔离占用计算、动态 1-125x 杠杆做空（Perpetual Contract）的能力支持。
2. **可视化盲盒**: 前端只实现了轻量图表（lightweight-charts）里自带的资金面积图层 (AreaSeries)，但并未能将真实的加密货币行情 K 线载入渲染，也没法直观排查到底是在哪根针尖进的出。
3. **无验证/无优化深层体系**: 停留在“单次回测”的手动阶段。尚未实现能防过拟合（Out-Of-Sample, 样本外前向分析）、尚未实装能自动寻找夏普高点解的网格调度器。
