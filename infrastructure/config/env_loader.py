"""
基础设施层：环境变量加载模块
使用 python-dotenv 加载根目录 .env 文件，提供配置读取和验证功能。
"""
import os
import logging
from typing import Optional, Tuple
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 环境变量缓存
_env_loaded = False


def load_env() -> None:
    """
    加载项目根目录的 .env 文件
    只在首次调用时加载，避免重复 I/O
    """
    global _env_loaded
    if _env_loaded:
        return

    # 查找 .env 文件（支持多级目录）
    possible_paths = [
        Path(__file__).parent.parent.parent / ".env",  # 项目根目录
        Path(__file__).parent.parent / ".env",  # infrastructure/.env
        Path.cwd() / ".env",  # 当前工作目录
        Path.cwd() / "config" / ".env",  # config/.env
    ]

    env_file = None
    for path in possible_paths:
        if path.exists():
            env_file = path
            break

    if env_file:
        load_dotenv(env_file)
        logger.info(f"已加载环境变量文件：{env_file}")
        _env_loaded = True
    else:
        logger.warning("未找到 .env 文件，将使用系统环境变量")
        _env_loaded = True  # 标记已尝试加载


def get_required_env(key: str) -> str:
    """
    获取必填环境变量，如果不存在则抛出异常

    :param key: 环境变量名
    :return: 环境变量值
    :raises ValueError: 如果环境变量不存在
    """
    value = os.getenv(key)
    if value is None or value.strip() == "":
        raise ValueError(f"必填环境变量 {key} 未配置")
    return value.strip()


def get_optional_env(key: str, default: str = "") -> Optional[str]:
    """
    获取可选环境变量，如果不存在则返回默认值

    :param key: 环境变量名
    :param default: 默认值
    :return: 环境变量值或默认值
    """
    return os.getenv(key, default)


def get_bool_env(key: str, default: bool = False) -> bool:
    """
    获取布尔型环境变量

    :param key: 环境变量名
    :param default: 默认值
    :return: True/False
    """
    value = os.getenv(key, "").lower().strip()
    if value == "":
        return default
    return value in ("true", "1", "yes", "on")


def get_binance_config() -> Tuple[str, str]:
    """
    获取币安 API 配置

    :return: (api_key, api_secret) 元组
    :raises ValueError: 如果配置不完整
    """
    load_env()
    api_key = get_required_env("BINANCE_API_KEY")
    api_secret = get_required_env("BINANCE_API_SECRET")
    return api_key, api_secret


def get_push_config() -> dict:
    """
    获取推送配置

    :return: 推送配置字典
    """
    load_env()
    return {
        "global_enabled": get_bool_env("GLOBAL_PUSH_ENABLED", True),
        "feishu": {
            "enabled": get_bool_env("FEISHU_ENABLED", False),
            "webhook_url": get_optional_env("FEISHU_WEBHOOK_URL"),
        },
        "wecom": {
            "enabled": get_bool_env("WECOM_ENABLED", False),
            "webhook_url": get_optional_env("WECOM_WEBHOOK_URL"),
        },
    }


def validate_required_config() -> None:
    """
    验证必填环境变量是否已配置

    :raises ValueError: 如果有必填项未配置
    """
    load_env()
    missing = []

    # 币安 API 是必填的
    if not os.getenv("BINANCE_API_KEY") or os.getenv("BINANCE_API_KEY").strip() == "":
        missing.append("BINANCE_API_KEY")
    if not os.getenv("BINANCE_API_SECRET") or os.getenv("BINANCE_API_SECRET").strip() == "":
        missing.append("BINANCE_API_SECRET")

    if missing:
        error_msg = f"必填环境变量未配置：{', '.join(missing)}\n\n"
        error_msg += "操作步骤：\n"
        error_msg += "1. 复制 .env.example 到项目根目录\n"
        error_msg += "2. 编辑 .env 文件并填写配置\n"
        error_msg += "3. 重启应用"
        raise ValueError(error_msg)

    logger.info("环境变量验证通过")
