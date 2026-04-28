"""
Vault 密钥提供者。

从 HashiCorp Vault 读取敏感配置（DB 密码、API key 等）。
支持优雅降级：Vault 不可用时自动回退到环境变量。
"""

import logging
from typing import Any, Dict, Optional

from core.config import settings

logger = logging.getLogger(__name__)

_vault_client: Optional[Any] = None


def _get_client():
    """懒加载 Vault 客户端。"""
    global _vault_client

    if _vault_client is not None:
        return _vault_client

    if not settings.vault_enabled:
        return None

    try:
        import hvac
        _vault_client = hvac.Client(
            url=settings.vault_addr,
            token=settings.vault_token,
        )

        if not _vault_client.is_authenticated():
            logger.warning("Vault 认证失败，请检查 VAULT_TOKEN")
            _vault_client = None
            return None

        logger.info(f"Vault 连接成功: {settings.vault_addr}")
        return _vault_client
    except ImportError:
        logger.warning("hvac 库未安装。运行: pip install hvac")
        return None
    except Exception as e:
        logger.warning(f"Vault 连接失败: {e}，将回退到环境变量")
        return None


def get_secret(key: str, default: Any = None, version: Optional[int] = None) -> Any:
    """从 Vault KV 读取密钥。

    路径: {vault_kv_mount}/data/{vault_kv_path}/{key}
    使用 KV v2 API。

    Args:
        key: 密钥名
        default: 默认值（Vault 不可用或 key 不存在时返回）
        version: KV 版本号（None 表示最新版本）

    Returns:
        密钥值
    """
    client = _get_client()
    if client is None:
        return default

    try:
        path = f"{settings.vault_kv_mount}/data/{settings.vault_kv_path}"
        read_kwargs: Dict[str, Any] = {"mount_point": settings.vault_kv_mount}
        if version is not None:
            read_kwargs["version"] = version

        response = client.secrets.kv.v2.read_secret_version(
            path=settings.vault_kv_path,
            mount_point=settings.vault_kv_mount,
            version=version,
        )

        data = response.get("data", {}).get("data", {})
        value = data.get(key)

        if value is not None:
            logger.debug(f"Vault 密钥读取成功: {key}")
            return value

        return default
    except Exception as e:
        logger.warning(f"Vault 密钥读取失败 [{key}]: {e}")
        return default


def get_all_secrets() -> Dict[str, str]:
    """获取 Vault KV 路径下的所有密钥。

    Returns:
        所有密钥的字典 {key: value}
    """
    client = _get_client()
    if client is None:
        return {}

    try:
        response = client.secrets.kv.v2.read_secret_version(
            path=settings.vault_kv_path,
            mount_point=settings.vault_kv_mount,
        )
        return response.get("data", {}).get("data", {})
    except Exception as e:
        logger.warning(f"Vault 读取所有密钥失败: {e}")
        return {}


def health_check() -> bool:
    """Vault 健康检查。"""
    client = _get_client()
    if client is None:
        return False

    try:
        client.sys.health()
        return True
    except Exception:
        return False
