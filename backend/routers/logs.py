"""
日志记录 API 路由。

处理饮食、活动、体重等日志记录的 CRUD 操作。

Round 2 改造要点：
- 新增 list_activity_logs 端点（Cache-Aside）
- 3 个 DELETE 端点（meals/weights/activities），删后失效对应缓存
- COUNT 查询使用 func.count() 高效实现（避免加载全表到内存）
- 宠物权限校验支持 30s 缓存（check_pet_permission_cached）
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

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


# ==================== 辅助函数 ====================

async def check_pet_permission_cached(
    pet_id: UUID,
    user: User,
    db: AsyncSession,
    redis_service: RedisService,
    require_active: bool = True,
) -> Pet:
    """校验用户对宠物的操作权限（Round 2 新增，带 30s Redis 缓存）。

    正向命中：只标记"user_id 对 pet_id 有权访问"，不缓存 Pet 对象本身
    （避免缓存过期数据）。命中时仍会查一次 DB 拿最新 Pet 记录，但省去
    了 `WHERE owner_id=?` 谓词，且大部分情况下宠物数据由 SQLAlchemy
    identity map 快速返回。

    仅缓存"有权访问"的正向结果，避免权限变更后延迟生效。

    Args:
        pet_id: 宠物ID
        user: 当前登录用户
        db: 数据库会话
        redis_service: Redis 服务
        require_active: 是否要求 pet.is_active=True（写操作场景需要，
                        读操作允许查询已归档宠物的历史记录）

    Returns:
        Pet: 校验通过的宠物对象

    Raises:
        HTTPException(404): 宠物不存在或无权访问
    """
    # 先查 Redis 缓存
    try:
        cached = await redis_service.get_pet_permission_cached(str(pet_id), str(user.id))
        if cached is True:
            # 缓存命中：仍需查 DB 拿最新宠物对象，但可以跳过 owner 谓词
            stmt = select(Pet).where(Pet.id == pet_id)
            if require_active:
                stmt = stmt.where(Pet.is_active == True)  # noqa: E712
            result = await db.execute(stmt)
            pet = result.scalar_one_or_none()
            if pet is not None:
                return pet
            # 缓存与 DB 不一致（宠物被删）—— 落回全量校验
    except Exception:
        logger.warning("Redis 权限缓存读取失败，降级查 DB", exc_info=True)

    # 缓存未命中，走完整 owner 校验
    conditions = [Pet.id == pet_id, Pet.owner_id == user.id]
    if require_active:
        conditions.append(Pet.is_active == True)  # noqa: E712
    stmt = select(Pet).where(and_(*conditions))
    result = await db.execute(stmt)
    pet = result.scalar_one_or_none()

    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="宠物不存在或无权访问",
        )

    # 回填缓存（不阻塞业务）
    try:
        await redis_service.set_pet_permission_cached(str(pet_id), str(user.id))
    except Exception:
        logger.warning("Redis 权限缓存回填失败", exc_info=True)

    return pet


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
    """创建饮食记录接口。"""
    try:
        pet = await check_pet_permission_cached(
            meal_data.pet_id, current_user, db, redis_service, require_active=True
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

        # 失效该宠物的饮食记录缓存，保证数据一致性
        try:
            await redis_service.invalidate_log_cache(
                str(meal_data.pet_id), prefix=RedisService.CACHE_PREFIX_MEAL_LOGS
            )
        except Exception:
            logger.warning("饮食记录缓存失效失败", exc_info=True)

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
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> LogListResponse:
    """获取饮食记录列表接口（带 Redis 缓存）。

    Cache-Aside 模式：先查缓存，命中则直接返回；未命中则查 DB 并回填缓存。
    空结果使用短 TTL 哨兵值防止缓存穿透。
    """
    try:
        await check_pet_permission_cached(
            pet_id, current_user, db, redis_service, require_active=False
        )

        # --- 缓存查询 ---
        cache_kwargs = dict(
            page=page, page_size=page_size,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
        )
        try:
            cached = await redis_service.get_log_cache(
                RedisService.CACHE_PREFIX_MEAL_LOGS, str(pet_id), **cache_kwargs,
            )
            if cached is not None:
                if cached == RedisService.CACHE_NULL_SENTINEL:
                    logger.debug(f"缓存命中(空结果): meal_logs pet_id={pet_id}")
                    return LogListResponse(total=0, items=[])
                logger.debug(f"缓存命中: meal_logs pet_id={pet_id}")
                return LogListResponse(**cached)
        except Exception:
            logger.warning("Redis 缓存读取失败，降级查 DB", exc_info=True)

        # --- DB 查询（缓存未命中） ---
        conditions = [MealLog.pet_id == pet_id]
        if start_date:
            conditions.append(MealLog.meal_time >= start_date)
        if end_date:
            conditions.append(MealLog.meal_time <= end_date)

        # Round 2：COUNT 用 func.count()，避免 len(scalars().all()) 加载全表
        count_stmt = select(func.count()).select_from(MealLog).where(*conditions)
        total = (await db.execute(count_stmt)).scalar_one()

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

        response = LogListResponse(
            total=total,
            items=[MealLogResponse.model_validate(log) for log in logs]
        )

        # --- 回填缓存 ---
        try:
            cache_data = {
                "total": response.total,
                "items": [item.model_dump(mode="json") for item in response.items],
            }
            await redis_service.set_log_cache(
                RedisService.CACHE_PREFIX_MEAL_LOGS, str(pet_id), cache_data, **cache_kwargs,
            )
        except Exception:
            logger.warning("Redis 缓存回填失败", exc_info=True)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取饮食记录列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取饮食记录列表失败"
        )


@router.delete(
    "/meals/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除饮食记录",
    description="删除指定饮食记录，同步失效缓存。"
)
async def delete_meal_log(
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除饮食记录（Round 2 新增）。"""
    try:
        stmt = select(MealLog).where(MealLog.id == log_id)
        result = await db.execute(stmt)
        meal_log = result.scalar_one_or_none()
        if meal_log is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="饮食记录不存在",
            )

        # 校验权限（只能删除自己宠物的记录）
        await check_pet_permission_cached(
            meal_log.pet_id, current_user, db, redis_service, require_active=False
        )

        pet_id = meal_log.pet_id
        await db.delete(meal_log)
        await db.commit()

        try:
            await redis_service.invalidate_log_cache(
                str(pet_id), prefix=RedisService.CACHE_PREFIX_MEAL_LOGS
            )
        except Exception:
            logger.warning("饮食记录缓存失效失败", exc_info=True)

        logger.info(f"删除饮食记录: id={log_id} pet_id={pet_id}")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"删除饮食记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除饮食记录失败",
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
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> ActivityLogResponse:
    """创建活动记录（Round 2：接入缓存失效）。"""
    try:
        await check_pet_permission_cached(
            activity_data.pet_id, current_user, db, redis_service, require_active=True
        )

        activity_log = ActivityLog(
            **activity_data.model_dump(),
            user_id=current_user.id,
        )

        db.add(activity_log)
        await db.commit()
        await db.refresh(activity_log)

        # Round 2：失效该宠物的活动记录缓存
        try:
            await redis_service.invalidate_log_cache(
                str(activity_data.pet_id), prefix=RedisService.CACHE_PREFIX_ACTIVITY_LOGS
            )
        except Exception:
            logger.warning("活动记录缓存失效失败", exc_info=True)

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


@router.get(
    "/activities",
    response_model=LogListResponse,
    summary="获取活动记录列表",
    description="获取指定宠物的活动记录列表（Round 2 新增）。"
)
async def list_activity_logs(
    pet_id: UUID = Query(..., description="宠物ID"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> LogListResponse:
    """获取活动记录列表接口（Round 2 新增，带 Cache-Aside）。"""
    try:
        await check_pet_permission_cached(
            pet_id, current_user, db, redis_service, require_active=False
        )

        # --- 缓存查询 ---
        cache_kwargs = dict(
            page=page, page_size=page_size,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
        )
        try:
            cached = await redis_service.get_log_cache(
                RedisService.CACHE_PREFIX_ACTIVITY_LOGS, str(pet_id), **cache_kwargs,
            )
            if cached is not None:
                if cached == RedisService.CACHE_NULL_SENTINEL:
                    logger.debug(f"缓存命中(空结果): activity_logs pet_id={pet_id}")
                    return LogListResponse(total=0, items=[])
                logger.debug(f"缓存命中: activity_logs pet_id={pet_id}")
                return LogListResponse(**cached)
        except Exception:
            logger.warning("Redis 缓存读取失败，降级查 DB", exc_info=True)

        # --- DB 查询（缓存未命中） ---
        conditions = [ActivityLog.pet_id == pet_id]
        if start_date:
            conditions.append(ActivityLog.activity_time >= start_date)
        if end_date:
            conditions.append(ActivityLog.activity_time <= end_date)

        count_stmt = select(func.count()).select_from(ActivityLog).where(*conditions)
        total = (await db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(ActivityLog)
            .where(*conditions)
            .order_by(desc(ActivityLog.activity_time))
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        logs = result.scalars().all()

        response = LogListResponse(
            total=total,
            items=[ActivityLogResponse.model_validate(log) for log in logs]
        )

        # --- 回填缓存 ---
        try:
            cache_data = {
                "total": response.total,
                "items": [item.model_dump(mode="json") for item in response.items],
            }
            await redis_service.set_log_cache(
                RedisService.CACHE_PREFIX_ACTIVITY_LOGS, str(pet_id), cache_data, **cache_kwargs,
            )
        except Exception:
            logger.warning("Redis 缓存回填失败", exc_info=True)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取活动记录列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取活动记录列表失败"
        )


@router.delete(
    "/activities/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除活动记录",
    description="删除指定活动记录，同步失效缓存（Round 2 新增）。"
)
async def delete_activity_log(
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除活动记录（Round 2 新增）。"""
    try:
        stmt = select(ActivityLog).where(ActivityLog.id == log_id)
        result = await db.execute(stmt)
        activity_log = result.scalar_one_or_none()
        if activity_log is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="活动记录不存在",
            )

        await check_pet_permission_cached(
            activity_log.pet_id, current_user, db, redis_service, require_active=False
        )

        pet_id = activity_log.pet_id
        await db.delete(activity_log)
        await db.commit()

        try:
            await redis_service.invalidate_log_cache(
                str(pet_id), prefix=RedisService.CACHE_PREFIX_ACTIVITY_LOGS
            )
        except Exception:
            logger.warning("活动记录缓存失效失败", exc_info=True)

        logger.info(f"删除活动记录: id={log_id} pet_id={pet_id}")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"删除活动记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除活动记录失败",
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
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> WeightLogResponse:
    """创建体重记录接口。"""
    try:
        pet = await check_pet_permission_cached(
            weight_data.pet_id, current_user, db, redis_service, require_active=True
        )

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

        # 失效该宠物的体重记录缓存
        try:
            await redis_service.invalidate_log_cache(
                str(weight_data.pet_id), prefix=RedisService.CACHE_PREFIX_WEIGHT_LOGS
            )
        except Exception:
            logger.warning("体重记录缓存失效失败", exc_info=True)

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
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> LogListResponse:
    """获取体重记录列表接口（带 Redis 缓存）。"""
    try:
        await check_pet_permission_cached(
            pet_id, current_user, db, redis_service, require_active=False
        )

        cache_kwargs = dict(limit=limit)
        try:
            cached = await redis_service.get_log_cache(
                RedisService.CACHE_PREFIX_WEIGHT_LOGS, str(pet_id), **cache_kwargs,
            )
            if cached is not None:
                if cached == RedisService.CACHE_NULL_SENTINEL:
                    logger.debug(f"缓存命中(空结果): weight_logs pet_id={pet_id}")
                    return LogListResponse(total=0, items=[])
                logger.debug(f"缓存命中: weight_logs pet_id={pet_id}")
                return LogListResponse(**cached)
        except Exception:
            logger.warning("Redis 缓存读取失败，降级查 DB", exc_info=True)

        # Round 2：COUNT 与分页解耦，避免 len(all()) 全表加载
        count_stmt = select(func.count()).select_from(WeightLog).where(WeightLog.pet_id == pet_id)
        total_all = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(WeightLog)
            .where(WeightLog.pet_id == pet_id)
            .order_by(desc(WeightLog.measurement_time))
            .limit(limit)
        )
        result = await db.execute(stmt)
        logs = result.scalars().all()

        response = LogListResponse(
            total=min(total_all, limit) if total_all > 0 else 0,
            items=[WeightLogResponse.model_validate(log) for log in logs]
        )

        try:
            cache_data = {
                "total": response.total,
                "items": [item.model_dump(mode="json") for item in response.items],
            }
            await redis_service.set_log_cache(
                RedisService.CACHE_PREFIX_WEIGHT_LOGS, str(pet_id), cache_data, **cache_kwargs,
            )
        except Exception:
            logger.warning("Redis 缓存回填失败", exc_info=True)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取体重记录列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取体重记录列表失败"
        )


@router.delete(
    "/weights/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除体重记录",
    description="删除指定体重记录，同步失效缓存（Round 2 新增）。"
)
async def delete_weight_log(
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除体重记录（Round 2 新增）。"""
    try:
        stmt = select(WeightLog).where(WeightLog.id == log_id)
        result = await db.execute(stmt)
        weight_log = result.scalar_one_or_none()
        if weight_log is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="体重记录不存在",
            )

        await check_pet_permission_cached(
            weight_log.pet_id, current_user, db, redis_service, require_active=False
        )

        pet_id = weight_log.pet_id
        await db.delete(weight_log)
        await db.commit()

        try:
            await redis_service.invalidate_log_cache(
                str(pet_id), prefix=RedisService.CACHE_PREFIX_WEIGHT_LOGS
            )
        except Exception:
            logger.warning("体重记录缓存失效失败", exc_info=True)

        logger.info(f"删除体重记录: id={log_id} pet_id={pet_id}")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"删除体重记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除体重记录失败",
        )
