# 技能：严格的六边形架构与领域驱动设计 (DDD)

## 核心目标
你必须使用领域驱动设计 (DDD) 和六边形架构 (端口与适配器) 来编写本系统的每一行代码。保持模块高内聚、低耦合。

## 严格约束规则
1. **依赖倒置原则 (Dependency Rule)**：依赖关系只能由外向内指向。`domain` 层绝对不能导入 `infrastructure` 层或 `application` 层的任何代码。
2. **核心实体先行 (Core Entities)**：任何业务流转的数据，必须首先在 `core/entities.py` 中定义为 `@dataclass`。禁止在模块间传递原始的字典 (Dict) 或 JSON 格式数据。
3. **面向接口编程 (Interface First)**：所有的外部 I/O 操作（数据库读写、API 请求、消息推送）必须在 `core/interfaces.py` 中定义抽象基类 (ABC)。
4. **依赖注入 (Dependency Injection)**：禁止在类内部实例化外部依赖。所有的适配器（如数据库仓储、API 客户端、推送器）必须在 `main.py` 中完成实例化，并通过构造函数注入到 `Engine` 或其他服务中。
5. **职责单一 (Single Responsibility)**：
   - 策略类 (`PinbarStrategy`) 只负责计算 K 线并吐出 `Signal`，绝不能查询数据库或发网络请求。
   - 引擎类 (`SignalMonitorEngine`) 只负责调用和编排顺序，绝不能包含任何数学计算或具体的 HTTP 请求逻辑。