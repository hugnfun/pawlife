"""
Consul 配置提供者。

从 Consul KV 读取配置，作为环境变量的补充来源。
支持优雅降级：Consul 不可用时自动回退到环境变量。
"""

import logging
from typing import Any, Dict, Optional

from core.config import settings

logger = logging.getLogger(__name__)

_consul_client: Optional[Any] = None


def _get_client():
    """懒加载 Consul 客户端。"""
    global _consul_client

    if _consul_client is not None:
        return _consul_client

    if not settings.consul_enabled:
        return None

    try:
        import consul
        _consul_client = consul.Consul(
            host=settings.consul_host,
            port=settings.consul_port,
            token=settings.consul_token,
            scheme="http",
        )
        # 健康检查
        _consul_client.agent.self()
        logger.info(f"Consul 连接成功: {settings.consul_host}:{settings.consul_port}")
        return _consul_client
    except ImportError:
        logger.warning("python-consul 库未安装。运行: pip install python-consul")
        return None
    except Exception as e:
        logger.warning(f"Consul 连接失败: {e}，将回退到环境变量")
        return None


def get_config(key: str, default: Any = None) -> Any:
    """从 Consul KV 读取配置。

    配置键格式: pawlife/config/DATABASE_URL
    在 KV 中存储为: {consul_kv_prefix}/{key}

    Args:
        key: 配置键（不含前缀）
        default: 默认值（Consul 不可用或 key 不存在时返回）

    Returns:
        配置值
    """
    client = _get_client()
    if client is None:
        return default

    try:
        full_key = f"{settings.consul_kv_prefix}/{key}"
        _, data = client.kv.get(full_key)

        if data and data["Value"]:
            value = data["Value"].decode("utf-8")
            logger.debug(f"Consul 配置: {key} = {value[:20]}...")
            return value
        return default
    except Exception as e:
        logger.warning(f"读取 Consul 配置失败 [{key}]: {e}")
        return default


def get_all_configs() -> Dict[str, str]:
    """获取 Consul KV 前缀下的所有配置。

    Returns:
        所有配置的字典 {key: value}
    """
    client = _get_client()
    if client is None:
        return {}

    try:
        _, data = client.kv.get(settings.consul_kv_prefix, keys=True)
        if not data:
            return {}

        configs = {}
        for key in data.get("Keys", []):
            short_key = key.replace(f"{settings.consul_kv_prefix}/", "")
            value = get_config(short_key)
            if value is not None:
                configs[short_key] = value

        return configs
    except Exception as e:
        logger.warning(f"读取 Consul 所有配置失败: {e}")
        return {}


def health_check() -> bool:
    """Consul 健康检查。"""
    client = _get_client()
    if client is None:
        return False

    try:
        client.agent.self()
        return True
    except Exception:
        return False
