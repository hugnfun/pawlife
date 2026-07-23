"""
账户管理 API 路由。

处理家庭成员、推送设置等账户相关操作。
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_user
from models.user import Family, FamilyMember, User
from services.database import get_db
from services.redis import RedisService, get_redis

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/account", tags=["账户管理"])


# ========== Schemas ==========

class FamilyMemberOut(BaseModel):
    """家庭成员输出模型。"""
    user_id: str
    family_id: str
    role: str
    joined_at: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PushSettings(BaseModel):
    """推送设置模型。"""
    daily_summary: bool = False
    feeding_reminder: bool = True
    weight_reminder: bool = True
    vaccine_reminder: bool = True
    health_alert: bool = True


class PushSettingsUpdate(BaseModel):
    """推送设置更新模型。"""
    daily_summary: Optional[bool] = None
    feeding_reminder: Optional[bool] = None
    weight_reminder: Optional[bool] = None
    vaccine_reminder: Optional[bool] = None
    health_alert: Optional[bool] = None


# ========== 路由 ==========

@router.get(
    "/family/members",
    summary="获取我的家庭成员列表",
    description="获取当前用户所在家庭组的所有成员信息。"
)
async def get_family_members(
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户所在家庭组的成员列表。

    如果用户属于多个家庭组，返回第一个家庭的成员。
    前端可指定 family_id 参数选择特定家庭。
    """
    try:
        # 查找用户所属的家庭组
        stmt = select(FamilyMember).where(
            FamilyMember.user_id == current_user.id
        )
        result = await db.execute(stmt)
        memberships = result.scalars().all()

        if not memberships:
            # 用户不在任何家庭组，返回空列表
            return []

        # 使用第一个家庭组（后续可扩展为 family_id 参数选择）
        family_id = memberships[0].family_id

        # 获取该家庭组的所有成员
        member_stmt = (
            select(FamilyMember, User)
            .join(User, FamilyMember.user_id == User.id)
            .where(FamilyMember.family_id == family_id)
            .order_by(FamilyMember.role.desc(), FamilyMember.joined_at.asc())
        )
        result = await db.execute(member_stmt)
        rows = result.all()

        members = []
        for member, user in rows:
            members.append(FamilyMemberOut(
                user_id=str(member.user_id),
                family_id=str(member.family_id),
                role=member.role.value,
                joined_at=member.joined_at.isoformat() if member.joined_at else "",
                nickname=user.nickname,
                avatar_url=user.avatar_url,
            ).model_dump())

        logger.info(f"获取家庭成员列表: user_id={current_user.id}, family_id={family_id}, count={len(members)}")

        return members

    except Exception as e:
        logger.exception(f"获取家庭成员列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取家庭成员列表失败"
        )


@router.get(
    "/push-settings",
    summary="获取推送设置",
    description="获取当前用户的推送通知设置。"
)
async def get_push_settings(
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> PushSettings:
    """获取当前用户的推送设置。

    推送设置存储在 Redis 中，key 格式: push_settings:{user_id}
    """
    try:
        user_id_str = str(current_user.id)
        cached = await redis_service.get(f"push_settings:{user_id_str}")

        if cached:
            settings_data = json.loads(cached) if isinstance(cached, str) else cached
            return PushSettings(**settings_data)

        # 返回默认设置
        return PushSettings()

    except Exception as e:
        logger.exception(f"获取推送设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取推送设置失败"
        )


@router.post(
    "/push-settings",
    summary="更新推送设置",
    description="更新当前用户的推送通知设置。"
)
async def update_push_settings(
    settings_update: PushSettingsUpdate,
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户的推送设置。

    只更新传入的字段（部分更新），未传入的字段保持不变。
    """
    try:
        user_id_str = str(current_user.id)

        # 读取现有设置
        cached = await redis_service.get(f"push_settings:{user_id_str}")
        if cached:
            current_settings = json.loads(cached) if isinstance(cached, str) else cached
        else:
            current_settings = PushSettings().model_dump()

        # 合并更新（只更新非 None 字段）
        update_data = settings_update.model_dump(exclude_unset=True)
        current_settings.update(update_data)

        # 写回 Redis
        await redis_service.set(
            f"push_settings:{user_id_str}",
            json.dumps(current_settings, ensure_ascii=False),
        )

        logger.info(f"更新推送设置: user_id={current_user.id}, updated_fields={list(update_data.keys())}")

        return {"success": True}

    except Exception as e:
        logger.exception(f"更新推送设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新推送设置失败"
        )


@router.get(
    "/family/invite",
    summary="获取家庭邀请信息",
    description="获取当前用户家庭的邀请码。"
)
async def get_family_invite(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户所在家庭组的邀请码。

    如果用户不在任何家庭组，返回提示信息。
    """
    try:
        # 查找用户所属的家庭组
        stmt = select(FamilyMember).where(
            FamilyMember.user_id == current_user.id
        )
        result = await db.execute(stmt)
        memberships = result.scalars().all()

        if not memberships:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="你还没有加入任何家庭组"
            )

        # 使用第一个家庭组
        family_id = memberships[0].family_id

        family_stmt = select(Family).where(Family.id == family_id)
        family_result = await db.execute(family_stmt)
        family = family_result.scalar_one_or_none()

        if family is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="家庭组不存在"
            )

        # 生成二维码 URL
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={family.invite_code}"

        logger.info(f"获取家庭邀请信息: user_id={current_user.id}, family_id={family_id}")

        return {
            "invite_code": family.invite_code,
            "qr_code_url": qr_code_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取家庭邀请信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取家庭邀请信息失败"
        )
