"""
日志记录 API 路由。

处理饮食、活动、体重等日志记录的 CRUD 操作。
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from models.log import MealLog, ActivityLog, WeightLog
from models.pet import Pet
from models.user import User
from schemas.logs import (
    MealLogCreate,
    MealLogResponse,
    ActivityLogCreate,
    ActivityLogResponse,
    WeightLogCreate,
    WeightLogResponse,
    LogListResponse,
)
from services.database import get_db
from services.redis import get_redis, RedisService
from core.dependencies import get_current_user

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/logs", tags=["日志记录"])


# ==================== 饮食记录 ====================

@router.post(
    "/meals",
    response_model=MealLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="记录饮食",
    description="记录宠物饮食，包含重复喂食检测。"
)
async def create_meal_log(
    meal_data: MealLogCreate,
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> MealLogResponse:
    """创建饮食记录接口。

    Args:
        meal_data: 饮食记录数据
        db: 数据库会话
        redis_service: Redis 服务
        current_user: 当前登录用户

    Returns:
        MealLogResponse: 创建的饮食记录

    Raises:
        HTTPException: 宠物不存在、重复喂食或记录失败
    """
    try:
        # 检查宠物是否存在且属于当前用户
        stmt = select(Pet).where(
            and_(
                Pet.id == meal_data.pet_id,
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

        # 检查重复喂食
        timestamp = int(meal_data.meal_time.timestamp())
        is_duplicate = await redis_service.check_duplicate_feeding(
            str(meal_data.pet_id), timestamp
        )

        if is_duplicate:
            logger.warning(f"重复喂食检测: pet_id={meal_data.pet_id}, time={meal_data.meal_time}")

        # 创建饮食记录
        meal_log = MealLog(
            **meal_data.model_dump(),
            user_id=current_user.id,
            is_duplicate=is_duplicate,
        )

        db.add(meal_log)
        await db.commit()
        await db.refresh(meal_log)

        logger.info(f"记录饮食: pet_id={meal_data.pet_id}, food={meal_data.food_name}")

        return MealLogResponse.model_validate(meal_log)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"记录饮食失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"记录饮食失败: {str(e)}"
        )


@router.get(
    "/meals",
    response_model=LogListResponse,
    summary="获取饮食记录列表",
    description="获取指定宠物的饮食记录列表。"
)
async def list_meal_logs(
    pet_id: UUID = Query(..., description="宠物ID"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LogListResponse:
    """获取饮食记录列表接口。

    Args:
        pet_id: 宠物ID
        start_date: 开始日期
        end_date: 结束日期
        page: 页码
        page_size: 每页数量
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        LogListResponse: 饮食记录列表
    """
    try:
        # 检查宠物权限
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
                detail="宠物不存在或无权访问"
            )

        # 构建查询条件
        conditions = [MealLog.pet_id == pet_id]
        if start_date:
            conditions.append(MealLog.meal_time >= start_date)
        if end_date:
            conditions.append(MealLog.meal_time <= end_date)

        # 计算总数
        count_stmt = select(MealLog).where(*conditions)
        count_result = await db.execute(count_stmt)
        total = len(count_result.scalars().all())

        # 分页查询
        offset = (page - 1) * page_size
        stmt = (
            select(MealLog)
            .where(*conditions)
            .order_by(desc(MealLog.meal_time))
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        logs = result.scalars().all()

        return LogListResponse(
            total=total,
            items=[MealLogResponse.model_validate(log) for log in logs]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取饮食记录列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取饮食记录列表失败"
        )


# ==================== 活动记录 ====================

@router.post(
    "/activities",
    response_model=ActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="记录活动",
    description="记录宠物活动。"
)
async def create_activity_log(
    activity_data: ActivityLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActivityLogResponse:
    """创建活动记录接口。

    Args:
        activity_data: 活动记录数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        ActivityLogResponse: 创建的活动记录

    Raises:
        HTTPException: 宠物不存在或记录失败
    """
    try:
        # 检查宠物权限
        stmt = select(Pet).where(
            and_(
                Pet.id == activity_data.pet_id,
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

        # 创建活动记录
        activity_log = ActivityLog(
            **activity_data.model_dump(),
            user_id=current_user.id,
        )

        db.add(activity_log)
        await db.commit()
        await db.refresh(activity_log)

        logger.info(f"记录活动: pet_id={activity_data.pet_id}, type={activity_data.activity_type}")

        return ActivityLogResponse.model_validate(activity_log)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"记录活动失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"记录活动失败: {str(e)}"
        )


# ==================== 体重记录 ====================

@router.post(
    "/weights",
    response_model=WeightLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="记录体重",
    description="记录宠物体重。"
)
async def create_weight_log(
    weight_data: WeightLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeightLogResponse:
    """创建体重记录接口。

    Args:
        weight_data: 体重记录数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        WeightLogResponse: 创建的体重记录

    Raises:
        HTTPException: 宠物不存在或记录失败
    """
    try:
        # 检查宠物权限
        stmt = select(Pet).where(
            and_(
                Pet.id == weight_data.pet_id,
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

        # 创建体重记录
        weight_log = WeightLog(
            **weight_data.model_dump(),
            user_id=current_user.id,
        )

        db.add(weight_log)
        await db.commit()
        await db.refresh(weight_log)

        # 更新宠物的当前体重
        pet.current_weight = weight_data.weight
        await db.commit()

        logger.info(f"记录体重: pet_id={weight_data.pet_id}, weight={weight_data.weight}")

        return WeightLogResponse.model_validate(weight_log)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"记录体重失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"记录体重失败: {str(e)}"
        )


@router.get(
    "/weights",
    response_model=LogListResponse,
    summary="获取体重记录列表",
    description="获取指定宠物的体重记录历史。"
)
async def list_weight_logs(
    pet_id: UUID = Query(..., description="宠物ID"),
    limit: int = Query(30, ge=1, le=100, description="返回记录数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LogListResponse:
    """获取体重记录列表接口。

    Args:
        pet_id: 宠物ID
        limit: 返回记录数量
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        LogListResponse: 体重记录列表
    """
    try:
        # 检查宠物权限
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
                detail="宠物不存在或无权访问"
            )

        # 查询体重记录
        stmt = (
            select(WeightLog)
            .where(WeightLog.pet_id == pet_id)
            .order_by(desc(WeightLog.measurement_time))
            .limit(limit)
        )
        result = await db.execute(stmt)
        logs = result.scalars().all()

        return LogListResponse(
            total=len(logs),
            items=[WeightLogResponse.model_validate(log) for log in logs]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取体重记录列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取体重记录列表失败"
        )