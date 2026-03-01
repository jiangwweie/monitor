"""
风控算仓大脑模块 (Domain 层)
严格按照 PRD 计算风险敞口、分配开仓本金并推算安全杠杆与开仓数量。
此模块为纯数学运算，没有任何网络请求或实际下单动作！
"""
from core.entities import Signal, AccountBalance, PositionSizing
from core.exceptions import RiskLimitExceeded

class PositionSizer:
    """风控仓位计算器
    严格遵守 Zero Execution 的红线规则。仅用于推算开仓建议，保护本金安全。
    """

    def calculate(
        self,
        signal: Signal,
        account: AccountBalance,
        risk_pct: float,
        max_leverage: float
    ) -> PositionSizing:
        """
        根据当前账户快照和风控配置对有效信号进行杠杆和算仓建议计算。

        :param signal: 策略引擎生成的有效信号快照
        :param account: 从交易所实时只读获取到的账户余额与持仓笔数
        :param risk_pct: 单笔最大承受风险比例（如 0.02 表示 2%）
        :param max_leverage: 系统允许的最高杠杆倍数（如 20.0）
        :return: 推算出的包含杠杆及数量的 PositionSizing 实体。
        :raises RiskLimitExceeded: 在前置拦截条件不满足时抛出异常。
        """

        # ==========================================
        # 1. 前置拦截规则 (Pre-flight checks)
        # ==========================================
        # 拦截：当前持仓笔数 n >= 4 时，不可再开新仓，避免所有资金爆仓
        if account.current_positions_count >= 4:
            raise RiskLimitExceeded(f"当前持仓笔数已达上限 ({account.current_positions_count}>=4)，禁止新开仓")

        # 为了避免全仓余额被零除，做一道基本安全拦截
        if account.total_wallet_balance <= 0 or account.available_balance <= 0:
            raise RiskLimitExceeded("账户余额不足或已穿仓")

        # ==========================================
        # 2. 本金分配计算 (Capital Allocation)
        # ==========================================
        # 根据动态剩余槽位分配可用资金
        # 假定总最多同时可以持有 4 笔单子，那么当前分配给这笔单子的理论可用资金是：
        investment_amount = account.total_wallet_balance / (4 - account.current_positions_count)

        # 保护性检查：如果计算出分配资金比可用余额多，只能取最小可用量
        # if investment_amount > account.available_balance:
        #    investment_amount = account.available_balance

        # ==========================================
        # 3. 风险及止损测算 (Risk Assessment)
        # ==========================================
        # 单笔允许承受的绝对风险金额 = 钱包总额 * 单笔配置风险比率 (2%)
        risk_amount = account.total_wallet_balance * risk_pct

        # 校验：这笔信号传来的止损百分比是否正常
        if signal.sl_distance_pct <= 0:
            raise RiskLimitExceeded("信号自带的止损百分比距离无效或小于零")

        # ==========================================
        # 4. 计算仓位与杠杆 (Position & Leverage Calculation)
        # ==========================================
        # 计算理论应开名义价值 (Notional Value) = 单笔风险金额 / 止损距离比例
        # 例如：风险 20 USDT，止损距离 1%，那么我们需要开 2000 USDT 身价的仓位才会在止损时刚好吃满 20 USDT 风险
        notional_value = risk_amount / signal.sl_distance_pct

        # 开仓数量 = 理论名义价值 / 当前价格
        suggested_quantity = notional_value / signal.entry_price

        # 计算理论需要开出的杠杆：名义价值 / 可用投资本金额
        # 并在此基础上预留 1.05 作为安全垫，预防维持保证金和强平平推穿仓费率导致没止损就爆了
        theoretical_leverage = (notional_value / investment_amount) * 1.05

        # ==========================================
        # 5. 杠杆熔断自适应 (Leverage Cap & Auto-Scaling)
        # ==========================================
        suggested_leverage = theoretical_leverage

        # 熔断截断：当算出来的危险推算杠杆大大超出熔断线的时候
        if suggested_leverage > max_leverage:
            # 强制压制为系统顶格杠杆
            suggested_leverage = max_leverage

            # 对应只能同比例压制仓位
            # 反推出被压缩后的理论开仓的实际价值
            capped_notional_value = investment_amount * (max_leverage / 1.05)
            
            # 使用这笔实际价值反推压缩后的开仓数量
            suggested_quantity = capped_notional_value / signal.entry_price
            
            # 同时由于本金、杠杆都被压缩，这笔单子的理论风险敞口其实降低了
            risk_amount = capped_notional_value * signal.sl_distance_pct

        # ==========================================
        # 6. 生成安全算仓结果并返回
        # ==========================================
        return PositionSizing(
            signal=signal,
            suggested_leverage=suggested_leverage,
            suggested_quantity=suggested_quantity,
            investment_amount=investment_amount,
            risk_amount=risk_amount
        )
