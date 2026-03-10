"""
 基础设施层：并发广播器 (NotificationBroadcaster)。
 采用组合模式 (Composite Pattern) 实现多渠道并发分发。
 完全遵循 @skills/pluggable_notify 规范。
"""
import asyncio
import logging
from typing import List

from core.interfaces import INotifier

logger = logging.getLogger(__name__)

class NotificationBroadcaster(INotifier):
    """
    负责管理和并行调用所有注册进来的通信终端（如发送到飞书同时发给 TG），
    保证哪怕某一端网络堵塞或崩溃挂了也不影响其它端点或阻塞主干流转。
    """
    def __init__(self):
        self._channels: List[INotifier] = []

    def register(self, notifier: INotifier) -> "NotificationBroadcaster":
        """
        动态注册一个实现了 INotifier 的具体适配器实例
        支持链式调用，如 broadcaster.register(feishu).register(wecom)
        """
        if notifier not in self._channels:
            self._channels.append(notifier)
        return self

    async def send_markdown(self, formatted_message: str) -> None:
        """
        向所有已注册频道并发发送消息。
        必须且只能使用 asyncio.gather 配合 return_exceptions=True 做到绝对的互不干扰隔离发送。
        绝不允许在此处使用阻塞式的 ``for await`` 循环。
        """
        if not self._channels:
            logger.debug("广播器当前没有任何下挂频道，消息被忽略丢弃。")
            return

        # 封装出各个频道发给事件循环的任务群
        tasks = [
            channel.send_markdown(formatted_message)
            for channel in self._channels
        ]

        logger.info(f"正在准备向 {len(self._channels)} 个子频道并行广播消息...")

        # 核心防雪崩机制所在：并发等待全部任务。就算任何一个 tasks 抛出 exception 也不会在此刻打断后续其它任务。
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            # 将收集来的 Exception 统一只写入日志（由于单个端的 try-except 在它们各自内部做了，这里通常用于抓那些漏网之鱼）
            if isinstance(result, Exception):
                channel_name = self._channels[i].__class__.__name__
                logger.error(f"严重: 频道 {channel_name} 在并发期间爆破了意料之外的未处理异常: {repr(result)}")
