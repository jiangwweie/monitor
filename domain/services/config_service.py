"""
配置服务模块
提供系统配置的读取和更新功能，统一管理各类配置数据。
"""
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import asdict

from core.entities import (
    IntervalConfig,
    PinbarConfig,
    ScoringWeights,
    RiskConfig as RiskConfigEntity
)
from domain.strategy.scoring_config import ScoringConfig

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """配置校验异常"""
    pass


class ConfigService:
    """
    配置服务类
    统一管理配置读取和更新操作，封装 SQLiteRepo 的配置访问逻辑。
    """

    def __init__(self, repo):
        """
        初始化配置服务

        :param repo: SQLiteRepo 实例，用于配置持久化
        """
        self.repo = repo

    async def _get_json_secret(self, key: str, default: Optional[Dict] = None) -> Optional[Dict]:
        """从数据库获取 JSON 格式的配置"""
        value = await self.repo.get_secret(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"配置 {key} JSON 解析失败")
                return default
        return default

    async def get_system_config(self) -> Dict[str, Any]:
        """
        获取系统配置摘要
        返回系统启用状态、活跃币种、监控周期等基础配置
        """
        # 从数据库读取 system_enabled
        system_enabled_val = await self.repo.get_secret("system_enabled")
        system_enabled = system_enabled_val.lower() == "true" if system_enabled_val else True

        # 获取活跃币种
        active_symbols_json = await self.repo.get_secret("active_symbols")
        active_symbols = json.loads(active_symbols_json) if active_symbols_json else []

        # 获取监控周期配置
        monitor_intervals_json = await self.repo.get_secret("monitor_intervals")
        monitor_intervals = {}
        if monitor_intervals_json:
            try:
                intervals_data = json.loads(monitor_intervals_json)
                if isinstance(intervals_data, dict):
                    monitor_intervals = {
                        k: asdict(v) if isinstance(v, IntervalConfig) else v
                        for k, v in intervals_data.items()
                    }
            except json.JSONDecodeError:
                pass

        return {
            "system_enabled": system_enabled,
            "active_symbols": active_symbols,
            "monitor_intervals": monitor_intervals,
        }

    async def get_symbols_config(self) -> Dict[str, Any]:
        """
        获取币种配置
        返回当前监控的交易对列表
        """
        active_symbols_json = await self.repo.get_secret("active_symbols")
        active_symbols = json.loads(active_symbols_json) if active_symbols_json else []

        return {
            "active_symbols": active_symbols,
        }

    async def get_monitor_config(self) -> Dict[str, Any]:
        """
        获取监控周期配置
        返回各时间周期的监控设置
        """
        monitor_intervals_json = await self.repo.get_secret("monitor_intervals")
        monitor_intervals = {}

        if monitor_intervals_json:
            try:
                intervals_data = json.loads(monitor_intervals_json)
                if isinstance(intervals_data, dict):
                    monitor_intervals = {
                        k: asdict(v) if isinstance(v, IntervalConfig) else v
                        for k, v in intervals_data.items()
                    }
            except json.JSONDecodeError:
                pass

        return {
            "monitor_intervals": monitor_intervals,
        }

    async def update_monitor_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新监控配置

        :param config: 配置字典，包含 monitor_intervals 和 active_symbols
        :return: 更新后的配置
        """
        if "monitor_intervals" in config and config["monitor_intervals"] is not None:
            # 校验：至少保留一个监控级别
            intervals = config["monitor_intervals"]
            if isinstance(intervals, dict) and len(intervals) == 0:
                raise ConfigValidationError("监控配置：至少需要保留一个监控级别")
            if isinstance(intervals, list) and len(intervals) == 0:
                raise ConfigValidationError("监控配置：至少需要保留一个监控级别")

            await self.repo.set_secret("monitor_intervals", json.dumps(intervals))

        if "active_symbols" in config and config["active_symbols"] is not None:
            await self.repo.set_secret("active_symbols", json.dumps(config["active_symbols"]))

        return await self.get_monitor_config()

    async def get_risk_config(self, engine_risk_config: Optional[RiskConfigEntity] = None) -> Dict[str, Any]:
        """
        获取风控配置

        :param engine_risk_config: 引擎当前的风控配置，作为默认值
        :return: 风控配置字典
        """
        risk_config_json = await self.repo.get_secret("risk_config")

        if risk_config_json:
            try:
                risk_config_data = json.loads(risk_config_json)
                return {
                    "risk_pct": risk_config_data.get("risk_pct", 0.02),
                    "max_sl_dist": risk_config_data.get("max_sl_dist", 0.035),
                    "max_leverage": risk_config_data.get("max_leverage", 20.0),
                }
            except json.JSONDecodeError:
                pass

        # 返回默认值或引擎配置
        if engine_risk_config:
            return {
                "risk_pct": engine_risk_config.risk_pct,
                "max_sl_dist": engine_risk_config.max_sl_dist,
                "max_leverage": engine_risk_config.max_leverage,
            }

        return {
            "risk_pct": 0.02,
            "max_sl_dist": 0.035,
            "max_leverage": 20.0,
        }

    async def get_scoring_config(self) -> Dict[str, Any]:
        """
        获取打分配置
        返回打分模式、参数和权重配置
        """
        config_json = await self.repo.get_secret("scoring_config")

        if config_json:
            try:
                config_data = json.loads(config_json)
                return {
                    "mode": config_data.get("mode", "classic"),
                    "classic_shadow_min": config_data.get("classic_shadow_min", 0.6),
                    "classic_shadow_max": config_data.get("classic_shadow_max", 0.9),
                    "classic_body_good": config_data.get("classic_body_good", 0.1),
                    "classic_body_bad": config_data.get("classic_body_bad", 0.5),
                    "classic_vol_min": config_data.get("classic_vol_min", 1.2),
                    "classic_vol_max": config_data.get("classic_vol_max", 3.0),
                    "classic_trend_max_dist": config_data.get("classic_trend_max_dist", 0.03),
                    "progressive_base_cap": config_data.get("progressive_base_cap", 30.0),
                    "progressive_shadow_threshold": config_data.get("progressive_shadow_threshold", 0.6),
                    "progressive_shadow_bonus_rate": config_data.get("progressive_shadow_bonus_rate", 20.0),
                    "progressive_body_bonus_threshold": config_data.get("progressive_body_bonus_threshold", 0.1),
                    "progressive_body_bonus_rate": config_data.get("progressive_body_bonus_rate", 100.0),
                    "progressive_doji_bonus": config_data.get("progressive_doji_bonus", 5.0),
                    "progressive_vol_threshold": config_data.get("progressive_vol_threshold", 2.0),
                    "progressive_vol_bonus_rate": config_data.get("progressive_vol_bonus_rate", 15.0),
                    "progressive_extreme_vol_threshold": config_data.get("progressive_extreme_vol_threshold", 3.0),
                    "progressive_extreme_vol_bonus": config_data.get("progressive_extreme_vol_bonus", 10.0),
                    "progressive_penetration_rate": config_data.get("progressive_penetration_rate", 30.0),
                    "w_shape": config_data.get("w_shape", 0.4),
                    "w_trend": config_data.get("w_trend", 0.3),
                    "w_vol": config_data.get("w_vol", 0.3),
                }
            except json.JSONDecodeError:
                logger.warning("打分配置 JSON 解析失败，使用默认配置")

        # 返回默认配置
        return {
            "mode": "classic",
            "classic_shadow_min": 0.6,
            "classic_shadow_max": 0.9,
            "classic_body_good": 0.1,
            "classic_body_bad": 0.5,
            "classic_vol_min": 1.2,
            "classic_vol_max": 3.0,
            "classic_trend_max_dist": 0.03,
            "progressive_base_cap": 30.0,
            "progressive_shadow_threshold": 0.6,
            "progressive_shadow_bonus_rate": 20.0,
            "progressive_body_bonus_threshold": 0.1,
            "progressive_body_bonus_rate": 100.0,
            "progressive_doji_bonus": 5.0,
            "progressive_vol_threshold": 2.0,
            "progressive_vol_bonus_rate": 15.0,
            "progressive_extreme_vol_threshold": 3.0,
            "progressive_extreme_vol_bonus": 10.0,
            "progressive_penetration_rate": 30.0,
            "w_shape": 0.4,
            "w_trend": 0.3,
            "w_vol": 0.3,
        }

    async def get_pinbar_config(self, engine_pinbar_config: Optional[PinbarConfig] = None) -> Dict[str, Any]:
        """
        获取 Pinbar 策略配置

        :param engine_pinbar_config: 引擎当前的 Pinbar 配置，作为默认值
        :return: Pinbar 配置字典
        """
        pinbar_config_json = await self.repo.get_secret("pinbar_config")

        if pinbar_config_json:
            try:
                pinbar_data = json.loads(pinbar_config_json)
                return {
                    "body_max_ratio": pinbar_data.get("body_max_ratio", 0.25),
                    "shadow_min_ratio": pinbar_data.get("shadow_min_ratio", 2.5),
                    "volatility_atr_multiplier": pinbar_data.get("volatility_atr_multiplier", 1.2),
                    "doji_threshold": pinbar_data.get("doji_threshold", 0.05),
                    "doji_shadow_bonus": pinbar_data.get("doji_shadow_bonus", 0.6),
                    "mtf_trend_filter_mode": pinbar_data.get("mtf_trend_filter_mode", "soft"),
                    "dynamic_sl_enabled": pinbar_data.get("dynamic_sl_enabled", True),
                    "dynamic_sl_base": pinbar_data.get("dynamic_sl_base", 0.035),
                    "dynamic_sl_atr_multiplier": pinbar_data.get("dynamic_sl_atr_multiplier", 0.5),
                }
            except json.JSONDecodeError:
                pass

        # 返回默认值或引擎配置
        if engine_pinbar_config:
            return asdict(engine_pinbar_config)

        return {
            "body_max_ratio": 0.25,
            "shadow_min_ratio": 2.5,
            "volatility_atr_multiplier": 1.2,
            "doji_threshold": 0.05,
            "doji_shadow_bonus": 0.6,
            "mtf_trend_filter_mode": "soft",
            "dynamic_sl_enabled": True,
            "dynamic_sl_base": 0.035,
            "dynamic_sl_atr_multiplier": 0.5,
        }

    async def get_webhook_config(self) -> Dict[str, Any]:
        """
        获取 Webhook 推送配置
        返回各推送通道的启用状态和密钥配置
        """
        # 获取全局推送开关
        global_push_enabled_val = await self.repo.get_secret("global_push_enabled")
        global_push_enabled = global_push_enabled_val.lower() == "true" if global_push_enabled_val else True

        # 获取飞书配置
        feishu_enabled_val = await self.repo.get_secret("feishu_enabled")
        feishu_enabled = feishu_enabled_val.lower() == "true" if feishu_enabled_val else False
        feishu_secret = await self.repo.get_secret("feishu_webhook_url")

        # 获取企业微信配置
        wecom_enabled_val = await self.repo.get_secret("wecom_enabled")
        wecom_enabled = wecom_enabled_val.lower() == "true" if wecom_enabled_val else False
        wecom_secret = await self.repo.get_secret("wecom_webhook_url")

        return {
            "global_push_enabled": global_push_enabled,
            "feishu_enabled": feishu_enabled,
            "feishu_secret": feishu_secret if feishu_secret else "",
            "wecom_enabled": wecom_enabled,
            "wecom_secret": wecom_secret if wecom_secret else "",
        }

    async def update_system_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新系统配置

        :param config: 配置字典，可包含 system_enabled, active_symbols, monitor_intervals
        :return: 更新后的配置
        """
        if "system_enabled" in config and config["system_enabled"] is not None:
            await self.repo.set_secret(
                "system_enabled",
                str(config["system_enabled"]).lower()
            )

        if "active_symbols" in config and config["active_symbols"] is not None:
            await self.repo.set_secret("active_symbols", json.dumps(config["active_symbols"]))

        if "monitor_intervals" in config and config["monitor_intervals"] is not None:
            await self.repo.set_secret(
                "monitor_intervals",
                json.dumps(config["monitor_intervals"])
            )

        return await self.get_system_config()

    async def update_risk_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新风控配置

        :param config: 配置字典，包含 risk_pct, max_sl_dist, max_leverage
        :return: 更新后的配置
        """
        current = await self.get_risk_config()
        current.update(config)

        await self.repo.set_secret("risk_config", json.dumps(current))
        return current

    async def update_scoring_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新打分配置

        :param config: 配置字典，包含各项打分参数
        :return: 更新后的配置
        """
        current = await self.get_scoring_config()
        current.update(config)

        await self.repo.set_secret("scoring_config", json.dumps(current))
        return current

    async def update_pinbar_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新 Pinbar 配置

        :param config: 配置字典，包含各项 Pinbar 参数
        :return: 更新后的配置
        """
        current = await self.get_pinbar_config()
        current.update(config)

        await self.repo.set_secret("pinbar_config", json.dumps(current))
        return current

    async def update_webhook_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新 Webhook 配置

        :param config: 配置字典，包含各推送通道配置
        :return: 更新后的配置
        """
        if "global_push_enabled" in config and config["global_push_enabled"] is not None:
            await self.repo.set_secret(
                "global_push_enabled",
                str(config["global_push_enabled"]).lower()
            )

        if "feishu_enabled" in config and config["feishu_enabled"] is not None:
            await self.repo.set_secret(
                "feishu_enabled",
                str(config["feishu_enabled"]).lower()
            )

        if "feishu_secret" in config and config["feishu_secret"] is not None:
            await self.repo.set_secret("feishu_webhook_url", config["feishu_secret"])

        if "wecom_enabled" in config and config["wecom_enabled"] is not None:
            await self.repo.set_secret(
                "wecom_enabled",
                str(config["wecom_enabled"]).lower()
            )

        if "wecom_secret" in config and config["wecom_secret"] is not None:
            await self.repo.set_secret("wecom_webhook_url", config["wecom_secret"])

        return await self.get_webhook_config()

    async def get_push_config(self) -> Dict[str, Any]:
        """
        获取推送配置
        返回各推送通道的启用状态、密钥和服务器配置
        """
        # 获取全局推送开关
        global_push_enabled_val = await self.repo.get_secret("global_push_enabled")
        global_push_enabled = global_push_enabled_val.lower() == "true" if global_push_enabled_val else True

        # 获取飞书配置
        feishu_enabled_val = await self.repo.get_secret("feishu_enabled")
        feishu_enabled = feishu_enabled_val.lower() == "true" if feishu_enabled_val else False
        feishu_webhook_url = await self.repo.get_secret("feishu_webhook_url")

        # 获取企业微信配置
        wecom_enabled_val = await self.repo.get_secret("wecom_enabled")
        wecom_enabled = wecom_enabled_val.lower() == "true" if wecom_enabled_val else False
        wecom_webhook_url = await self.repo.get_secret("wecom_webhook_url")

        # 获取 Telegram 配置
        telegram_enabled_val = await self.repo.get_secret("telegram_enabled")
        telegram_enabled = telegram_enabled_val.lower() == "true" if telegram_enabled_val else False
        telegram_bot_token = await self.repo.get_secret("telegram_bot_token")
        telegram_chat_id = await self.repo.get_secret("telegram_chat_id")

        return {
            "global_push_enabled": global_push_enabled,
            "feishu_enabled": feishu_enabled,
            "feishu_webhook_url": feishu_webhook_url if feishu_webhook_url else "",
            "wecom_enabled": wecom_enabled,
            "wecom_webhook_url": wecom_webhook_url if wecom_webhook_url else "",
            "telegram_enabled": telegram_enabled,
            "telegram_bot_token": telegram_bot_token if telegram_bot_token else "",
            "telegram_chat_id": telegram_chat_id if telegram_chat_id else "",
        }

    async def update_push_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新推送配置

        :param config: 配置字典，包含各推送通道配置
        :return: 更新后的配置
        """
        if "global_push_enabled" in config and config["global_push_enabled"] is not None:
            await self.repo.set_secret(
                "global_push_enabled",
                str(config["global_push_enabled"]).lower()
            )

        if "feishu_enabled" in config and config["feishu_enabled"] is not None:
            await self.repo.set_secret(
                "feishu_enabled",
                str(config["feishu_enabled"]).lower()
            )

        if "feishu_webhook_url" in config and config["feishu_webhook_url"] is not None:
            await self.repo.set_secret("feishu_webhook_url", config["feishu_webhook_url"])

        if "wecom_enabled" in config and config["wecom_enabled"] is not None:
            await self.repo.set_secret(
                "wecom_enabled",
                str(config["wecom_enabled"]).lower()
            )

        if "wecom_webhook_url" in config and config["wecom_webhook_url"] is not None:
            await self.repo.set_secret("wecom_webhook_url", config["wecom_webhook_url"])

        if "telegram_enabled" in config and config["telegram_enabled"] is not None:
            await self.repo.set_secret(
                "telegram_enabled",
                str(config["telegram_enabled"]).lower()
            )

        if "telegram_bot_token" in config and config["telegram_bot_token"] is not None:
            await self.repo.set_secret("telegram_bot_token", config["telegram_bot_token"])

        if "telegram_chat_id" in config and config["telegram_chat_id"] is not None:
            await self.repo.set_secret("telegram_chat_id", config["telegram_chat_id"])

        return await self.get_push_config()

    async def get_exchange_config(self) -> Dict[str, Any]:
        """
        获取交易所配置
        返回 Binance API 密钥配置（密钥脱敏）
        """
        api_key = await self.repo.get_secret("binance_api_key")
        api_secret_exists = bool(await self.repo.get_secret("binance_api_secret"))

        # 获取 API 权限配置（如果有）
        api_permissions_val = await self.repo.get_secret("binance_api_permissions")
        api_permissions = None
        if api_permissions_val:
            try:
                api_permissions = json.loads(api_permissions_val)
            except json.JSONDecodeError:
                pass

        # 获取测试网配置
        use_testnet_val = await self.repo.get_secret("binance_use_testnet")
        use_testnet = use_testnet_val.lower() == "true" if use_testnet_val else False

        # 脱敏显示 API Key
        masked_api_key = ""
        if api_key and len(api_key) > 8:
            masked_api_key = f"{api_key[:4]}***{api_key[-4:]}"

        return {
            "binance_api_key": masked_api_key,
            "has_binance_api_secret": api_secret_exists,
            "api_permissions": api_permissions,
            "use_testnet": use_testnet,
        }

    async def update_exchange_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新交易所配置

        :param config: 配置字典，包含 API 密钥等配置
        :return: 更新后的配置
        """
        if "binance_api_key" in config and config["binance_api_key"] is not None:
            await self.repo.set_secret("binance_api_key", config["binance_api_key"])

        if "binance_api_secret" in config and config["binance_api_secret"] is not None:
            await self.repo.set_secret("binance_api_secret", config["binance_api_secret"])

        if "use_testnet" in config and config["use_testnet"] is not None:
            await self.repo.set_secret(
                "binance_use_testnet",
                str(config["use_testnet"]).lower()
            )

        if "api_permissions" in config and config["api_permissions"] is not None:
            await self.repo.set_secret(
                "binance_api_permissions",
                json.dumps(config["api_permissions"])
            )

        return await self.get_exchange_config()

    async def get_all_config_for_export(self) -> Dict[str, Any]:
        """
        获取所有配置用于导出
        敏感字段（API Key/Secret、Webhook URL）会被置空
        导出结构与导入结构对应

        :return: 所有配置的字典
        """
        from datetime import datetime

        # 获取各部分配置
        system_config = await self.get_system_config()
        monitor_config = await self.get_monitor_config()
        risk_config = await self.get_risk_config()
        scoring_config = await self.get_scoring_config()
        pinbar_config = await self.get_pinbar_config()
        push_config = await self.get_push_config()
        exchange_config = await self.get_exchange_config()

        # 组织导出结构（与导入结构对应）
        # 安全：排除 4 项敏感信息 - binance_api_key, binance_api_secret, feishu_webhook_url, wecom_webhook_url
        return {
            "# CryptoRadar 配置导出": f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "export_timestamp": datetime.now().isoformat(),
            "version": "1.0",
            "exchange_settings": {
                "binance_api_key": "",  # 安全：置空
                "binance_api_secret": "",  # 安全：置空
                "use_testnet": exchange_config.get("use_testnet", False),
                "api_permissions": exchange_config.get("api_permissions"),
            },
            "monitor_config": {
                "active_symbols": system_config.get("active_symbols", []),
                "monitor_intervals": monitor_config.get("monitor_intervals", {}),
            },
            "pinbar_config": pinbar_config,
            "risk_config": risk_config,
            "scoring_config": scoring_config,  # 导出完整打分配置
            "push_config": {
                # 安全：webhook URL 置空，仅导出启用状态和开关
                "global_push_enabled": push_config.get("global_push_enabled", True),
                "feishu_enabled": push_config.get("feishu_enabled", False),
                "feishu_webhook_url": "",  # 安全：置空
                "wecom_enabled": push_config.get("wecom_enabled", False),
                "wecom_webhook_url": "",  # 安全：置空
                "telegram_enabled": push_config.get("telegram_enabled", False),
                "telegram_bot_token": "",  # 安全：置空
                "telegram_chat_id": "",  # 安全：置空
            },
        }

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        校验配置数据的合法性

        :param config: 待校验的配置字典
        :raises ConfigValidationError: 校验失败时抛出
        """
        # === 1. 校验 monitor_intervals 至少保留一个级别 ===
        monitor_config = config.get("monitor_config", {})
        monitor_intervals = monitor_config.get("monitor_intervals", {})
        if isinstance(monitor_intervals, dict) and len(monitor_intervals) == 0:
            raise ConfigValidationError("监控配置：至少需要保留一个监控级别")
        if isinstance(monitor_intervals, list) and len(monitor_intervals) == 0:
            raise ConfigValidationError("监控配置：至少需要保留一个监控级别")

        # === 2. 校验打分权重总和为 1.0 ===
        # 兼容 scoring_config（新格式）和 scoring_weights（旧格式）
        scoring_weights = config.get("scoring_config") or config.get("scoring_weights", {})
        if scoring_weights:
            w_shape = float(scoring_weights.get("w_shape", 0))
            w_trend = float(scoring_weights.get("w_trend", 0))
            w_vol = float(scoring_weights.get("w_vol", 0))
            total = round(w_shape + w_trend + w_vol, 4)
            if abs(total - 1.0) > 0.0001:
                raise ConfigValidationError(
                    f"打分权重总和必须为 1.0，当前总和为 {total} "
                    f"(w_shape={w_shape}, w_trend={w_trend}, w_vol={w_vol})"
                )

        # === 3. 校验风险参数范围 ===
        risk_config = config.get("risk_config", {})
        if risk_config:
            # 只校验提供的字段
            if "risk_pct" in risk_config:
                risk_pct = float(risk_config["risk_pct"])
                if not (0.005 <= risk_pct <= 0.1):
                    raise ConfigValidationError(
                        f"风险配置：risk_pct 必须在 0.005-0.1 范围内，当前为 {risk_pct}"
                    )
            if "max_sl_dist" in risk_config:
                max_sl_dist = float(risk_config["max_sl_dist"])
                if not (0.01 <= max_sl_dist <= 0.1):
                    raise ConfigValidationError(
                        f"风险配置：max_sl_dist 必须在 0.01-0.1 范围内，当前为 {max_sl_dist}"
                    )
            if "max_leverage" in risk_config:
                max_leverage = float(risk_config["max_leverage"])
                if not (1 <= max_leverage <= 125):
                    raise ConfigValidationError(
                        f"风险配置：max_leverage 必须在 1-125 范围内，当前为 {max_leverage}"
                    )

        # === 4. 校验 Pinbar 参数范围 ===
        pinbar_config = config.get("pinbar_config", {})
        if pinbar_config:
            # 只校验提供的字段
            if "body_max_ratio" in pinbar_config:
                body_max_ratio = float(pinbar_config["body_max_ratio"])
                if not (0.05 <= body_max_ratio <= 0.8):
                    raise ConfigValidationError(
                        f"Pinbar 配置：body_max_ratio 必须在 0.05-0.8 范围内，当前为 {body_max_ratio}"
                    )

            if "shadow_min_ratio" in pinbar_config:
                shadow_min_ratio = float(pinbar_config["shadow_min_ratio"])
                if not (1.0 <= shadow_min_ratio <= 10.0):
                    raise ConfigValidationError(
                        f"Pinbar 配置：shadow_min_ratio 必须在 1.0-10.0 范围内，当前为 {shadow_min_ratio}"
                    )

            if "volatility_atr_multiplier" in pinbar_config:
                volatility_atr_multiplier = float(pinbar_config["volatility_atr_multiplier"])
                if not (0.5 <= volatility_atr_multiplier <= 5.0):
                    raise ConfigValidationError(
                        f"Pinbar 配置：volatility_atr_multiplier 必须在 0.5-5.0 范围内，当前为 {volatility_atr_multiplier}"
                    )

    async def import_config_from_yaml(self, config: Dict[str, Any], engine: Any = None) -> Dict[str, Any]:
        """
        从 YAML 配置字典导入配置
        包含完整的校验逻辑，支持导入所有配置项（包括敏感信息）

        :param config: 解析后的 YAML 配置字典
        :param engine: 引擎实例，用于更新内存配置
        :return: 导入后的配置摘要
        :raises ConfigValidationError: 校验失败时抛出
        """
        # 校验配置
        self._validate_config(config)

        result = {}

        # === 导入监控配置 ===
        monitor_config = config.get("monitor_config", {})
        if monitor_config:
            active_symbols = monitor_config.get("active_symbols", [])
            monitor_intervals = monitor_config.get("monitor_intervals", {})
            if active_symbols:
                await self.repo.set_secret("active_symbols", json.dumps(active_symbols))
            if monitor_intervals:
                await self.repo.set_secret("monitor_intervals", json.dumps(monitor_intervals))
            result["monitor_config"] = monitor_config

        # === 导入推送配置（支持 webhook URL）===
        push_config = config.get("push_config", {})
        if push_config:
            await self.update_push_config(push_config)
            result["push_config"] = push_config

        # === 导入 Pinbar 配置 ===
        pinbar_config = config.get("pinbar_config", {})
        if pinbar_config:
            await self.update_pinbar_config(pinbar_config)
            result["pinbar_config"] = pinbar_config

        # === 导入打分配置（兼容 scoring_config 和 scoring_weights 两种格式）===
        scoring_config = config.get("scoring_config")
        scoring_weights = config.get("scoring_weights")
        if scoring_config:
            # 新格式：完整的 scoring_config
            await self.update_scoring_config(scoring_config)
            result["scoring_config"] = scoring_config
        elif scoring_weights:
            # 旧格式：仅权重
            await self.update_scoring_config(scoring_weights)
            result["scoring_weights"] = scoring_weights

        # === 导入风险配置 ===
        risk_config = config.get("risk_config", {})
        if risk_config:
            await self.update_risk_config(risk_config)
            result["risk_config"] = risk_config

        # === 导入交易所配置（支持导入 API 密钥）===
        exchange_settings = config.get("exchange_settings", {})
        if exchange_settings:
            # 支持导入所有字段，包括 API 密钥（如果 YAML 中存在且非空）
            exchange = {}
            for k, v in exchange_settings.items():
                # 跳过空值的敏感字段（导出的配置会置空这些字段）
                if k in ["binance_api_key", "binance_api_secret"] and not v:
                    continue
                exchange[k] = v
            if exchange:
                await self.update_exchange_config(exchange)
            # 记录导入结果
            if exchange_settings.get("binance_api_key"):
                result["exchange_settings"] = {"note": "API 密钥已导入"}
            elif exchange:
                result["exchange_settings"] = {"note": "已导入非敏感配置项"}

        # === 更新引擎内存配置 ===
        if engine:
            if monitor_config:
                if "active_symbols" in monitor_config:
                    engine.active_symbols = monitor_config["active_symbols"]
                if "monitor_intervals" in monitor_config:
                    intervals_data = monitor_config["monitor_intervals"]
                    engine.monitor_intervals = {
                        k: IntervalConfig(**v) if isinstance(v, dict) else v
                        for k, v in intervals_data.items()
                    }
            if risk_config:
                if "risk_pct" in risk_config:
                    engine.risk_pct = risk_config["risk_pct"]
                if "max_sl_dist" in risk_config:
                    engine.max_sl_dist = risk_config["max_sl_dist"]
                if "max_leverage" in risk_config:
                    engine.max_leverage = risk_config["max_leverage"]
            if pinbar_config:
                engine.pinbar_config = PinbarConfig(**pinbar_config)
            # 处理打分配置更新引擎
            if scoring_config:
                engine.scoring_config = ScoringConfig(**scoring_config)
            elif scoring_weights:
                engine.scoring_config = ScoringConfig(**scoring_weights)

        logger.info(f"配置导入完成：{list(result.keys())}")
        return result
