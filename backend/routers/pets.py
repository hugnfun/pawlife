"""
宠物管理 API 路由。

处理宠物档案的 CRUD 操作、活跃宠物切换等。
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.pet import Pet
from models.user import User, UserRole
from schemas.pets import PetCreate, PetUpdate, PetResponse, PetListResponse
from services.database import get_db
from services.redis import get_redis, RedisService
from core.dependencies import get_current_user

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/pets", tags=["宠物管理"])


@router.post(
    "/",
    response_model=PetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建宠物档案",
    description="创建新的宠物档案。"
)
async def create_pet(
    pet_data: PetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PetResponse:
    """创建宠物档案接口。

    Args:
        pet_data: 宠物数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        PetResponse: 创建的宠物信息

    Raises:
        HTTPException: 创建失败或权限不足
    """
    try:
        # 创建宠物实例
        pet = Pet(
            **pet_data.model_dump(exclude={"family_id"}),
            owner_id=current_user.id,
            family_id=pet_data.family_id,
        )

        db.add(pet)
        await db.commit()
        await db.refresh(pet)

        logger.info(f"创建宠物: pet_id={pet.id}, owner_id={current_user.id}")

        return PetResponse.model_validate(pet)

    except Exception as e:
        await db.rollback()
        logger.exception(f"创建宠物失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建宠物失败: {str(e)}"
        )


@router.get(
    "/",
    response_model=PetListResponse,
    summary="获取宠物列表",
    description="获取当前用户的所有宠物列表。"
)
async def list_pets(
    include_inactive: bool = Query(False, description="是否包含非活跃宠物"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PetListResponse:
    """获取宠物列表接口。

    Args:
        include_inactive: 是否包含非活跃宠物
        page: 页码
        page_size: 每页数量
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        PetListResponse: 宠物列表
    """
    try:
        # 构建查询条件
        conditions = [Pet.owner_id == current_user.id]
        if not include_inactive:
            conditions.append(Pet.is_active == True)

        # 计算总数
        count_stmt = select(Pet).where(*conditions)
        count_result = await db.execute(count_stmt)
        total = len(count_result.scalars().all())

        # 分页查询
        offset = (page - 1) * page_size
        stmt = (
            select(Pet)
            .where(*conditions)
            .order_by(Pet.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        pets = result.scalars().all()

        return PetListResponse(
            total=total,
            items=[PetResponse.model_validate(pet) for pet in pets]
        )

    except Exception as e:
        logger.exception(f"获取宠物列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取宠物列表失败"
        )


@router.get(
    "/{pet_id}",
    response_model=PetResponse,
    summary="获取宠物详情",
    description="根据ID获取宠物详细档案信息。"
)
async def get_pet(
    pet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PetResponse:
    """获取宠物详情接口。

    Args:
        pet_id: 宠物ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        PetResponse: 宠物信息

    Raises:
        HTTPException: 宠物不存在或权限不足
    """
    try:
        stmt = select(Pet).where(
            and_(
                Pet.id == pet_id,
                Pet.owner_id == current_user.id,
                Pet.is_active == True,
            )
        )
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()

        if pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="宠物不存在或无权访问"
            )

        return PetResponse.model_validate(pet)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取宠物详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取宠物详情失败"
        )


@router.put(
    "/{pet_id}",
    response_model=PetResponse,
    summary="更新宠物档案",
    description="更新宠物档案信息。"
)
async def update_pet(
    pet_id: UUID,
    pet_data: PetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PetResponse:
    """更新宠物档案接口。

    Args:
        pet_id: 宠物ID
        pet_data: 更新数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        PetResponse: 更新后的宠物信息

    Raises:
        HTTPException: 宠物不存在或更新失败
    """
    try:
        # 检查宠物是否存在且属于当前用户
        stmt = select(Pet).where(
            and_(
                Pet.id == pet_id,
                Pet.owner_id == current_user.id,
            )
        )
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()

        if pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="宠物不存在或无权修改"
            )

        # 更新字段
        update_data = pet_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(pet, field, value)

        await db.commit()
        await db.refresh(pet)

        logger.info(f"更新宠物: pet_id={pet.id}")

        return PetResponse.model_validate(pet)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"更新宠物失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新宠物失败: {str(e)}"
        )


@router.delete(
    "/{pet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除宠物档案",
    description="软删除宠物档案（标记为非活跃状态）。"
)
async def delete_pet(
    pet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除宠物档案接口。

    Args:
        pet_id: 宠物ID
        db: 数据库会话
        current_user: 当前登录用户

    Raises:
        HTTPException: 宠物不存在或删除失败
    """
    try:
        # 检查宠物是否存在且属于当前用户
        stmt = select(Pet).where(
            and_(
                Pet.id == pet_id,
                Pet.owner_id == current_user.id,
                Pet.is_active == True,
            )
        )
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()

        if pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="宠物不存在或无权删除"
            )

        # 软删除：标记为非活跃
        pet.is_active = False
        await db.commit()

        logger.info(f"删除宠物: pet_id={pet.id}")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"删除宠物失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除宠物失败"
        )


@router.post(
    "/{pet_id}/set-active",
    summary="设置活跃宠物",
    description="将指定宠物设置为当前用户的活跃宠物。"
)
async def set_active_pet(
    pet_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> dict:
    """设置活跃宠物接口。

    Args:
        pet_id: 宠物ID
        db: 数据库会话
        redis_service: Redis 服务
        current_user: 当前登录用户

    Returns:
        dict: 设置结果

    Raises:
        HTTPException: 宠物不存在或权限不足
    """
    try:
        # 检查宠物是否存在且属于当前用户
        stmt = select(Pet).where(
            and_(
                Pet.id == pet_id,
                Pet.owner_id == current_user.id,
                Pet.is_active == True,
            )
        )
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()

        if pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="宠物不存在或无权操作"
            )

        # 在 Redis 中设置活跃宠物
        await redis_service.set_active_pet(str(current_user.id), str(pet_id))

        logger.info(f"设置活跃宠物: user_id={current_user.id}, pet_id={pet_id}")

        return {
            "success": True,
            "message": "设置活跃宠物成功",
            "data": {"pet_id": str(pet_id)}
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"设置活跃宠物失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="设置活跃宠物失败"
        )


# ========== 宠物详情子资源（/pet/{pet_id}/...）==========
# 前端 api/pet-profile.ts 使用单数 /pet/ 路径，这里单独创建路由实例匹配

pet_detail_router = APIRouter(prefix="/pet", tags=["宠物详情"])


@pet_detail_router.get(
    "/{pet_id}/profile",
    summary="获取宠物档案详情",
    description="获取宠物完整档案信息（前端 pet-profile 页面使用）。"
)
async def get_pet_profile_detail(
    pet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取宠物档案详情（兼容前端 /pet/{petId}/profile 路径）。"""
    try:
        stmt = select(Pet).where(
            and_(
                Pet.id == pet_id,
                Pet.owner_id == current_user.id,
                Pet.is_active == True,
            )
        )
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()

        if pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="宠物不存在或无权访问"
            )

        return PetResponse.model_validate(pet)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取宠物档案详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取宠物档案详情失败"
        )


@pet_detail_router.get(
    "/{pet_id}/vaccines",
    summary="获取疫苗记录",
    description="获取宠物的疫苗接种记录列表。"
)
async def get_vaccine_records(
    pet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取宠物疫苗记录。

    Args:
        pet_id: 宠物ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        疫苗记录列表
    """
    try:
        # 验证宠物权限
        stmt = select(Pet).where(
            and_(
                Pet.id == pet_id,
                Pet.owner_id == current_user.id,
                Pet.is_active == True,
            )
        )
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()

        if pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="宠物不存在或无权访问"
            )

        from models.pet import VaccineRecord

        stmt = select(VaccineRecord).where(
            VaccineRecord.pet_id == pet_id
        ).order_by(VaccineRecord.administered_date.desc())

        result = await db.execute(stmt)
        records = result.scalars().all()

        return [
            {
                "id": str(r.id),
                "pet_id": str(r.pet_id),
                "vaccine_name": r.vaccine_name,
                "vaccine_type": "",
                "vaccine_date": r.administered_date.isoformat() if r.administered_date else "",
                "next_dose_date": r.next_due_date.isoformat() if r.next_due_date else None,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取疫苗记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取疫苗记录失败"
        )


@pet_detail_router.get(
    "/{pet_id}/diet-recipe",
    summary="获取当前饮食方案",
    description="获取宠物当前激活的饮食方案。"
)
async def get_diet_recipe(
    pet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取宠物当前激活的饮食方案。

    Args:
        pet_id: 宠物ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        当前饮食方案，如果没有返回 null
    """
    try:
        # 验证宠物权限
        stmt = select(Pet).where(
            and_(
                Pet.id == pet_id,
                Pet.owner_id == current_user.id,
                Pet.is_active == True,
            )
        )
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()

        if pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="宠物不存在或无权访问"
            )

        from models.recipe import Recipe, RecipeIngredient

        stmt = select(Recipe).where(
            and_(
                Recipe.pet_id == pet_id,
                Recipe.is_active == True,
            )
        ).order_by(Recipe.created_at.desc()).limit(1)

        result = await db.execute(stmt)
        recipe = result.scalar_one_or_none()

        if recipe is None:
            return None

        # 获取食材列表
        ing_stmt = select(RecipeIngredient).where(
            RecipeIngredient.recipe_id == recipe.id
        )
        ing_result = await db.execute(ing_stmt)
        ingredients = ing_result.scalars().all()

        # 按餐次分组（简化处理，直接列出所有食材）
        meals = []
        for ing in ingredients:
            meals.append({
                "time": "",
                "food": ing.food_name,
                "amount": float(ing.amount) if ing.amount else 0,
                "unit": ing.unit,
            })

        return {
            "id": str(recipe.id),
            "pet_id": str(recipe.pet_id),
            "name": recipe.name,
            "description": recipe.description or "",
            "daily_calories": float(recipe.daily_calories_target) if recipe.daily_calories_target else 0,
            "protein_ratio": float(recipe.protein_target_percent) if recipe.protein_target_percent else 0,
            "fat_ratio": float(recipe.fat_target_percent) if recipe.fat_target_percent else 0,
            "carb_ratio": float(recipe.carb_target_percent) if recipe.carb_target_percent else 0,
            "meals": meals,
            "is_active": recipe.is_active,
            "created_at": recipe.created_at.isoformat() if recipe.created_at else "",
            "updated_at": recipe.updated_at.isoformat() if recipe.updated_at else "",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取饮食方案失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取饮食方案失败"
        )


