# 风控模块（domain/risk/sizer.py）问题修复方案

**文档版本**: v1.0
**审查日期**: 2026-03-09
**审查范围**: domain/risk/sizer.py 及相关联模块
**修复目标**: 消除严重风控逻辑缺陷，提升系统安全性和可维护性

---

## 一、问题汇总与修复优先级

| 优先级 | 编号 | 问题分类 | 问题简述 | 风险等级 | 预计工时 |
|--------|------|----------|----------|----------|----------|
| **P0** | 3 | 业务逻辑 | 安全垫系数方向错误，放大风险 | 🔴 严重 | 2h |
| **P0** | 4 | 业务逻辑 | 杠杆熔断后风险金额计算错误 | 🔴 严重 | 2h |
| **P1** | 2 | 业务逻辑 | 资金分配逻辑存在漏洞 | 🟠 高 | 4h |
| **P1** | 7 | 技术实现 | 缺少输入参数有效性校验 | 🟠 高 | 2h |
| **P1** | 12 | 架构设计 | 缺少总风险敞口聚合计算 | 🟠 高 | 6h |
| **P2** | 1 | 业务逻辑 | 硬编码持仓上限缺乏灵活性 | 🟡 中 | 3h |
| **P2** | 5 | 业务逻辑 | 缺少仓位价值比例校验 | 🟡 中 | 2h |
| **P2** | 6 | 技术实现 | 注释代码未清理 | 🟡 中 | 0.5h |
| **P3** | 8 | 技术实现 | 浮点数精度问题 | 🟢 低 | 2h |
| **P3** | 9 | 技术实现 | 异常信息非结构化 | 🟢 低 | 2h |
| **P2** | 11 | 架构设计 | 风控参数硬编码在引擎层 | 🟡 中 | 3h |
| **P2** | 10 | 技术实现 | AccountBalance.positions 类型过宽 | 🟡 中 | 2h |

---

## 二、详细修复方案

### P0-问题 3：安全垫系数方向错误（严重）

**问题描述**
当前代码第 76 行：
```python
theoretical_leverage = (notional_value / investment_amount) * 1.05
```
安全垫系数 `1.05` 向上乘，导致计算出的杠杆比实际需求**高 5%**，与"预留安全边际"的初衷相反。

**风险分析**
- 若理论杠杆应为 10x，实际计算为 10.5x
- 在极端行情下，这 5% 的额外杠杆可能导致保证金不足、提前强平

**修复方案**
将安全垫改为**除法**或**增加分母**，确保预留更多保证金：

```python
# 方案 A：除法（推荐）
theoretical_leverage = notional_value / (investment_amount * 1.05)

# 方案 B：调整为可配置的安全垫系数
SAFETY_CUSHION = 1.15  # 类常量，预留 15% 安全边际
theoretical_leverage = notional_value / (investment_amount * SAFETY_CUSHION)
```

**涉及文件**
- `domain/risk/sizer.py` 第 76 行

---

### P0-问题 4：杠杆熔断后风险金额计算错误（严重）

**问题描述**
当前代码第 96 行：
```python
risk_amount = capped_notional_value * signal.sl_distance_pct
```
当杠杆被强制压缩后，`risk_amount` 被重新计算为更小值，但这笔交易的**实际风险敞口**并未改变。

**风险分析**
- 对外暴露的 `risk_amount` 与实际不符
- 后续若有基于 `risk_amount` 的风险聚合计算，将得到错误结果
- 可能导致风险监控系统失真

**修复方案**
保持原始 `risk_amount` 不变，额外添加一个字段记录**压缩后的实际风险**：

```python
# 在 PositionSizing 实体中添加新字段
@dataclass
class PositionSizing:
    signal: Signal
    suggested_leverage: float
    suggested_quantity: float
    investment_amount: float
    risk_amount: float          # 原始理论风险额（基于用户配置的 risk_pct）
    actual_risk_amount: float   # 新增：杠杆压缩后的实际风险额
    leverage_capped: bool       # 新增：是否触发了杠杆熔断
```

```python
# 在 sizer.py 中
original_risk_amount = risk_amount  # 保存原始值
leverage_capped = suggested_leverage > max_leverage

if leverage_capped:
    suggested_leverage = max_leverage
    capped_notional_value = investment_amount * (max_leverage / 1.05)
    suggested_quantity = capped_notional_value / signal.entry_price
    actual_risk_amount = capped_notional_value * signal.sl_distance_pct
else:
    actual_risk_amount = risk_amount

return PositionSizing(
    signal=signal,
    suggested_leverage=suggested_leverage,
    suggested_quantity=suggested_quantity,
    investment_amount=investment_amount,
    risk_amount=original_risk_amount,
    actual_risk_amount=actual_risk_amount,
    leverage_capped=leverage_capped
)
```

**涉及文件**
- `domain/risk/sizer.py` 第 84-96 行
- `core/entities.py` PositionSizing 实体

---

### P1-问题 2：资金分配逻辑漏洞（高）

**问题描述**
当前代码第 48 行：
```python
investment_amount = account.total_wallet_balance / (4 - account.current_positions_count)
```
当已有 3 个持仓时，新仓位将分配到总资金的 100%（`total/1`），但实际可能已有 75% 资金被占用。

**风险分析**
- 违背"分散风险"初衷
- 可能导致单一时点仓位过度集中
- 与"最多 4 个持仓"的风控目标矛盾

**修复方案**
改用**剩余可用资金比例**或**固定比例分配**：

```python
# 方案 A：基于可用余额的固定比例分配（推荐）
MAX_POSITIONS = 4
position_slot_ratio = 1.0 / MAX_POSITIONS  # 每个仓位理论占用 25%
investment_amount = min(
    account.total_wallet_balance * position_slot_ratio,
    account.available_balance  # 不超过实际可用余额
)

# 方案 B：考虑已占用资金的动态分配
occupied_ratio = account.current_positions_count / MAX_POSITIONS
remaining_ratio = 1.0 - occupied_ratio
investment_amount = account.total_wallet_balance * remaining_ratio * 0.9  # 留 10% 缓冲
```

**涉及文件**
- `domain/risk/sizer.py` 第 44-52 行

---

### P1-问题 7：缺少输入参数有效性校验（高）

**问题描述**
`risk_pct` 和 `max_leverage` 参数没有范围校验，危险值可直接传入。

**修复方案**
在 `calculate()` 方法开头添加参数校验：

```python
# 参数有效性校验
if not (0 < risk_pct <= 0.1):
    raise RiskLimitExceeded(f"单笔风险比例必须在 (0, 10%] 范围内，当前：{risk_pct}")

if not (1 <= max_leverage <= 125):
    raise RiskLimitExceeded(f"杠杆倍数必须在 [1, 125] 范围内，当前：{max_leverage}")

if risk_pct <= 0:
    raise RiskLimitExceeded("单笔风险比例必须大于 0")
```

**涉及文件**
- `domain/risk/sizer.py` 第 31-42 行（前置拦截区域）

---

### P1-问题 12：缺少总风险敞口聚合计算（高）

**问题描述**
系统只计算单笔交易的风险，没有聚合所有持仓的总风险敞口。极端行情下，所有持仓可能同时触发止损。

**修复方案**
新增 `PortfolioRiskService` 服务，计算聚合风险：

```python
# 新增文件：domain/risk/portfolio_risk.py
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class PortfolioRiskMetrics:
    total_risk_amount: float      # 所有持仓的总风险额
    total_risk_pct: float         # 总风险占账户比例
    max_single_loss_pct: float    # 最大单笔损失比例
    correlation_adjusted_risk: float  # 相关性调整后风险（简化版可暂不实现）

class PortfolioRiskService:
    """投资组合风险聚合服务"""

    def calculate_portfolio_risk(
        self,
        positions: List[Dict],
        total_wallet_balance: float
    ) -> PortfolioRiskMetrics:
        """计算投资组合的聚合风险指标"""
        total_risk = sum(pos.get('risk_amount', 0) for pos in positions)
        total_risk_pct = total_risk / total_wallet_balance if total_wallet_balance > 0 else 0

        max_single_risk = max((pos.get('risk_amount', 0) for pos in positions), default=0)
        max_single_loss_pct = max_single_risk / total_wallet_balance if total_wallet_balance > 0 else 0

        return PortfolioRiskMetrics(
            total_risk_amount=total_risk,
            total_risk_pct=total_risk_pct,
            max_single_loss_pct=max_single_loss_pct,
            correlation_adjusted_risk=total_risk  # 简化版
        )

    def check_portfolio_limit(
        self,
        metrics: PortfolioRiskMetrics,
        max_portfolio_risk_pct: float = 0.08  # 默认总风险不超过 8%
    ) -> bool:
        """检查投资组合风险是否超限"""
        return metrics.total_risk_pct <= max_portfolio_risk_pct
```

**在 monitor_engine 中的集成**：
```python
# 在算仓前检查总风险敞口
portfolio_risk_service = PortfolioRiskService()
current_risk_metrics = portfolio_risk_service.calculate_portfolio_risk(
    positions=account_balance.positions,
    total_wallet_balance=account_balance.total_wallet_balance
)

if not portfolio_risk_service.check_portfolio_limit(current_risk_metrics):
    logger.warning(f"投资组合总风险超限：{current_risk_metrics.total_risk_pct:.2%}")
    continue  # 跳过此信号
```

**涉及文件**
- 新增：`domain/risk/portfolio_risk.py`
- 修改：`application/monitor_engine.py`

---

### P2-问题 1：硬编码持仓上限缺乏灵活性（中）

**问题描述**
`if account.current_positions_count >= 4` 硬编码了最大持仓笔数。

**修复方案**
将上限移至 `RiskConfig` 配置实体：

```python
# core/entities.py
@dataclass
class RiskConfig:
    risk_pct: float
    max_sl_dist: float
    max_leverage: float
    max_positions: int = 4  # 新增：最大持仓笔数（可配置）
    max_portfolio_risk_pct: float = 0.08  # 新增：投资组合最大风险比例
```

```python
# domain/risk/sizer.py
def calculate(
    self,
    signal: Signal,
    account: AccountBalance,
    risk_pct: float,
    max_leverage: float,
    max_positions: int = 4  # 新增参数
) -> PositionSizing:
    # 使用传入参数而非硬编码
    if account.current_positions_count >= max_positions:
        raise RiskLimitExceeded(f"当前持仓笔数已达上限 ({account.current_positions_count}>={max_positions})")
```

**涉及文件**
- `core/entities.py` RiskConfig 实体
- `domain/risk/sizer.py` calculate 方法签名
- `application/monitor_engine.py` 调用处

---

### P2-问题 5：缺少仓位价值比例校验（中）

**问题描述**
当止损距离很小时，计算出的名义价值可能是账户总额的数倍。

**修复方案**
添加仓位价值上限校验：

```python
# 添加最大仓位价值比例常量
MAX_POSITION_VALUE_RATIO = 3.0  # 单个仓位名义价值不超过账户总额的 3 倍

# 在计算 notional_value 后添加校验
max_allowed_notional = account.total_wallet_balance * MAX_POSITION_VALUE_RATIO
if notional_value > max_allowed_notional:
    # 压缩至上限
    notional_value = max_allowed_notional
    suggested_quantity = notional_value / signal.entry_price
    logger.warning(f"仓位价值超限，已压缩至{MAX_POSITION_VALUE_RATIO}倍账户总额")
```

**涉及文件**
- `domain/risk/sizer.py` 第 69-72 行后

---

### P2-问题 6：注释代码未清理（中）

**问题描述**
第 51-52 行有被注释的保护性代码，未说明原因。

**修复方案**
经分析，该逻辑应与 P1-问题 2 一同修复。修复后删除注释代码，替换为正式实现：

```python
# 删除：
# if investment_amount > account.available_balance:
#    investment_amount = account.available_balance

# 替换为正式实现（见 P1-问题 2 修复方案）
investment_amount = min(
    account.total_wallet_balance / (MAX_POSITIONS - account.current_positions_count),
    account.available_balance
)
```

**涉及文件**
- `domain/risk/sizer.py` 第 51-52 行

---

### P2-问题 11：风控参数硬编码在引擎层（中）

**问题描述**
`monitor_engine.py` 中硬编码了 `self.risk_pct = 0.02` 等参数。

**修复方案**
从 `SystemConfig` 或数据库动态加载：

```python
# application/monitor_engine.py __init__ 方法
# 移除硬编码，改为从配置加载
self.risk_pct = risk_config.risk_pct if risk_config else 0.02
self.max_sl_dist = risk_config.max_sl_dist if risk_config else 0.035
self.max_leverage = risk_config.max_leverage if risk_config else 20.0
self.max_positions = risk_config.max_positions if risk_config else 4
```

```python
# main.py 依赖注入处
from core.entities import RiskConfig

# 从数据库加载配置
risk_config = await repo.get_risk_config()  # 假设有此方法
# 或使用默认值
risk_config = RiskConfig(risk_pct=0.02, max_sl_dist=0.035, max_leverage=20.0, max_positions=4)

risk_sizer = PositionSizer()
engine = CryptoRadarEngine(
    ...
    risk_config=risk_config,  # 传入配置
    ...
)
```

**涉及文件**
- `application/monitor_engine.py`
- `main.py`
- `web/api.py`（配置读取接口）

---

### P3-问题 8：浮点数精度问题（低）

**问题描述**
大量浮点数运算未考虑精度损失。

**修复方案**
使用 `decimal.Decimal` 进行关键计算：

```python
from decimal import Decimal, ROUND_DOWN

# 关键计算使用 Decimal
def calculate(...):
    ...
    # 使用 Decimal 进行精确计算
    risk_amount_decimal = Decimal(str(account.total_wallet_balance)) * Decimal(str(risk_pct))
    notional_value_decimal = risk_amount_decimal / Decimal(str(signal.sl_distance_pct))

    # 转换回 float 并保留合理精度
    risk_amount = float(risk_amount_decimal.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    suggested_quantity = float((notional_value_decimal / Decimal(str(signal.entry_price))).quantize(Decimal('0.0001'), rounding=ROUND_DOWN))
```

**涉及文件**
- `domain/risk/sizer.py`

---

### P3-问题 9：异常信息非结构化（低）

**问题描述**
`RiskLimitExceeded` 仅返回字符串，调用方难以判断具体规则。

**修复方案**
添加异常类型细分和错误码：

```python
# core/exceptions.py
from enum import Enum

class RiskErrorCode(Enum):
    POSITION_LIMIT_EXCEEDED = "POSITION_LIMIT_EXCEEDED"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVALID_STOP_LOSS = "INVALID_STOP_LOSS"
    LEVERAGE_LIMIT_EXCEEDED = "LEVERAGE_LIMIT_EXCEEDED"
    PORTFOLIO_RISK_EXCEEDED = "PORTFOLIO_RISK_EXCEEDED"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"

class RiskLimitExceeded(Exception):
    def __init__(self, message: str, error_code: RiskErrorCode = None, context: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}

    def to_dict(self) -> dict:
        return {
            "message": str(self),
            "error_code": self.error_code.value if self.error_code else None,
            "context": self.context
        }

# 使用示例
raise RiskLimitExceeded(
    f"当前持仓笔数已达上限",
    error_code=RiskErrorCode.POSITION_LIMIT_EXCEEDED,
    context={"current": account.current_positions_count, "max": max_positions}
)
```

**涉及文件**
- `core/exceptions.py`
- `domain/risk/sizer.py` 所有 `raise` 语句

---

### P3-问题 10：AccountBalance.positions 类型过宽（中）

**问题描述**
`positions: List[Dict[str, float]]` 类型过于宽松。

**修复方案**
定义明确的 `Position` 实体：

```python
# core/entities.py
@dataclass
class Position:
    symbol: str
    side: str           # "LONG" | "SHORT"
    size: float         # 持仓数量
    entry_price: float  # 入场价
    mark_price: float   # 标记价格
    leverage: float     # 杠杆倍数
    unrealized_pnl: float
    risk_amount: float  # 该仓位的风控风险额
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

@dataclass
class AccountBalance:
    total_wallet_balance: float
    available_balance: float
    current_positions_count: int
    total_balance: float = 0.0
    available_margin: float = 0.0
    total_unrealized_pnl: float = 0.0
    positions: List[Position] = field(default_factory=list)  # 使用强类型
```

**涉及文件**
- `core/entities.py`
- `infrastructure/reader/binance_api.py`（需适配返回格式）

---

## 三、修复后代码结构

### sizer.py 完整重构预览

```python
"""
风控算仓大脑模块 (Domain 层)
严格按照 PRD 计算风险敞口、分配开仓本金并推算安全杠杆与开仓数量。
此模块为纯数学运算，没有任何网络请求或实际下单动作！
"""
from decimal import Decimal, ROUND_DOWN
from typing import Tuple
from core.entities import Signal, AccountBalance, PositionSizing
from core.exceptions import RiskLimitExceeded, RiskErrorCode

# ============= 风控常量配置 =============
DEFAULT_MAX_POSITIONS = 4
DEFAULT_MAX_POSITION_VALUE_RATIO = 3.0  # 单仓位名义价值上限 / 账户总额
DEFAULT_SAFETY_CUSHION = 1.15           # 安全垫系数（预留 15% 保证金）
DEFAULT_MAX_PORTFOLIO_RISK_PCT = 0.08   # 投资组合总风险上限 8%


class PositionSizer:
    """风控仓位计算器
    严格遵守 Zero Execution 的红线规则。仅用于推算开仓建议，保护本金安全。
    """

    def calculate(
        self,
        signal: Signal,
        account: AccountBalance,
        risk_pct: float,
        max_leverage: float,
        max_positions: int = DEFAULT_MAX_POSITIONS,
        max_position_value_ratio: float = DEFAULT_MAX_POSITION_VALUE_RATIO,
        safety_cushion: float = DEFAULT_SAFETY_CUSHION,
    ) -> PositionSizing:
        """
        根据当前账户快照和风控配置对有效信号进行杠杆和算仓建议计算。

        :param signal: 策略引擎生成的有效信号快照
        :param account: 从交易所实时只读获取到的账户余额与持仓笔数
        :param risk_pct: 单笔最大承受风险比例（如 0.02 表示 2%）
        :param max_leverage: 系统允许的最高杠杆倍数（如 20.0）
        :param max_positions: 最大持仓笔数上限
        :param max_position_value_ratio: 单仓位名义价值上限 / 账户总额
        :param safety_cushion: 安全垫系数（>1.0，值越大越保守）
        :return: 推算出的包含杠杆及数量的 PositionSizing 实体。
        :raises RiskLimitExceeded: 在前置拦截条件不满足时抛出异常。
        """

        # ==========================================
        # 1. 参数有效性校验
        # ==========================================
        self._validate_parameters(risk_pct, max_leverage, max_positions, safety_cushion)

        # ==========================================
        # 2. 前置拦截规则 (Pre-flight checks)
        # ==========================================
        self._check_position_limit(account, max_positions)
        self._check_account_balance(account)
        self._check_signal_stop_loss(signal)

        # ==========================================
        # 3. 本金分配计算 (Capital Allocation)
        # ==========================================
        investment_amount = self._calculate_investment_amount(account, max_positions)

        # ==========================================
        # 4. 风险及止损测算 (Risk Assessment)
        # ==========================================
        original_risk_amount = self._calculate_risk_amount(account, risk_pct)

        # ==========================================
        # 5. 计算仓位与杠杆 (Position & Leverage Calculation)
        # ==========================================
        notional_value = self._calculate_notional_value(original_risk_amount, signal.sl_distance_pct)

        # 仓位价值上限校验
        notional_value = self._cap_notional_value(notional_value, account, max_position_value_ratio)

        suggested_quantity = self._calculate_quantity(notional_value, signal.entry_price)
        theoretical_leverage = self._calculate_leverage(notional_value, investment_amount, safety_cushion)

        # ==========================================
        # 6. 杠杆熔断自适应 (Leverage Cap & Auto-Scaling)
        # ==========================================
        suggested_leverage, actual_risk_amount, leverage_capped = self._apply_leverage_cap(
            theoretical_leverage, max_leverage, investment_amount,
            notional_value, signal, safety_cushion
        )

        # ==========================================
        # 7. 生成安全算仓结果并返回
        # ==========================================
        return PositionSizing(
            signal=signal,
            suggested_leverage=suggested_leverage,
            suggested_quantity=suggested_quantity,
            investment_amount=investment_amount,
            risk_amount=original_risk_amount,
            actual_risk_amount=actual_risk_amount,
            leverage_capped=leverage_capped
        )

    def _validate_parameters(self, risk_pct: float, max_leverage: float,
                            max_positions: int, safety_cushion: float) -> None:
        """参数有效性校验"""
        if not (0 < risk_pct <= 0.1):
            raise RiskLimitExceeded(
                f"单笔风险比例必须在 (0, 10%] 范围内",
                error_code=RiskErrorCode.INVALID_PARAMETERS,
                context={"risk_pct": risk_pct}
            )
        if not (1 <= max_leverage <= 125):
            raise RiskLimitExceeded(
                f"杠杆倍数必须在 [1, 125] 范围内",
                error_code=RiskErrorCode.INVALID_PARAMETERS,
                context={"max_leverage": max_leverage}
            )
        if max_positions < 1:
            raise RiskLimitExceeded(
                f"最大持仓笔数必须 >= 1",
                error_code=RiskErrorCode.INVALID_PARAMETERS,
                context={"max_positions": max_positions}
            )
        if safety_cushion < 1.0:
            raise RiskLimitExceeded(
                f"安全垫系数必须 >= 1.0",
                error_code=RiskErrorCode.INVALID_PARAMETERS,
                context={"safety_cushion": safety_cushion}
            )

    def _check_position_limit(self, account: AccountBalance, max_positions: int) -> None:
        """持仓笔数上限检查"""
        if account.current_positions_count >= max_positions:
            raise RiskLimitExceeded(
                f"当前持仓笔数已达上限 ({account.current_positions_count}>={max_positions})",
                error_code=RiskErrorCode.POSITION_LIMIT_EXCEEDED,
                context={"current": account.current_positions_count, "max": max_positions}
            )

    def _check_account_balance(self, account: AccountBalance) -> None:
        """账户余额检查"""
        if account.total_wallet_balance <= 0:
            raise RiskLimitExceeded(
                "账户余额不足或已穿仓",
                error_code=RiskErrorCode.INSUFFICIENT_BALANCE,
                context={"total_wallet_balance": account.total_wallet_balance}
            )
        if account.available_balance <= 0:
            raise RiskLimitExceeded(
                "可用余额不足",
                error_code=RiskErrorCode.INSUFFICIENT_BALANCE,
                context={"available_balance": account.available_balance}
            )

    def _check_signal_stop_loss(self, signal: Signal) -> None:
        """信号止损检查"""
        if signal.sl_distance_pct <= 0:
            raise RiskLimitExceeded(
                "信号自带的止损百分比距离无效或小于零",
                error_code=RiskErrorCode.INVALID_STOP_LOSS,
                context={"sl_distance_pct": signal.sl_distance_pct}
            )

    def _calculate_investment_amount(self, account: AccountBalance, max_positions: int) -> float:
        """计算分配给本笔交易的本金"""
        position_slot_ratio = Decimal('1.0') / Decimal(str(max_positions))
        theoretical_amount = Decimal(str(account.total_wallet_balance)) * position_slot_ratio

        # 使用 Decimal 精确比较
        available = Decimal(str(account.available_balance))
        investment = min(theoretical_amount, available)

        return float(investment.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))

    def _calculate_risk_amount(self, account: AccountBalance, risk_pct: float) -> float:
        """计算风险金额"""
        risk = Decimal(str(account.total_wallet_balance)) * Decimal(str(risk_pct))
        return float(risk.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))

    def _calculate_notional_value(self, risk_amount: float, sl_distance_pct: float) -> float:
        """计算名义价值"""
        notional = Decimal(str(risk_amount)) / Decimal(str(sl_distance_pct))
        return float(notional.quantize(Decimal('0.01'), rounding=ROUND_DOWN))

    def _cap_notional_value(self, notional_value: float, account: AccountBalance,
                           max_ratio: float) -> float:
        """仓位价值上限校验"""
        max_allowed = Decimal(str(account.total_wallet_balance)) * Decimal(str(max_ratio))
        if Decimal(str(notional_value)) > max_allowed:
            return float(max_allowed.quantize(Decimal('0.01'), rounding=ROUND_DOWN))
        return notional_value

    def _calculate_quantity(self, notional_value: float, entry_price: float) -> float:
        """计算开仓数量"""
        quantity = Decimal(str(notional_value)) / Decimal(str(entry_price))
        return float(quantity.quantize(Decimal('0.001'), rounding=ROUND_DOWN))

    def _calculate_leverage(self, notional_value: float, investment_amount: float,
                           safety_cushion: float) -> float:
        """计算理论杠杆"""
        leverage = Decimal(str(notional_value)) / (Decimal(str(investment_amount)) * Decimal(str(safety_cushion)))
        return float(leverage.quantize(Decimal('0.01'), rounding=ROUND_DOWN))

    def _apply_leverage_cap(self, theoretical_leverage: float, max_leverage: float,
                           investment_amount: float, notional_value: float,
                           signal: Signal, safety_cushion: float) -> Tuple[float, float, bool]:
        """应用杠杆熔断"""
        leverage_capped = theoretical_leverage > max_leverage

        if leverage_capped:
            suggested_leverage = max_leverage
            # 反推压缩后的名义价值
            capped_notional = (Decimal(str(investment_amount)) * Decimal(str(max_leverage))) / Decimal(str(safety_cushion))
            actual_risk = capped_notional * Decimal(str(signal.sl_distance_pct))
            suggested_quantity = capped_notional / Decimal(str(signal.entry_price))

            return (
                max_leverage,
                float(actual_risk.quantize(Decimal('0.000001'), rounding=ROUND_DOWN)),
                True
            )
        else:
            return (
                theoretical_leverage,
                notional_value * signal.sl_distance_pct,  # 原始风险额
                False
            )
```

---

## 四、实施计划

### 阶段一：核心缺陷修复（P0，预计 4 小时）
- [ ] 修复安全垫系数方向错误（问题 3）
- [ ] 修复杠杆熔断后风险金额计算（问题 4）
- [ ] 单元测试验证

### 阶段二：高风险问题修复（P1，预计 12 小时）
- [ ] 修复资金分配逻辑（问题 2）
- [ ] 添加输入参数校验（问题 7）
- [ ] 实现投资组合风险聚合服务（问题 12）
- [ ] 集成到监控引擎

### 阶段三：中低风险问题修复（P2-P3，预计 12 小时）
- [ ] 配置化持仓上限（问题 1）
- [ ] 添加仓位价值比例校验（问题 5）
- [ ] 清理注释代码（问题 6）
- [ ] 浮点数精度处理（问题 8）
- [ ] 异常结构化（问题 9）
- [ ] 强类型化 Position 实体（问题 10）
- [ ] 引擎层配置解耦（问题 11）

### 阶段四：测试与验证（预计 8 小时）
- [ ] 单元测试覆盖率达到 90%+
- [ ] 边界条件测试
- [ ] 集成测试
- [ ] 回归测试

---

## 五、验收标准

### 1. 功能验收
- [ ] 所有 P0/P1 问题已修复并通过测试
- [ ] 安全垫系数方向正确（除法而非乘法）
- [ ] 杠杆熔断后风险金额准确反映实际情况

### 2. 代码质量验收
- [ ] 无硬编码魔法数字
- [ ] 所有公共方法有类型注解
- [ ] 关键计算使用 Decimal 保证精度

### 3. 测试验收
- [ ] 单元测试覆盖率 ≥ 90%
- [ ] 边界条件测试全部通过
- [ ] 无回归缺陷

### 4. 文档验收
- [ ] 修复方案已更新到代码注释
- [ ] 变更日志已记录

---

## 六、风险评估

| 风险项 | 可能性 | 影响 | 缓解措施 |
|--------|--------|------|----------|
| 修复引入新 bug | 中 | 高 | 充分单元测试 + 回归测试 |
| 与现有逻辑不兼容 | 低 | 中 | 小步提交，逐步验证 |
| 性能下降（Decimal） | 低 | 低 | 性能测试验证，必要时热点优化 |

---

## 七、审批签字

| 角色 | 姓名 | 日期 | 意见 |
|------|------|------|------|
| 技术负责人 | | | |
| 风控负责人 | | | |
| 开发负责人 | | | |
