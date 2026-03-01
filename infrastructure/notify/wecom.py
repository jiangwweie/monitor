"""
 基础设施层：企业微信 (WeCom) 机器人推送适配器。
 实现 INotifier 接口，发送 Markdown 富文本到企业微信。
 遵循 @skills/dynamic_config，动态从 DB 读取配置。
"""
import logging
import httpx
from core.interfaces import INotifier, IRepository

logger = logging.getLogger(__name__)

class WeComNotifier(INotifier):
    """
    负责将告警推送给企业微信 Webhook 机器人的适配器。
    采用动态配置模式：每次发送前从数据库拉取最新的开关状态和 URL。
    """
    def __init__(self, repo: IRepository):
        """
        初始化企业微信推送器。
        
        :param repo: 仓储接口，用于查询动态配置。
        """
        self.repo = repo

    async def send_markdown(self, formatted_message: str) -> None:
        """
        异步调用企业微信 API 投递消息。
        """
        # 从数据库获取最新的配置
        # 注意：此处依赖于 IRepository 扩展了获取配置的能力，或者直接从 configs 表读
        # 在我们的实现中，使用 repo.get_secret 或类似机制
        try:
            is_enabled_str = await self.repo.get_secret("wecom_enabled")
            webhook_url = await self.repo.get_secret("wecom_webhook_url")
            
            # 默认为关闭，除非明确设置为 "true"
            is_enabled = is_enabled_str.lower() == "true"
            
            if not is_enabled:
                logger.debug("WeCom 推送未开启，跳过发送。")
                return

            if not webhook_url:
                logger.warning("WeCom Webhook URL 已开启但未配置，跳过发送。")
                return

            # 企业微信的 Markdown 报文结构
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": formatted_message
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=5.0
                )
                response.raise_for_status()
                resp_data = response.json()
                
                # 企业微信返回 errcode 为 0 表示成功
                if resp_data.get('errcode', -1) != 0:
                    logger.error(f"企业微信推送失败，返回信息: {resp_data.get('errmsg')}")
                else:
                    logger.info("企业微信推送成功。")
                    
        except httpx.TimeoutException:
            logger.error("企业微信推送超时，放弃当前消息发送。")
        except httpx.HTTPError as e:
            logger.error(f"企业微信推送网络异常: {e}")
        except Exception as e:
            logger.error(f"企业微信推送未知异常: {e}")
