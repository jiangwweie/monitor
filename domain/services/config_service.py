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
            "system_enabled": True,  # 默认启用，实际状态由引擎控制
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
