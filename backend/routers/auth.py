"""
认证相关 API 路由。

处理微信小程序登录、用户注册/登录、会话管理等。
"""

import logging
import httpx
import uuid
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from schemas.auth import (
    WechatLoginRequest,
    WechatLoginResponse,
    UserProfile,
    TokenResponse,
)
from services.database import get_db
from services.redis import get_redis, RedisService
from core.config import settings
from core.security import create_access_token, create_refresh_token

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/auth", tags=["认证"])

# OAuth2 配置
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)

# 创建 HTTP 客户端
async def get_httpx_client() -> httpx.AsyncClient:
    """获取异步 HTTP 客户端。"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


@router.post(
    "/wechat-login",
    response_model=WechatLoginResponse,
    summary="微信小程序登录",
    description="使用微信 code 进行登录或注册。"
)
async def wechat_login(
    request: WechatLoginRequest,
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    client: httpx.AsyncClient = Depends(get_httpx_client),
) -> WechatLoginResponse:
    """微信小程序登录接口。

    Args:
        request: 包含微信登录 code 的请求体
        db: 数据库会话
        redis_service: Redis 服务
        client: HTTP 客户端

    Returns:
        WechatLoginResponse: 登录响应，包含用户信息和 token

    Raises:
        HTTPException: 微信登录失败或服务器错误
    """
    try:
        # 1. 调用微信 API 获取 openid 和 session_key
        wechat_data = await _get_wechat_session(request.code, client)
        openid = wechat_data.get("openid")
        unionid = wechat_data.get("unionid")
        session_key = wechat_data.get("session_key")
        errcode = wechat_data.get("errcode")

        # 微信返回错误码处理
        if errcode is not None and errcode != 0:
            errmsg = wechat_data.get("errmsg", "未知错误")
            logger.error(f"微信登录失败: errcode={errcode}, errmsg={errmsg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"微信登录失败: {errmsg}"
            )

        if not openid:
            logger.error(f"微信登录未返回 openid: {wechat_data}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="微信登录失败，请重试"
            )

        # 2. 查询或创建用户
        async with db.begin():
            # 尝试查找已有用户
            from sqlalchemy import select
            stmt = select(User).where(User.wechat_openid == openid)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if user is None:
                # 新用户注册
                user = User(
                    wechat_openid=openid,
                    wechat_unionid=unionid,
                    nickname=request.nickname,
                    avatar_url=request.avatar_url,
                    role=UserRole.USER,
                    is_active=True,
                    last_login_at=datetime.utcnow(),
                )
                db.add(user)
                await db.flush()  # 获取生成的 ID
                logger.info(f"新用户注册完成: user_id={user.id}, openid={openid}")
            else:
                # 更新最后登录时间
                user.last_login_at = datetime.utcnow()
                if request.nickname and not user.nickname:
                    user.nickname = request.nickname
                if request.avatar_url and not user.avatar_url:
                        user.avatar_url = request.avatar_url
                # 如果有 unionid 但之前没有保存，更新它
                if unionid and not user.wechat_unionid:
                    user.wechat_unionid = unionid
                logger.info(f"用户登录成功: user_id={user.id}, openid={openid}")

            await db.commit()

        # 3. 生成 JWT 访问令牌
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            subject=user.id,
            extra_claims={
                "role": user.role.value,
                "nickname": user.nickname or "",
            },
            expires_delta=access_token_expires,
        )
        refresh_token = create_refresh_token(subject=user.id)

        # 4. 在 Redis 中存储会话上下文和 session_key（用于后续微信消息解密）
        session_id = f"session_{user.id}_{datetime.utcnow().timestamp()}"
        session_context = {
            "user_id": str(user.id),
            "openid": openid,
            "session_key": session_key,
            "role": user.role.value,
            "nickname": user.nickname,
        }
        await redis_service.set_session_context(session_id, session_context)

        # 5. 返回响应
        expires_in = int(settings.access_token_expire_minutes * 60)
        return WechatLoginResponse(
            success=True,
            message="登录成功",
            data=UserProfile(
                id=user.id,
                wechat_openid=user.wechat_openid,
                nickname=user.nickname,
                avatar_url=user.avatar_url,
                phone_number=user.phone_number,
                role=user.role,
                is_active=user.is_active,
                last_login_at=user.last_login_at,
            ),
            token=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=expires_in,
                session_id=session_id,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"微信登录异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )


@router.get(
    "/profile",
    response_model=UserProfile,
    summary="获取用户资料",
    description="获取当前登录用户的详细资料。"
)
async def get_profile(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    """获取当前用户资料接口。

    Args:
        token: OAuth2 token
        db: 数据库会话

    Returns:
        UserProfile: 用户资料

    Raises:
        HTTPException: 未认证或用户不存在
    """
    # 简化的 token 验证
    if not token or not token.startswith("user_token_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证或 token 无效"
        )

    # 提取 user_id
    try:
        user_id = token.replace("user_token_", "")
        user_uuid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 格式错误"
        )

    # 查询用户
    from sqlalchemy import select
    stmt = select(User).where(User.id == user_uuid, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在或已被禁用"
        )

    return UserProfile(
        id=user.id,
        wechat_openid=user.wechat_openid,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        phone_number=user.phone_number,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
    )


@router.post(
    "/logout",
    summary="用户登出",
    description="登出当前用户，清除会话信息。"
)
async def logout(
    session_id: str,
    redis_service: RedisService = Depends(get_redis),
) -> dict:
    """用户登出接口。

    Args:
        session_id: 会话ID
        redis_service: Redis 服务

    Returns:
        dict: 登出结果
    """
    try:
        # 删除会话上下文
        await redis_service.delete_session_context(session_id)
        return {"success": True, "message": "登出成功"}
    except Exception as e:
        logger.error(f"登出失败: {e}")
        return {"success": False, "message": "登出失败"}


async def _get_wechat_session(code: str, client: httpx.AsyncClient) -> dict:
    """调用微信官方 API 获取 session 信息。

    使用微信接口：https://api.weixin.qq.com/sns/jscode2session

    Args:
        code: 微信登录 code
        client: HTTP 客户端

    Returns:
        dict: 包含 openid, session_key, unionid 等信息的字典

    Raises:
        httpx.HTTPError: HTTP 请求错误
    """
    # 检查配置
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        logger.warning("微信配置未设置，使用模拟返回（开发模式）")
        return {
            "openid": f"mock_openid_{code[:10]}",
            "session_key": "mock_session_key",
            "unionid": f"mock_unionid_{code[:10]}" if len(code) > 10 else None,
        }

    # 构建请求 URL
    params = {
        "appid": settings.wechat_app_id,
        "secret": settings.wechat_app_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    # 调用微信 API
    response = await client.get(settings.wechat_login_url, params=params)
    response.raise_for_status()

    return response.json()