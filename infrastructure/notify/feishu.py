"""
 基础设施层：飞书 (Feishu) 机器人推送适配器。
 实现 INotifier 接口，发送 Markdown 富文本到飞书群组。
"""
import json
import logging

import httpx
from core.interfaces import INotifier

logger = logging.getLogger(__name__)

class FeishuNotifier(INotifier):
    """
    负责将告警推送给飞书 Webhook 机器人的专职适配器。
    具有静默失败机制，不会因自身超时影响其它流程网络服务。
    """
    def __init__(self, webhook_url: str, secret: str = None):
        """
        初始化飞书推送器。
        
        :param webhook_url: 飞书自定义机器人的 Webhook 地址。
        :param secret: 飞书安全校验密钥 (可选，本期简易实现可留空)。
        """
        self.webhook_url = webhook_url
        self.secret = secret

    async def send_markdown(self, formatted_message: str) -> None:
        """
        异步调用飞书 API 投递消息。使用 POST 请求且设置 5s 超时。
        """
        if not self.webhook_url:
            logger.warning("Feishu Webhook URL 未配置，跳过发送。")
            return

        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📡 CryptoRadar 交易决策雷达"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": formatted_message
                    }
                ]
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=5.0
                )
                response.raise_for_status()
                # 飞书接口成功时返回码是 0
                resp_data = response.json()
                if resp_data.get('code', -1) != 0:
                    logger.error(f"飞书推送失败，返回信息: {resp_data.get('msg')}")
                else:
                    logger.info("飞书推送成功。")
            except httpx.TimeoutException:
                logger.error("飞书推送超时，放弃当前消息发送。")
            except httpx.HTTPError as e:
                logger.error(f"飞书推送网络异常: {e}")
            except Exception as e:
                logger.error(f"飞书推送未知异常: {e}")
