"""
认证相关的 Pydantic 模型。

用于 API 请求/响应数据验证和序列化。
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from models.user import UserRole


class WechatLoginRequest(BaseModel):
    """微信登录请求模型。"""

    code: str = Field(..., description="微信登录 code")
    nickname: Optional[str] = Field(None, description="用户昵称")
    avatar_url: Optional[str] = Field(None, description="用户头像 URL")


class UserProfile(BaseModel):
    """用户资料响应模型。"""

    id: UUID = Field(..., description="用户ID")
    wechat_openid: str = Field(..., description="微信 openid")
    nickname: Optional[str] = Field(None, description="用户昵称")
    avatar_url: Optional[str] = Field(None, description="头像 URL")
    phone_number: Optional[str] = Field(None, description="手机号")
    role: UserRole = Field(..., description="用户角色")
    is_active: bool = Field(..., description="是否激活")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")

    class Config:
        """Pydantic 配置。"""
        from_attributes = True  # 允许从 ORM 模型转换


class TokenResponse(BaseModel):
    """Token 响应模型。"""

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(..., description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    session_id: str = Field(..., description="会话ID")


class WechatLoginResponse(BaseModel):
    """微信登录响应模型。"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: UserProfile = Field(..., description="用户资料")
    token: TokenResponse = Field(..., description="认证令牌")
