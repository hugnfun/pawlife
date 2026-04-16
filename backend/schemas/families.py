"""
家庭组相关的 Pydantic 模型。
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from models.user import FamilyRole


class FamilyCreate(BaseModel):
    """创建家庭组请求模型。"""

    name: str = Field(..., min_length=1, max_length=100, description="家庭组名称")


class FamilyResponse(BaseModel):
    """家庭组响应模型。"""

    id: UUID = Field(..., description="家庭组ID")
    name: str = Field(..., description="家庭组名称")
    invite_code: str = Field(..., description="邀请码")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        """Pydantic 配置。"""
        from_attributes = True


class FamilyMemberResponse(BaseModel):
    """家庭成员响应模型。"""

    user_id: UUID = Field(..., description="用户ID")
    family_id: UUID = Field(..., description="家庭组ID")
    role: FamilyRole = Field(..., description="家庭角色")
    joined_at: datetime = Field(..., description="加入时间")
    nickname: Optional[str] = Field(None, description="用户昵称")
    avatar_url: Optional[str] = Field(None, description="用户头像")

    class Config:
        """Pydantic 配置。"""
        from_attributes = True


class FamilyJoinRequest(BaseModel):
    """加入家庭组请求模型。"""

    invite_code: str = Field(..., min_length=6, max_length=6, description="邀请码")


class FamilyInviteResponse(BaseModel):
    """家庭邀请响应模型。"""

    family_id: UUID = Field(..., description="家庭组ID")
    invite_code: str = Field(..., description="邀请码")
    qr_code_url: Optional[str] = Field(None, description="邀请二维码URL")