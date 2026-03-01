"""
 基础设施层：Telegram 机器人推送适配器。
 实现 INotifier 接口，发送 Markdown 富文本到 TG 频道或个人的 bot 聊天。
"""
import logging

import httpx
from core.interfaces import INotifier

logger = logging.getLogger(__name__)

class TelegramNotifier(INotifier):
    """
    负责将交易监控告警送往指定 Telegram 对话 (chat_id) 的适配器。
    具有静默失败机制，不反噬主干。
    """
    def __init__(self, bot_token: str, chat_id: str):
        """
        初始化 Telegram 推送器。
        
        :param bot_token: TGBot 的访问令牌 token。
        :param chat_id: 消息接收者群组或个人的 ChatID。
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        # 为了应对可能有 GFW 阻挡的情况，可允许复用或者提供代理机制，当前默认裸连。
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    async def send_markdown(self, formatted_message: str) -> None:
        """
        向 Telegram 发送含有 MarkdownV2 或者普通 Markdown 格式的文本信息。
        这里使用 parse_mode=Markdown 以适配广泛环境。
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram token 或 chat_id 缺失，取消发送。")
            return

        payload = {
            "chat_id": self.chat_id,
            "text": formatted_message,
            "parse_mode": "Markdown", 
            "disable_web_page_preview": True 
        }

        async with httpx.AsyncClient() as client:
            try:
                # 容忍代理网络较慢的情形，给 10s 超时
                response = await client.post(
                    self.api_url, 
                    json=payload, 
                    timeout=10.0
                )
                response.raise_for_status()
                
                resp_json = response.json()
                if resp_json.get("ok"):
                    logger.info(f"Telegram 推送成功至 {self.chat_id}。")
                else:
                    error_desc = resp_json.get("description", "Unknown TG error")
                    logger.error(f"Telegram API 拒绝了请求: {error_desc}")
            except httpx.TimeoutException:
                logger.error("Telegram 推送网络连接超时，已忽略该条。")
            except httpx.HTTPError as e:
                logger.error(f"Telegram 推送发生 HTTP 网络错误: {e}")
            except Exception as e:
                logger.error(f"Telegram 推送遭遇了意料外的错误: {e}")
