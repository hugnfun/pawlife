"""
加密服务。

使用 Fernet (AES-128-CBC) 对敏感字段进行加密存储。
支持配置自动生成和优雅降级。
"""

import base64
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Fernet key 缓存
_fernet_key: Optional[bytes] = None
_fernet = None


def _generate_fernet_key() -> bytes:
    """生成 Fernet 兼容的密钥（32 字节 URL-safe base64 编码）。

    Returns:
        Fernet 密钥
    """
    key = base64.urlsafe_b64encode(os.urandom(32))
    return key


def _get_fernet_key(settings_key: Optional[str] = None) -> bytes:
    """获取 Fernet 密钥。

    优先使用配置中的密钥，否则自动生成。
    自动生成的密钥在进程生命周期内保持不变。

    Args:
        settings_key: 从配置中获取的密钥

    Returns:
        Fernet 密钥
    """
    global _fernet_key

    if _fernet_key is not None:
        return _fernet_key

    if settings_key:
        # 如果密钥长度不足 32 字节，通过 SHA256 扩展
        if len(settings_key) < 32:
            settings_key = hashlib.sha256(settings_key.encode()).hexdigest()
        _fernet_key = base64.urlsafe_b64encode(settings_key[:32].encode())
    else:
        _fernet_key = _generate_fernet_key()
        logger.warning("未配置加密密钥，使用自动生成的临时密钥。生产环境请设置 ENCRYPTION_KEY 环境变量。")

    return _fernet_key


def _get_fernet():
    """懒加载 Fernet 实例。"""
    global _fernet

    if _fernet is None:
        try:
            from cryptography.fernet import Fernet
            key = _get_fernet_key()
            _fernet = Fernet(key)
        except ImportError:
            logger.warning("cryptography 库未安装，加密功能不可用。运行: pip install cryptography")
            return None

    return _fernet


def encrypt(plaintext: str) -> str:
    """加密字符串。

    Args:
        plaintext: 明文

    Returns:
        加密后的 base64 字符串。如果加密不可用，返回原始字符串。
    """
    if not plaintext:
        return plaintext

    f = _get_fernet()
    if f is None:
        return plaintext

    try:
        encrypted = f.encrypt(plaintext.encode("utf-8"))
        return encrypted.decode("utf-8")
    except Exception as e:
        logger.error(f"加密失败: {e}")
        return plaintext


def decrypt(ciphertext: str) -> str:
    """解密字符串。

    Args:
        ciphertext: 密文

    Returns:
        解密后的明文。如果解密不可用或失败，返回原始字符串。
    """
    if not ciphertext:
        return ciphertext

    f = _get_fernet()
    if f is None:
        return ciphertext

    try:
        decrypted = f.decrypt(ciphertext.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception as e:
        logger.error(f"解密失败: {e}")
        return ciphertext


def is_encrypted(value: str) -> bool:
    """检查字符串是否已加密。

    Fernet 加密的结果总是以 gAAAAA 开头的 base64 字符串。

    Args:
        value: 待检查的字符串

    Returns:
        是否已加密
    """
    if not value or len(value) < 10:
        return False
    try:
        decoded = base64.b64decode(value[:20])
        return decoded[:1] == b"\x80"  # Fernet version byte
    except Exception:
        return False


def hash_sensitive(value: str) -> str:
    """对敏感数据进行单向哈希（用于比较，不可逆）。

    Args:
        value: 原始值

    Returns:
        SHA256 哈希值
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def init_encryption(settings_key: Optional[str] = None):
    """初始化加密服务。

    应在应用启动时调用。

    Args:
        settings_key: 从配置中获取的密钥
    """
    _get_fernet_key(settings_key)
    _get_fernet()
    logger.info("加密服务初始化完成")
