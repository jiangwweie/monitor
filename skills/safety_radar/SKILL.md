# 技能：只读雷达系统的安全底线

## 核心目标
本系统是一个“纯信号监测与决策辅助系统 (CryptoRadar)”，仅负责【检测】与【推送】。它绝对不能包含任何真实下达交易订单的代码。

## 严格约束规则
1. **零交易指令 (Zero Execution)**：
   - 系统中**严禁**出现任何向交易所发送下单、撤单、改单请求的代码（如禁止出现 `POST /fapi/v1/order`）。
   - 如果发现代码中有类似 `place_order`、`execute_trade` 等函数名，立即删除并重构。
2. **只读权限 (Read-Only Access)**：
   - 币安 API 适配器只能实现拉取 K 线数据 (`GET /fapi/v1/klines` 或 WebSocket) 和获取账户信息 (`GET /fapi/v2/account`) 的方法。
3. **输出定义 (Output Definition)**：
   - 系统的最终输出形式**必须且只能是**向外部（如飞书、Telegram）发送一条 Markdown 格式的富文本通知。
   - 包含的字段必须是“建议”而非“指令”（如：建议开仓量、建议杠杆倍数）。