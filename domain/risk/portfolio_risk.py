"""
投资组合风险聚合服务 (Domain 层)
计算和监控所有持仓的总风险敞口，防止极端行情下多仓位同时止损导致总风险失控。
"""
from dataclasses import dataclass
from typing import List, Optional

from core.entities import Position


@dataclass
class PortfolioRiskMetrics:
    """投资组合风险指标"""
    total_risk_amount: float      # 所有持仓的总风险额
    total_risk_pct: float         # 总风险占账户比例
    max_single_loss_pct: float    # 最大单笔损失比例
    position_count: int           # 持仓数量


class PortfolioRiskService:
    """投资组合风险聚合服务

    核心职责：
    1. 聚合所有持仓的风险指标
    2. 检查组合总风险是否超限
    3. 提供风险透明度，帮助用户理解整体敞口
    """

    def calculate_portfolio_risk(
        self,
        positions: List[Position],
        total_wallet_balance: float
    ) -> PortfolioRiskMetrics:
        """计算投资组合的聚合风险指标

        :param positions: 当前持仓列表
        :param total_wallet_balance: 账户总余额
        :return: 包含聚合风险指标的 PortfolioRiskMetrics 实体
        """
        # 空持仓列表或零余额时返回零值指标，不抛异常
        if not positions or total_wallet_balance <= 0:
            return PortfolioRiskMetrics(
                total_risk_amount=0.0,
                total_risk_pct=0.0,
                max_single_loss_pct=0.0,
                position_count=0
            )

        # 计算总风险额（从每个持仓的风险额聚合）
        # 使用 getattr 兼容 Position 实体可能还没有 risk_amount 字段的情况
        total_risk = sum(
            getattr(pos, 'risk_amount', 0.0) for pos in positions
        )
        total_risk_pct = total_risk / total_wallet_balance

        # 计算最大单笔风险
        max_single_risk = max(
            (getattr(pos, 'risk_amount', 0.0) for pos in positions),
            default=0.0
        )
        max_single_loss_pct = (
            max_single_risk / total_wallet_balance
            if total_wallet_balance > 0
            else 0.0
        )

        return PortfolioRiskMetrics(
            total_risk_amount=total_risk,
            total_risk_pct=total_risk_pct,
            max_single_loss_pct=max_single_loss_pct,
            position_count=len(positions)
        )

    def check_portfolio_limit(
        self,
        metrics: PortfolioRiskMetrics,
        max_portfolio_risk_pct: float = 0.08
    ) -> bool:
        """检查投资组合风险是否超限

        :param metrics: 组合风险指标
        :param max_portfolio_risk_pct: 最大允许的组合风险比例（默认 8%）
        :return: True 表示风险在限制内，False 表示已超限
        """
        return metrics.total_risk_pct <= max_portfolio_risk_pct
