"""
信号服务模块
提供信号查询、过滤、分页等功能。
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from core.entities import SignalFilter

logger = logging.getLogger(__name__)


class SignalService:
    """
    信号服务类
    统一管理信号查询操作，封装信号过滤和分页逻辑。
    """

    def __init__(self, repo):
        """
        初始化信号服务

        :param repo: SQLiteRepo 实例，用于信号数据访问
        """
        self.repo = repo

    async def get_signals(
        self,
        symbols: Optional[List[str]] = None,
        intervals: Optional[List[str]] = None,
        directions: Optional[List[str]] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
        source: Optional[str] = None,
        sort_by: str = "timestamp",
        order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        获取信号列表，支持多维度过滤和分页

        :param symbols: 交易对列表，如 ["BTCUSDT", "ETHUSDT"]
        :param intervals: 时间周期列表，如 ["15m", "1h"]
        :param directions: 方向列表，如 ["LONG", "SHORT"]
        :param start_time: 开始时间戳（毫秒）
        :param end_time: 结束时间戳（毫秒）
        :param min_score: 最低分数
        :param max_score: 最高分数
        :param source: 信号来源，"realtime" 或 "history_scan"
        :param sort_by: 排序字段，"timestamp" 或 "score"
        :param order: 排序方向，"asc" 或 "desc"
        :param page: 页码，从 1 开始
        :param page_size: 每页数量，最大 200
        :return: 包含 total 和 items 的字典
        """
        # 限制 page_size 范围
        page_size = min(max(page_size, 1), 200)
        page = max(page, 1)

        # 构建过滤条件
        filter_params = SignalFilter(
            symbols=symbols,
            intervals=intervals,
            directions=directions,
            start_time=start_time,
            end_time=end_time,
            min_score=min_score,
            sort_by=sort_by,
            order=order,
        )

        # 获取信号列表
        total, items = await self.repo.get_signals(filter_params, page, page_size)

        # 如果有 max_score 过滤，在内存中进行二次过滤
        if max_score is not None:
            filtered_items = [item for item in items if item.get("score", 0) <= max_score]
            total = len(filtered_items)
            items = filtered_items

        # 如果有 source 过滤，在内存中进行二次过滤
        if source is not None:
            filtered_items = [item for item in items if item.get("source", "realtime") == source]
            total = len(filtered_items)
            items = filtered_items

        return {
            "total": total,
            "items": items,
            "page": page,
            "page_size": page_size,
        }

    async def get_signal_by_id(self, signal_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取单个信号

        :param signal_id: 信号 ID
        :return: 信号字典，如果不存在返回 None
        """
        # SignalFilter 不支持 ID 查询，需要通过其他方式实现
        # 这里暂时返回 None，实际项目中可以在 repo 层添加 get_signal_by_id 方法
        logger.warning(f"get_signal_by_id 方法暂未实现，signal_id={signal_id}")
        return None

    async def delete_signals(self, signal_ids: List[int]) -> int:
        """
        批量删除信号

        :param signal_ids: 信号 ID 列表
        :return: 删除成功的数量
        """
        if not signal_ids:
            return 0

        deleted = await self.repo.delete_signals(signal_ids)
        return deleted

    async def cleanup_old_signals(self, days: int = 7) -> int:
        """
        清理 N 天前的信号数据

        :param days: 天数
        :return: 清理的数量
        """
        deleted = await self.repo.cleanup_old_signals(days)
        return deleted

    async def get_signal_statistics(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        获取信号统计信息

        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :return: 统计信息字典
        """
        # 获取所有信号（不分页）
        filter_params = SignalFilter(
            start_time=start_time,
            end_time=end_time,
        )

        total, items = await self.repo.get_signals(filter_params, page=1, size=10000)

        if not items:
            return {
                "total": 0,
                "long_count": 0,
                "short_count": 0,
                "avg_score": 0,
                "score_distribution": {},
                "tier_distribution": {},
            }

        # 统计计算
        long_count = sum(1 for item in items if item.get("direction") == "LONG")
        short_count = sum(1 for item in items if item.get("direction") == "SHORT")
        scores = [item.get("score", 0) for item in items]
        avg_score = sum(scores) / len(scores) if scores else 0

        # 分数分布
        score_distribution = {
            "0-20": 0,
            "20-40": 0,
            "40-60": 0,
            "60-80": 0,
            "80-100": 0,
        }
        for score in scores:
            if score < 20:
                score_distribution["0-20"] += 1
            elif score < 40:
                score_distribution["20-40"] += 1
            elif score < 60:
                score_distribution["40-60"] += 1
            elif score < 80:
                score_distribution["60-80"] += 1
            else:
                score_distribution["80-100"] += 1

        # 质量等级分布
        tier_distribution = {"A": 0, "B": 0, "C": 0}
        for item in items:
            tier = item.get("quality_tier", "B")
            if tier in tier_distribution:
                tier_distribution[tier] += 1

        return {
            "total": total,
            "long_count": long_count,
            "short_count": short_count,
            "avg_score": round(avg_score, 2),
            "score_distribution": score_distribution,
            "tier_distribution": tier_distribution,
        }
