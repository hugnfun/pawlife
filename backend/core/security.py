"""
安全工具模块。

提供 JWT 令牌生成和验证、密码哈希等安全相关功能。
使用 python-jose 处理 JWT。
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from uuid import UUID

from jose import jwt
from passlib.context import CryptContext

from .config import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: UUID,
    extra_claims: Optional[Dict[str, str]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建 JWT 访问令牌。

    Args:
        subject: 用户 ID（UUID）
        extra_claims: 额外的声明信息
        expires_delta: 过期时间增量，如果不指定则使用配置默认值

    Returns:
        str: 编码后的 JWT 令牌
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    claims = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "token_type": "access",
    }

    if extra_claims:
        claims.update(extra_claims)

    encoded_jwt = jwt.encode(
        claims,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def create_refresh_token(
    subject: UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建 JWT 刷新令牌。

    Args:
        subject: 用户 ID（UUID）
        expires_delta: 过期时间增量，如果不指定则使用配置默认值

    Returns:
        str: 编码后的 JWT 刷新令牌
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.refresh_token_expire_days
        )

    claims = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "token_type": "refresh",
    }

    encoded_jwt = jwt.encode(
        claims,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, str]]:
    """解码并验证 JWT 令牌。

    Args:
        token: JWT 令牌字符串

    Returns:
        如果令牌有效返回声明字典，无效返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": True},
        )
        return payload
    except jwt.JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[UUID]:
    """从令牌中提取用户 ID。

    Args:
        token: JWT 令牌字符串

    Returns:
        如果令牌有效返回用户 UUID，无效返回 None
    """
    payload = decode_token(token)
    if payload is None:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        return UUID(user_id_str)
    except ValueError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否匹配。

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希。

    Args:
        password: 明文密码

    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)
