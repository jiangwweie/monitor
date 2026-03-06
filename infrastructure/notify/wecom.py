"""
基础设施层：企业微信 (WeCom) 机器人推送适配器。
实现 INotifier 接口，发送 Markdown 富文本到企业微信。
"""

import logging
import os

import httpx
from core.interfaces import INotifier

logger = logging.getLogger(__name__)


class WeComNotifier(INotifier):
    """
    负责将告警推送给企业微信 Webhook 机器人的适配器。
    配置从环境变量读取。
    """

    def __init__(self):
        """
        初始化企业微信推送器。
        从环境变量读取配置。
        """
        self.enabled = os.getenv("WECOM_ENABLED", "false").lower() == "true"
        self.webhook_url = os.getenv("WECOM_WEBHOOK_URL", "")
        self.global_enabled = os.getenv("GLOBAL_PUSH_ENABLED", "true").lower() != "false"

    async def send_markdown(self, formatted_message: str) -> None:
        """
        异步调用企业微信 API 投递消息。
        """
        try:
            # 检查全局开关和频道开关
            if not self.global_enabled:
                logger.debug("全局推送已关闭，跳过企业微信发送。")
                return

            if not self.enabled:
                logger.debug("WeCom 推送未开启，跳过发送。")
                return

            if not self.webhook_url:
                logger.warning("WeCom Webhook URL 已开启但未配置，跳过发送。")
                return

            # 企业微信的 Markdown 报文结构
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": formatted_message},
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=5.0)
                response.raise_for_status()
                resp_data = response.json()

                # 企业微信返回 errcode 为 0 表示成功
                if resp_data.get("errcode", -1) != 0:
                    logger.error(
                        f"企业微信推送失败，返回信息：{resp_data.get('errmsg')}"
                    )
                else:
                    logger.info("企业微信推送成功。")

        except httpx.TimeoutException:
            logger.error("企业微信推送超时，放弃当前消息发送。")
        except httpx.HTTPError as e:
            logger.error(f"企业微信推送网络异常：{e}")
        except Exception as e:
            logger.error(f"企业微信推送未知异常：{e}")
