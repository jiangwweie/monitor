"""
核心实体模块
本模块仅允许引用标准库，提供纯粹的数据载体，绝不能包含任何业务逻辑、网络请求或持久化代码。
严格遵守无第三方依赖原则。
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum

@dataclass
class PinbarConfig:
    """Pinbar 策略形态识别参数"""
    body_max_ratio: float = 0.25           # 实体最大比例 (实体/全长)
    shadow_min_ratio: float = 2.5          # 影线最小比例 (影线/实体)
    volatility_atr_multiplier: float = 1.2 # 波幅 ATR 乘数过滤
    doji_threshold: float = 0.05           # 十字星阈值 (实体/全长 < 5% 视为十字星)
    doji_shadow_bonus: float = 0.6         # 十字星影线比例放宽系数 (2.5 * 0.6 = 1.5)
    mtf_trend_filter_mode: str = "soft"    # MTF 趋势过滤模式："soft"(降分) | "hard"(直接拒绝)
    dynamic_sl_enabled: bool = True        # 是否启用动态止损阈值
    dynamic_sl_base: float = 0.035         # 动态止损基准值 (3.5%)
    dynamic_sl_atr_multiplier: float = 0.5 # ATR 对止损的贡献系数
    atr_volatility_lookback: int = 20      # ATR 波动率回溯周期
    shape_divergence_penalty: int = 20     # 形态-趋势背离扣分 (形态方向与EMA趋势方向相反时)

@dataclass
class Bar:
    """K线实体
    系统内所有涉及K线数据的标准载体。
    """
    symbol: str
    interval: str    # 时间级别 (如 "15m", "1h")
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool  # 仅处理 is_closed=True 的K线

@dataclass
class AccountBalance:
    """账户资产实体
    表示从交易所获取的真实账户只读状态。
    """
    total_wallet_balance: float
    available_balance: float
    current_positions_count: int  # 现有的持仓笔数（n）
    total_balance: float = 0.0 # 账户总资金
    available_margin: float = 0.0 # 可用保证金
    total_unrealized_pnl: float = 0.0 # 总计未实现盈亏
    positions: List[Dict[str, float]] = field(default_factory=list) # 持仓列表, 包括 unrealized_pnl

@dataclass
class PositionDetail:
    """实盘持仓详情实体
    用于展示单个币种的深度持仓信息和风控挂单状态
    """
    symbol: str
    direction: str              # "LONG" / "SHORT"
    leverage: float             # 杠杆倍数
    quantity: float             # 持仓数量
    entry_price: float          # 入场均价
    position_value: float       # 仓位价值
    unrealized_pnl: float       # 未实现盈亏
    open_time: int              # 开单时间戳
    status: str = "OPEN"        # 持仓状态
    take_profit_price: Optional[float] = None    # 止盈价格
    take_profit_order_id: Optional[str] = None   # 止盈单号
    stop_loss_price: Optional[float] = None      # 止损价格
    stop_loss_order_id: Optional[str] = None     # 止损单号

class TradingPair(str, Enum):
    """支持的交易对枚举"""
    BTCUSDT = "BTCUSDT"
    ETHUSDT = "ETHUSDT"
    SOLUSDT = "SOLUSDT"
    BNBUSDT = "BNBUSDT"

@dataclass
class ScoringWeights:
    """打分权重实体
    用于动态加权评分引擎。约束：w_shape + w_trend + w_vol == 1.0 (由外围或 Pydantic 效验)
    """
    w_shape: float
    w_trend: float
    w_vol: float

@dataclass
class Signal:
    """信号快照实体
    策略引擎产生的有效信号快照。
    """
    symbol: str            # 推荐使用 TradingPair.value，但为了向下兼容这里保持 str，可在 Pydantic 中校验
    interval: str          # 时间级别 (如 "15m", "1h", "4h", "1d")
    direction: str         # "LONG" 或 "SHORT"
    entry_price: float
    stop_loss: float
    take_profit_1: float
    timestamp: int
    reason: str            # 命中理由
    sl_distance_pct: float # 止损距离百分比
    score: int = 0         # 信号得分 (0-100)
    score_details: Dict[str, float] = field(default_factory=dict) # 打分详情维度
    shadow_ratio: float = 0.0 # 影线占比
    ema_distance: float = 0.0 # EMA 距离
    volatility_atr: float = 0.0 # ATR 波动率
    source: str = "realtime"   # 信号来源: "realtime" (实时监控) | "history_scan" (历史回扫)
    is_contrarian: bool = False # 是否为逆势信号 (MTF soft 模式下)
    is_shape_divergent: bool = False # 是否为形态与趋势背离信号
    quality_tier: str = "B"  # 信号质量分级："A" (精品) | "B" (普通) | "C" (观察)
    id: Optional[int] = None  # 数据库 ID（可选，仅查询时使用）

@dataclass
class PositionSizing:
    """风控算仓建议实体
    基于风控参数和账户真实余额推算的只读建议。
    这里仅仅是“建议”而非“指令”，严格遵循 Zero Execution 约束。
    """
    signal: Signal
    suggested_leverage: float  # 建议杠杆，受限于 max_leverage
    suggested_quantity: float  # 建议开仓数量
    investment_amount: float   # 最后分配的本金
    risk_amount: float         # 承担的固定风险额

@dataclass
class RiskConfig:
    """风控配置实体
    处理 K 线前进行热加载的风控参数。
    """
    risk_pct: float      # 单笔最大风险百分比，例如 0.02 (2%)
    max_sl_dist: float   # 天地针熔断最大止损距离，例如 0.035 (3.5%)
    max_leverage: float  # 杠杆熔断上限，例如 20.0

class AutoOrderStatus(str, Enum):
    """自动下单开关枚举 (严禁编辑且必须置灰显示)"""
    ON = "ON"
    OFF = "OFF"

@dataclass
class IntervalConfig:
    """单个监控周期的配置"""
    use_trend_filter: bool = True       # 是否开启大级别趋势校验

@dataclass
class WebhookSettings:
    """告警推送配置"""
    global_push_enabled: bool = True     # 全局推送总开关 (默认开启)
    feishu_enabled: bool = False
    wecom_enabled: bool = False          # 企业微信推送开关
    feishu_secret: Optional[str] = None
    wecom_secret: Optional[str] = None   # 企微 Webhook 密钥

@dataclass
class SystemConfig:
    """系统全局配置实体"""
    active_symbols: List[str]
    monitor_intervals: Dict[str, IntervalConfig]  # 监控周期及其各自配置, 如 {"15m": IntervalConfig(use_trend_filter=True)}
    risk_config: RiskConfig
    scoring_weights: ScoringWeights
    webhook_settings: WebhookSettings
    pinbar_config: PinbarConfig = field(default_factory=PinbarConfig)
    auto_order_status: AutoOrderStatus = AutoOrderStatus.OFF # 默认关闭，严禁开启

@dataclass
class SystemStatus:
    """系统遥测状态实体
    用于前端指挥中心大屏监控。
    """
    is_connected: bool
    api_latency_ms: int
    api_weight_usage: float # 币安 API 权重消耗百分比 (0-100%)
    uptime: str             # 已持续运行时间 (例如 "12d 4h 3m")

@dataclass
class SignalFilter:
    """信号过滤条件实体
    用于多维度查询信号记录。
    """
    symbols: Optional[List[str]] = None
    intervals: Optional[List[str]] = None     # 级别筛选 (如 ["15m", "1h"])
    directions: Optional[List[str]] = None    # "LONG" / "SHORT"
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    min_score: Optional[int] = None           # 最低分数线
    sort_by: Optional[str] = "timestamp"      # 排序字段: "timestamp" or "score"
    order: Optional[str] = "desc"             # 排序方向: "asc" or "desc"
