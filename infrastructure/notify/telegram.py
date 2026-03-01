"""
基础设施层：Telegram 机器人推送适配器。
实现 INotifier 接口，发送 Markdown 富文本到 TG 频道或个人的 bot 聊天。
"""

import logging

import httpx
from core.interfaces import INotifier, IRepository

logger = logging.getLogger(__name__)


class TelegramNotifier(INotifier):
    """
    负责将交易监控告警送往指定 Telegram 对话 (chat_id) 的适配器。
    采用动态配置模式：从数据库实时拉取 Token 和 ChatID。
    """

    def __init__(self, repo: IRepository):
        """
        初始化 Telegram 推送器。

        :param repo: 仓储接口，用于查询动态配置。
        """
        self.repo = repo

    async def send_markdown(self, formatted_message: str) -> None:
        """
        向 Telegram 发送含有 MarkdownV2 或者普通 Markdown 格式的文本信息。
        """
        try:
            is_enabled_str = await self.repo.get_secret("telegram_enabled")
            bot_token = await self.repo.get_secret("telegram_bot_token")
            chat_id = await self.repo.get_secret("telegram_chat_id")

            # 默认为关闭 (安全起见)
            is_enabled = is_enabled_str.lower() == "true" if is_enabled_str else False

            if not is_enabled:
                logger.debug("Telegram 推送未开启，跳过发送。")
                return

            if not bot_token or not chat_id:
                logger.warning("Telegram token 或 chat_id 缺失，取消发送。")
                return

            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

            payload = {
                "chat_id": chat_id,
                "text": formatted_message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }

            async with httpx.AsyncClient() as client:
                # 容忍代理网络较慢的情形，给 10s 超时
                response = await client.post(api_url, json=payload, timeout=10.0)
                response.raise_for_status()

                resp_json = response.json()
                if resp_json.get("ok"):
                    logger.info(f"Telegram 推送成功至 {chat_id}。")
                else:
                    error_desc = resp_json.get("description", "Unknown TG error")
                    logger.error(f"Telegram API 拒绝了请求: {error_desc}")
        except httpx.TimeoutException:
            logger.error("Telegram 推送网络连接超时，已忽略该条。")
        except httpx.HTTPError as e:
            logger.error(f"Telegram 推送发生 HTTP 网络错误: {e}")
        except Exception as e:
            logger.error(f"Telegram 推送遭遇了意料外的错误: {e}")
