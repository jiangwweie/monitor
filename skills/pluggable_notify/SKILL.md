# 技能：组合模式与高并发消息推送

## 核心目标
系统的推送模块必须支持多渠道（飞书、Telegram、Webhook 等），且要求“可随意插拔”、“互不阻塞”。

## 严格约束规则
1. **遵守契约**：所有的单一推送渠道适配器（如 `FeishuNotifier`, `TelegramNotifier`）都必须继承并实现 `core.interfaces.INotifier` 接口。
2. **组合模式 (Composite Pattern)**：
   - 必须实现一个 `NotificationBroadcaster` 类，它同样继承 `INotifier`，但内部持有一个 `List[INotifier]`。
   - 引擎 (`Engine`) 只允许持有并调用 `NotificationBroadcaster`，绝不能直接调用飞书或 TG 适配器。
3. **防雪崩异步并发**：
   - 在 `NotificationBroadcaster` 分发消息时，**必须使用 `asyncio.gather(*tasks, return_exceptions=True)`** 并发执行所有子渠道的发送任务。
   - 绝不允许使用 `for` 循环同步 `await` 等待。一个渠道网络超时，绝对不能影响其他渠道的发送。