"""
家庭组管理 API 路由。

处理家庭组的创建、加入、成员管理等。
"""

import logging
import random
import string
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_user
from models.user import Family, FamilyMember, FamilyRole, User
from schemas.families import (
    FamilyCreate,
    FamilyInviteResponse,
    FamilyJoinRequest,
    FamilyMemberResponse,
    FamilyResponse,
)
from services.database import get_db

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/families", tags=["家庭组管理"])


@router.post(
    "",
    response_model=FamilyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建家庭组",
    description="创建新的宠物管理家庭组。"
)
async def create_family(
    family_data: FamilyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FamilyResponse:
    """创建家庭组接口。

    Args:
        family_data: 家庭组数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        FamilyResponse: 创建的家庭组信息

    Raises:
        HTTPException: 创建失败
    """
    try:
        # 生成唯一邀请码（6位字母数字）
        invite_code = _generate_invite_code(db)

        # 创建家庭组
        family = Family(
            name=family_data.name,
            invite_code=invite_code,
        )

        db.add(family)
        await db.flush()  # 获取生成的 ID

        # 添加创建者为家庭成员（角色为OWNER）
        family_member = FamilyMember(
            family_id=family.id,
            user_id=current_user.id,
            role=FamilyRole.OWNER,
        )
        db.add(family_member)

        await db.commit()
        await db.refresh(family)

        logger.info(f"创建家庭组: family_id={family.id}, owner_id={current_user.id}")

        return FamilyResponse.model_validate(family)

    except Exception as e:
        await db.rollback()
        logger.exception(f"创建家庭组失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建家庭组失败: {str(e)}"
        )


@router.get(
    "",
    response_model=List[FamilyResponse],
    summary="获取我的家庭组列表",
    description="获取当前用户加入的所有家庭组列表。"
)
async def list_my_families(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FamilyResponse]:
    """获取我的家庭组列表接口。

    Args:
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        List[FamilyResponse]: 家庭组列表
    """
    try:
        stmt = (
            select(Family)
            .join(FamilyMember)
            .where(FamilyMember.user_id == current_user.id)
            .order_by(Family.created_at.desc())
        )
        result = await db.execute(stmt)
        families = result.scalars().all()

        return [FamilyResponse.model_validate(family) for family in families]

    except Exception as e:
        logger.exception(f"获取家庭组列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取家庭组列表失败"
        )


@router.get(
    "/{family_id}",
    response_model=FamilyResponse,
    summary="获取家庭组详情",
    description="获取家庭组详细信息。"
)
async def get_family(
    family_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FamilyResponse:
    """获取家庭组详情接口。

    Args:
        family_id: 家庭组ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        FamilyResponse: 家庭组信息

    Raises:
        HTTPException: 家庭组不存在或无权访问
    """
    try:
        # 检查用户是否是该家庭组成员
        stmt = select(FamilyMember).where(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == current_user.id,
            )
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该家庭组"
            )

        # 获取家庭组信息
        family_stmt = select(Family).where(Family.id == family_id)
        result = await db.execute(family_stmt)
        family = result.scalar_one_or_none()

        if family is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="家庭组不存在"
            )

        return FamilyResponse.model_validate(family)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取家庭组详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取家庭组详情失败"
        )


@router.get(
    "/{family_id}/members",
    response_model=List[FamilyMemberResponse],
    summary="获取家庭成员列表",
    description="获取家庭组的成员列表。"
)
async def list_family_members(
    family_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FamilyMemberResponse]:
    """获取家庭成员列表接口。

    Args:
        family_id: 家庭组ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        List[FamilyMemberResponse]: 成员列表

    Raises:
        HTTPException: 家庭组不存在或无权访问
    """
    try:
        # 检查用户是否是该家庭组成员
        stmt = select(FamilyMember).where(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == current_user.id,
            )
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该家庭组"
            )

        # 获取成员列表
        member_stmt = (
            select(FamilyMember, User)
            .join(User, FamilyMember.user_id == User.id)
            .where(FamilyMember.family_id == family_id)
            .order_by(
                FamilyMember.role.desc(),  # OWNER 在前
                FamilyMember.joined_at.asc()
            )
        )
        result = await db.execute(member_stmt)
        rows = result.all()

        members = []
        for member, user in rows:
            members.append(FamilyMemberResponse(
                user_id=member.user_id,
                family_id=member.family_id,
                role=member.role,
                joined_at=member.joined_at,
                nickname=user.nickname,
                avatar_url=user.avatar_url,
            ))

        return members

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取家庭成员列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取家庭成员列表失败"
        )


@router.post(
    "/join",
    response_model=FamilyResponse,
    summary="加入家庭组",
    description="通过邀请码加入家庭组。"
)
async def join_family(
    request: FamilyJoinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FamilyResponse:
    """加入家庭组接口。

    Args:
        request: 加入请求
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        FamilyResponse: 加入的家庭组信息

    Raises:
        HTTPException: 邀请码无效或已加入
    """
    try:
        # 查找对应邀请码的家庭组
        stmt = select(Family).where(Family.invite_code == request.invite_code)
        result = await db.execute(stmt)
        family = result.scalar_one_or_none()

        if family is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="邀请码无效"
            )

        # 检查是否已经是成员
        member_stmt = select(FamilyMember).where(
            and_(
                FamilyMember.family_id == family.id,
                FamilyMember.user_id == current_user.id,
            )
        )
        result = await db.execute(member_stmt)
        existing_member = result.scalar_one_or_none()

        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="您已经是该家庭组的成员"
            )

        # 添加为家庭成员（角色为MEMBER）
        family_member = FamilyMember(
            family_id=family.id,
            user_id=current_user.id,
            role=FamilyRole.MEMBER,
        )
        db.add(family_member)

        await db.commit()
        await db.refresh(family)

        logger.info(f"加入家庭组: user_id={current_user.id}, family_id={family.id}")

        return FamilyResponse.model_validate(family)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"加入家庭组失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"加入家庭组失败: {str(e)}"
        )


@router.get(
    "/{family_id}/invite",
    response_model=FamilyInviteResponse,
    summary="获取邀请信息",
    description="获取家庭组的邀请码和二维码。"
)
async def get_family_invite(
    family_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FamilyInviteResponse:
    """获取家庭组邀请信息接口。

    Args:
        family_id: 家庭组ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        FamilyInviteResponse: 邀请信息

    Raises:
        HTTPException: 家庭组不存在或无权访问
    """
    try:
        # 检查用户权限（只有OWNER可以获取邀请信息）
        stmt = select(FamilyMember).where(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == current_user.id,
                FamilyMember.role == FamilyRole.OWNER,
            )
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有家庭创建者可以获取邀请信息"
            )

        # 获取家庭组信息
        family_stmt = select(Family).where(Family.id == family_id)
        family_result = await db.execute(family_stmt)
        family = family_result.scalar_one_or_none()

        if family is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="家庭组不存在"
            )

        # 生成二维码URL（模拟）
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={family.invite_code}"

        return FamilyInviteResponse(
            family_id=family.id,
            invite_code=family.invite_code,
            qr_code_url=qr_code_url,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取邀请信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取邀请信息失败"
        )


async def _generate_invite_code(db: AsyncSession) -> str:
    """生成唯一的邀请码。

    Args:
        db: 数据库会话

    Returns:
        str: 6位唯一邀请码
    """
    for _ in range(10):  # 最多尝试10次
        # 生成6位大写字母和数字组合
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # 检查是否已存在
        stmt = select(Family).where(Family.invite_code == code)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            return code

    raise ValueError("无法生成唯一邀请码")
