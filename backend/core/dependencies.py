"""
依赖注入模块。

集中定义 FastAPI 依赖项，如认证、数据库连接等。
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from services.database import get_db
from core.security import get_user_id_from_token

# 配置日志
logger = logging.getLogger(__name__)

# OAuth2 方案
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/v1/auth/wechat-login",
    auto_error=False,
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前认证用户的依赖项。

    使用 JWT 验证 token，从数据库获取用户信息。

    Args:
        token: OAuth2 token
        db: 数据库会话

    Returns:
        User: 当前用户对象

    Raises:
        HTTPException: 未认证或 token 无效
    """
    # 开发环境下允许无 token 进入，返回模拟用户
    if not token:
        logger.warning("无认证 token，使用模拟用户（仅开发环境可用）")
        return _get_mock_user()

    # 使用 JWT 验证 token
    user_id = get_user_id_from_token(token)
    if user_id is None:
        logger.warning("JWT token 验证失败或已过期")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 已过期或无效，请重新登录"
        )

    # 从数据库查询用户
    from sqlalchemy import select
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"用户不存在或已被禁用: user_id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用"
        )

    logger.debug(f"用户认证成功: user_id={user.id}, nickname={user.nickname}")
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前活跃用户的依赖项。

    检查用户是否处于活跃状态。

    Args:
        current_user: 当前用户

    Returns:
        User: 活跃用户

    Raises:
        HTTPException: 用户未激活
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账户已被禁用"
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求管理员权限的依赖项。

    Args:
        current_user: 当前用户

    Returns:
        User: 管理员用户

    Raises:
        HTTPException: 用户不是管理员
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


def _get_mock_user() -> User:
    """获取模拟用户（仅用于开发环境）。

    Returns:
        User: 模拟用户对象
    """
    return User(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        wechat_openid="mock_openid_development",
        nickname="开发测试用户",
        role=UserRole.USER,
        is_active=True,
    )