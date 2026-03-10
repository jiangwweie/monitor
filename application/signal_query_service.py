"""
应用层：信号查询服务
封装信号查询的分页、筛选、排序业务逻辑
"""
from dataclasses import dataclass
from typing import List, Optional, Generic, TypeVar
from core.interfaces import IRepository
from core.entities import Signal

T = TypeVar('T')


@dataclass
class PaginatedResult(Generic[T]):
    """分页结果封装"""
    items: List[T]
    total: int
    page: int
    size: int
    has_next: bool
    has_prev: bool


class SignalQueryService:
    """
    信号查询应用服务
    职责：编排仓储查询，处理分页逻辑
    """

    def __init__(self, repo: IRepository):
        self.repo = repo

    async def query_signals(
        self,
        symbols: Optional[List[str]] = None,
        intervals: Optional[List[str]] = None,
        directions: Optional[List[str]] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
        quality_tier: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        sort_by: str = "timestamp",
        order: str = "desc"
    ) -> PaginatedResult[Signal]:
        """
        分页查询信号

        :param symbols: 币种列表
        :param intervals: 时间级别列表
        :param directions: 方向列表
        :param start_time: 开始时间（毫秒戳）
        :param end_time: 结束时间（毫秒戳）
        :param min_score: 最低评分
        :param max_score: 最高评分
        :param quality_tier: 信号等级 (A/B/C)
        :param source: 信号来源 ("realtime" 或 "history_scan")
        :param page: 页码 (从 1 开始)
        :param size: 每页大小
        :param sort_by: 排序字段
        :param order: 排序方向 (asc/desc)
        :return: 分页结果
        """
        # 调用仓储层查询
        items, total = await self.repo.query_signals_with_pagination(
            symbols=symbols,
            intervals=intervals,
            directions=directions,
            start_time=start_time,
            end_time=end_time,
            min_score=min_score,
            max_score=max_score,
            quality_tier=quality_tier,
            source=source,
            offset=(page - 1) * size,
            limit=size,
            sort_by=sort_by,
            order=order
        )

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            size=size,
            has_next=(page * size) < total,
            has_prev=page > 1
        )
