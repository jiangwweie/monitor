"""
基础设施层：飞书 (Feishu) 机器人推送适配器。
实现 INotifier 接口，发送 Markdown 富文本到飞书群组。
"""

import logging

import httpx
from core.interfaces import INotifier, IRepository

logger = logging.getLogger(__name__)


class FeishuNotifier(INotifier):
    """
    负责将告警推送给飞书 Webhook 机器人的专职适配器。
    采用动态配置模式：从数据库实时拉取 Webhook 地址和开关。
    """

    def __init__(self, repo: IRepository):
        """
        初始化飞书推送器。

        :param repo: 仓储接口，用于查询动态配置。
        """
        self.repo = repo

    async def send_markdown(self, formatted_message: str) -> None:
        """
        异步调用飞书 API 投递消息。使用 POST 请求且设置 5s 超时。
        """
        try:
            is_enabled_str = await self.repo.get_secret("feishu_enabled")
            webhook_url = await self.repo.get_secret("feishu_webhook_url")

            # 默认为开启 (兼容初次安装)，由 global_push_enabled 统一控制也是一种方案，
            # 但这里遵循各频道独立开关逻辑。
            is_enabled = is_enabled_str.lower() == "true" if is_enabled_str else True

            if not is_enabled:
                logger.debug("Feishu 推送未开启，跳过发送。")
                return

            if not webhook_url:
                logger.warning("Feishu Webhook URL 未配置，跳过发送。")
                return

            payload = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": "📡 CryptoRadar 交易决策雷达",
                        },
                        "template": "blue",
                    },
                    "elements": [{"tag": "markdown", "content": formatted_message}],
                },
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                response.raise_for_status()
                # 飞书接口成功时返回码是 0
                resp_data = response.json()
                if resp_data.get("code", -1) != 0:
                    logger.error(f"飞书推送失败，返回信息: {resp_data.get('msg')}")
                else:
                    logger.info("飞书推送成功。")
        except httpx.TimeoutException:
            logger.error("飞书推送超时，放弃当前消息发送。")
        except httpx.HTTPError as e:
            logger.error(f"飞书推送网络异常: {e}")
        except Exception as e:
            logger.error(f"飞书推送未知异常: {e}")
