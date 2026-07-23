"""
Agent 工具集合。

所有可供 AI Agent 调用的工具在这里定义注册。
遵循 LangChain 工具接口规范，具体实现延后到后续开发。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


async def _create_log_draft(
    log_type: str,
    pet_id: UUID,
    user_id: UUID,
    payload: Dict[str, Any],
    summary: str,
) -> Dict[str, Any]:
    """把 AI 提取的日志字段存为草稿，返回 draft_id 供用户确认。

    Args:
        log_type: "meal" / "weight" / "activity"
        pet_id: 宠物 UUID
        user_id: 用户 UUID
        payload: AI 提取的字段字典（会在 confirm 时用作默认值）
        summary: 面向用户的中文摘要（用于卡片展示，如"三花 今天 12:30 吃了 50g 鸡胸肉"）

    Returns:
        Agent 工具的标准返回结构，data 里含 draft_id 和 payload
    """
    import uuid
    from datetime import datetime, timezone

    from services.redis import redis_service

    draft_id = str(uuid.uuid4())
    draft_data = {
        "type": log_type,
        "pet_id": str(pet_id),
        "user_id": str(user_id),
        "payload": payload,
        "summary": summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis_service.save_log_draft(draft_id, draft_data)

    return {
        "success": True,
        "requires_confirmation": True,
        "error": None,
        "data": {
            "draft_id": draft_id,
            "log_type": log_type,
            "pet_id": str(pet_id),
            "payload": payload,
            "summary": summary,
        },
    }


async def _persist_meal(
    pet_id: UUID,
    user_id: UUID,
    payload: Dict[str, Any],
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    """真正把饮食记录写入数据库（供 confirm API 复用）。

    Args:
        session: 可选的外部 AsyncSession。API 端点传入时会走该会话
                （便于测试 mock 数据库）；否则自己创建。
    """
    import uuid
    from datetime import datetime
    from decimal import Decimal

    from models.log import MealLog
    from services.database import db

    food_name = payload["food_name"]
    amount = float(payload.get("amount", 0))
    unit = payload.get("unit", "g")
    meal_time_str = payload.get("meal_time")
    meal_time = (
        datetime.fromisoformat(meal_time_str) if meal_time_str else datetime.now()
    )
    notes = payload.get("notes")
    photo_url = payload.get("photo_url")

    async def _do(sess):
        meal_log = MealLog(
            id=uuid.uuid4(),
            pet_id=pet_id,
            user_id=user_id,
            food_name=food_name,
            amount=Decimal(str(amount)),
            unit=unit,
            meal_time=meal_time,
            notes=notes,
            photo_url=photo_url,
        )
        sess.add(meal_log)
        await sess.commit()
        logger.info(
            f"饮食记录创建成功: id={meal_log.id}, pet_id={pet_id}, food={food_name}, amount={amount}"
        )
        return {
            "meal_log_id": str(meal_log.id),
            "pet_id": str(meal_log.pet_id),
            "food_name": meal_log.food_name,
            "amount": float(meal_log.amount),
            "meal_time": meal_log.meal_time.isoformat(),
        }

    if session is not None:
        return await _do(session)
    async with db.get_session() as sess:
        return await _do(sess)


async def _persist_activity(
    pet_id: UUID,
    user_id: UUID,
    payload: Dict[str, Any],
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    """真正把运动记录写入数据库（供 confirm API 复用）。"""
    import uuid
    from datetime import datetime

    from models.log import ActivityLog
    from services.database import db

    activity_type = payload["activity_type"]
    duration_minutes = int(payload.get("duration_minutes", 0))
    activity_time_str = payload.get("activity_time")
    activity_time = (
        datetime.fromisoformat(activity_time_str)
        if activity_time_str
        else datetime.now()
    )
    notes = payload.get("notes")

    async def _do(sess):
        activity = ActivityLog(
            id=uuid.uuid4(),
            pet_id=pet_id,
            user_id=user_id,
            activity_type=activity_type,
            duration_minutes=duration_minutes,
            activity_time=activity_time,
            notes=notes,
        )
        sess.add(activity)
        await sess.commit()
        logger.info(
            f"活动记录创建成功: id={activity.id}, pet_id={pet_id}, type={activity_type}, duration={duration_minutes}min"
        )
        return {
            "activity_log_id": str(activity.id),
            "pet_id": str(pet_id),
            "activity_type": activity_type,
            "duration_minutes": duration_minutes,
            "activity_time": activity.activity_time.isoformat(),
        }

    if session is not None:
        return await _do(session)
    async with db.get_session() as sess:
        return await _do(sess)


async def _persist_weight(
    pet_id: UUID,
    user_id: UUID,
    payload: Dict[str, Any],
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    """真正把体重记录写入数据库并更新 Pet.current_weight（供 confirm API 复用）。"""
    import uuid
    from datetime import datetime
    from decimal import Decimal

    from sqlalchemy import select

    from models.log import WeightLog
    from models.pet import Pet
    from services.database import db

    weight_kg = float(payload["weight_kg"])

    async def _do(sess):
        weight_log = WeightLog(
            id=uuid.uuid4(),
            pet_id=pet_id,
            user_id=user_id,
            weight=Decimal(str(weight_kg)),
            measurement_time=datetime.now(),
        )
        sess.add(weight_log)

        stmt = select(Pet).where(Pet.id == pet_id)
        result = await sess.execute(stmt)
        pet = result.scalar_one_or_none()
        if pet:
            pet.current_weight = Decimal(str(weight_kg))

        await sess.commit()
        logger.info(
            f"体重记录创建成功: id={weight_log.id}, pet_id={pet_id}, weight={weight_kg}kg"
        )
        return {
            "weight_log_id": str(weight_log.id),
            "pet_id": str(pet_id),
            "weight_kg": weight_kg,
            "measurement_time": weight_log.measurement_time.isoformat(),
        }

    if session is not None:
        return await _do(session)
    async with db.get_session() as sess:
        return await _do(sess)


# ========== 宠物档案工具 ==========

class GetPetProfileInput(BaseModel):
    """获取宠物档案输入参数。"""
    pet_id: Optional[UUID] = Field(None, description="宠物ID，不提供则使用当前活跃宠物")


class GetPetProfileTool(BaseTool):
    """获取宠物档案信息工具。

    读取宠物的基本信息、健康数据、历史记录等。
    """
    name: str = "get_pet_profile"
    description: str = "获取宠物档案信息，包括基本信息、体重、品种等"
    args_schema: type[BaseModel] = GetPetProfileInput

    def _run(self, pet_id: Optional[UUID] = None) -> Dict[str, Any]:
        """同步执行不支持，委托到异步。"""
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(self, pet_id: Optional[UUID] = None) -> Dict[str, Any]:
        """异步执行：从数据库读取宠物档案信息。

        Args:
            pet_id: 宠物ID，如果不提供则查找用户当前活跃宠物

        Returns:
            操作结果，包含宠物档案数据
        """
        from sqlalchemy import select

        from models.pet import Pet
        from services.database import db

        if pet_id is None:
            return {
                "success": False,
                "error": "pet_id is required",
                "data": None,
            }

        try:
            async with db.get_session() as session:
                stmt = select(Pet).where(Pet.id == pet_id, Pet.is_active == True)
                result = await session.execute(stmt)
                pet = result.scalar_one_or_none()

                if pet is None:
                    return {
                        "success": False,
                        "error": f"Pet not found: {pet_id}",
                        "data": None,
                    }

                # 序列化宠物信息
                data = {
                    "pet_id": str(pet.id),
                    "name": pet.name,
                    "species": pet.species.value if pet.species else None,
                    "breed": pet.breed,
                    "gender": pet.gender.value if pet.gender else None,
                    "birth_date": pet.birth_date.isoformat() if pet.birth_date else None,
                    "neutered_status": pet.neutered_status.value if pet.neutered_status else None,
                    "current_weight": float(pet.current_weight) if pet.current_weight else None,
                    "ideal_weight": float(pet.ideal_weight) if pet.ideal_weight else None,
                    "body_condition_score": pet.body_condition_score.value if pet.body_condition_score else None,
                    "known_diseases": pet.known_diseases,
                    "main_food_brand": pet.main_food_brand,
                    "allergy_blacklist": pet.allergy_blacklist,
                    "created_at": pet.created_at.isoformat() if pet.created_at else None,
                    "updated_at": pet.updated_at.isoformat() if pet.updated_at else None,
                }

                return {
                    "success": True,
                    "error": None,
                    "data": data,
                }

        except Exception as e:
            logger.error(f"Get pet profile failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Get failed: {str(e)}",
                "data": None,
            }


class UpdatePetProfileInput(BaseModel):
    """更新宠物档案输入参数。"""
    pet_id: UUID = Field(..., description="宠物ID")
    updates: Dict[str, Any] = Field(..., description="要更新的字段和值")


class UpdatePetProfileTool(BaseTool):
    """更新宠物档案信息工具。

    更新宠物的基本信息、体重、品种等。
    对于新创建的宠物，可以一步步收集信息并更新。
    """
    name: str = "update_pet_profile"
    description: str = "更新宠物档案信息，比如体重、名字、品种等"
    args_schema: type[BaseModel] = UpdatePetProfileInput

    def _run(self, pet_id: UUID, updates: Dict[str, Any]) -> Dict[str, Any]:
        # 同步执行不支持，委托到异步
        return {
            "success": False,
            "error": "Sync not supported, use async",
            "data": None,
        }

    async def _arun(self, pet_id: UUID, updates: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行：更新宠物档案到数据库。

        Args:
            pet_id: 宠物ID
            updates: 要更新的字段键值对

        Returns:
            操作结果
        """
        from sqlalchemy import select

        from models.pet import Pet
        from services.database import db

        try:
            async with db.get_session() as session:
                # 查询宠物实体
                stmt = select(Pet).where(Pet.id == pet_id)
                result = await session.execute(stmt)
                pet = result.scalar_one_or_none()

                if pet is None:
                    return {
                        "success": False,
                        "error": f"Pet not found: {pet_id}",
                        "data": None,
                    }

                # 更新字段
                for field, value in updates.items():
                    if hasattr(pet, field):
                        setattr(pet, field, value)
                    else:
                        logger.warning(f"Pet model has no attribute: {field}")

                await session.commit()

                # 返回更新后的基本信息
                return {
                    "success": True,
                    "error": None,
                    "data": {
                        "pet_id": str(pet.id),
                        "name": pet.name,
                        "updated_fields": list(updates.keys()),
                    },
                }

        except Exception as e:
            logger.error(f"Update pet profile failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Update failed: {str(e)}",
                "data": None,
            }


class CreatePetProfileInput(BaseModel):
    """创建宠物档案输入参数。"""
    user_id: UUID = Field(..., description="用户ID")
    name: str = Field(..., description="宠物名字")


class SwitchActivePetInput(BaseModel):
    """切换活跃宠物输入参数。"""
    pet_id: UUID = Field(..., description="要切换到的宠物ID")


class CreatePetProfileTool(BaseTool):
    """创建新宠物档案工具。

    用于新用户首次建立档案时创建第一条宠物记录。
    """
    name: str = "create_pet_profile"
    description: str = "创建新的宠物档案，用于首次建档"
    args_schema: type[BaseModel] = CreatePetProfileInput

    def _run(self, user_id: UUID, name: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "Sync not supported, use async",
            "data": None,
        }

    async def _arun(self, user_id: UUID, name: str) -> Dict[str, Any]:
        """异步执行：创建新宠物档案。

        Args:
            user_id: 拥有者用户ID
            name: 宠物名字

        Returns:
            操作结果，包含新建宠物ID
        """
        import uuid

        from models.pet import Pet
        from services.database import db

        try:
            async with db.get_session() as session:
                # 创建新宠物记录
                from models.pet import PetSpecies
                pet = Pet(
                    id=uuid.uuid4(),
                    name=name,
                    species=PetSpecies.OTHER,  # 默认先设为其他，后续收集信息更新
                    owner_id=user_id,
                    is_active=True,
                )
                session.add(pet)
                await session.commit()

                return {
                    "success": True,
                    "error": None,
                    "data": {
                        "pet_id": str(pet.id),
                        "name": pet.name,
                    },
                }

        except Exception as e:
            logger.error(f"Create pet profile failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Create failed: {str(e)}",
                "data": None,
            }


class SwitchActivePetTool(BaseTool):
    """切换当前活跃宠物工具。

    切换对话上下文使用的活跃宠物。
    """
    name: str = "switch_active_pet"
    description: str = "切换当前对话的活跃宠物，后续操作都针对此宠物"
    args_schema: type[BaseModel] = SwitchActivePetInput

    def _run(self, pet_id: UUID) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "Sync not supported, use async",
            "data": None,
        }

    async def _arun(self, pet_id: UUID) -> Dict[str, Any]:
        """异步执行：切换当前活跃宠物到 Redis。

        Args:
            pet_id: 要切换到的宠物ID

        Returns:
            操作结果
        """
        from sqlalchemy import select

        from models.pet import Pet
        from services.database import db
        from services.redis import redis_service

        try:
            # 先验证宠物存在且属于当前用户
            async with db.get_session() as session:
                stmt = select(Pet).where(Pet.id == pet_id, Pet.is_active == True)
                result = await session.execute(stmt)
                pet = result.scalar_one_or_none()

                if pet is None:
                    return {
                        "success": False,
                        "error": f"Pet not found or inactive: {pet_id}",
                        "data": None,
                    }

            # 写入 Redis（user_id 从 AgentState 上下文传入，这里用 pet.owner_id）
            # 注意：实际调用时 user_id 由 Agent 编排层注入
            await redis_service.set_active_pet(
                user_id=str(pet.owner_id),
                pet_id=str(pet_id),
            )

            logger.info(f"活跃宠物切换成功: user_id={pet.owner_id}, pet_id={pet_id}, pet_name={pet.name}")

            return {
                "success": True,
                "error": None,
                "data": {
                    "pet_id": str(pet_id),
                    "pet_name": pet.name,
                    "message": f"已切换到 {pet.name}",
                },
            }

        except Exception as e:
            logger.error(f"Switch active pet failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Switch failed: {str(e)}",
                "data": None,
            }


# ========== 记录工具 ==========

class LogMealInput(BaseModel):
    """记录饮食输入参数。"""
    pet_id: Optional[UUID] = Field(None, description="宠物ID，不提供则使用当前活跃宠物")
    user_id: UUID = Field(..., description="记录创建者用户ID")
    food_name: str = Field(..., description="食物名称")
    amount: float = Field(..., description="分量（克）")
    notes: Optional[str] = Field(None, description="备注信息")
    image_url: Optional[str] = Field(None, description="食物图片URL")


class LogMealTool(BaseTool):
    """记录饮食工具。

    记录宠物的饮食摄入。
    """
    name: str = "log_meal"
    description: str = "记录宠物的饮食，包括食物名称和分量"
    args_schema: type[BaseModel] = LogMealInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        # 同步执行不支持，委托到异步
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(self,
        food_name: str,
        amount: float,
        pet_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        notes: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步执行：把饮食字段提取为草稿，等待用户确认后再入库。

        Args:
            pet_id: 宠物ID，不提供则使用当前活跃宠物
            user_id: 记录创建者用户ID
            food_name: 食物名称
            amount: 分量（克）
            notes: 备注信息
            image_url: 食物图片URL

        Returns:
            草稿结构：{success, requires_confirmation, data: {draft_id, ...}}
        """
        from datetime import datetime

        if pet_id is None:
            return {
                "success": False,
                "error": "pet_id is required",
                "data": None,
            }
        if user_id is None:
            return {
                "success": False,
                "error": "user_id is required",
                "data": None,
            }

        try:
            payload = {
                "food_name": food_name,
                "amount": amount,
                "unit": "g",
                "meal_time": datetime.now().isoformat(),
                "notes": notes,
                "photo_url": image_url,
            }
            summary = f"记录一次饮食：{food_name} {amount}g"
            return await _create_log_draft(
                "meal", pet_id, user_id, payload, summary
            )

        except Exception as e:
            logger.error(f"Log meal draft failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": None,
            }


class LogActivityInput(BaseModel):
    """记录运动输入参数。"""
    pet_id: Optional[UUID] = Field(None, description="宠物ID")
    user_id: Optional[UUID] = Field(None, description="用户ID，由 Agent 上下文注入")
    activity_type: str = Field(..., description="运动类型（散步/玩耍/游泳等）")
    duration_minutes: float = Field(..., description="持续时间（分钟）")
    notes: Optional[str] = Field(None, description="备注")


class LogActivityTool(BaseTool):
    """记录运动活动工具。"""
    name: str = "log_activity"
    description: str = "记录宠物的运动活动，包括类型和时长"
    args_schema: type[BaseModel] = LogActivityInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(
        self,
        activity_type: str,
        duration_minutes: float,
        pet_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步执行：把运动字段提取为草稿，等待用户确认后再入库。

        Args:
            pet_id: 宠物ID
            activity_type: 运动类型（散步/玩耍/游泳等）
            duration_minutes: 持续时间（分钟）
            notes: 备注

        Returns:
            草稿结构：{success, requires_confirmation, data: {draft_id, ...}}
        """
        from datetime import datetime

        if pet_id is None:
            return {
                "success": False,
                "error": "pet_id is required",
                "data": None,
            }

        # 映射中文活动类型到枚举
        activity_map = {
            "散步": "walk", "跑步": "run", "玩耍": "play",
            "游泳": "swim", "训练": "training",
            "walk": "walk", "run": "run", "play": "play",
            "swim": "swim", "training": "training",
        }
        mapped_type = activity_map.get(activity_type.lower(), "other")

        try:
            payload = {
                "activity_type": mapped_type,
                "duration_minutes": int(duration_minutes),
                "activity_time": datetime.now().isoformat(),
                "notes": notes,
            }
            summary = f"记录一次运动：{activity_type} {int(duration_minutes)} 分钟"
            return await _create_log_draft(
                "activity", pet_id, user_id or pet_id, payload, summary
            )

        except Exception as e:
            logger.error(f"Log activity draft failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": None,
            }


class LogWeightInput(BaseModel):
    """记录体重输入参数。"""
    pet_id: Optional[UUID] = Field(None, description="宠物ID")
    user_id: Optional[UUID] = Field(None, description="用户ID，由 Agent 上下文注入")
    weight_kg: float = Field(..., description="体重（公斤）")


class LogWeightTool(BaseTool):
    """记录体重工具。"""
    name: str = "log_weight"
    description: str = "记录宠物的体重"
    args_schema: type[BaseModel] = LogWeightInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(
        self,
        weight_kg: float,
        pet_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """异步执行：把体重字段提取为草稿，等待用户确认后再入库。

        Args:
            pet_id: 宠物ID
            weight_kg: 体重（公斤）

        Returns:
            草稿结构：{success, requires_confirmation, data: {draft_id, ...}}
        """
        if pet_id is None:
            return {
                "success": False,
                "error": "pet_id is required",
                "data": None,
            }

        try:
            payload = {"weight_kg": weight_kg}
            summary = f"记录体重：{weight_kg} kg"
            return await _create_log_draft(
                "weight", pet_id, user_id or pet_id, payload, summary
            )

        except Exception as e:
            logger.error(f"Log weight draft failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": None,
            }


# ========== 营养分析工具 ==========

class CalculateNutritionInput(BaseModel):
    """计算营养成分输入参数。"""
    food_name: str = Field(..., description="食物名称")
    amount_grams: float = Field(..., description="分量（克）")


class CalculateNutritionTool(BaseTool):
    """计算食物营养成分工具。

    根据食物名称和分量，计算卡路里、蛋白质、脂肪、碳水等营养成分。
    从通用营养数据库查询基准数据（每100克），然后按比例计算。
    """
    name: str = "calculate_nutrition"
    description: str = "计算食物的营养成分，包括卡路里、蛋白质、脂肪等"
    args_schema: type[BaseModel] = CalculateNutritionInput

    def _run(self, food_name: str, amount_grams: float) -> Dict[str, Any]:
        # 同步执行不支持，委托到异步
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(self, food_name: str, amount_grams: float) -> Dict[str, Any]:
        """异步执行：查询营养数据库并计算给定分量的营养成分。

        Args:
            food_name: 食物名称
            amount_grams: 分量（克）

        Returns:
            计算结果，包含各种营养素
        """
        from sqlalchemy import or_, select

        from models.nutrition import FoodNutrition
        from services.database import db

        try:
            async with db.get_session() as session:
                # 模糊搜索匹配食物名称
                stmt = select(FoodNutrition).where(
                    or_(
                        FoodNutrition.food_name == food_name,
                        FoodNutrition.food_name.contains(food_name),
                    )
                ).limit(1)
                result = await session.execute(stmt)
                food = result.scalar_one_or_none()

                if food is None:
                    return {
                        "success": False,
                        "error": f"Food not found in nutrition database: {food_name}",
                        "data": None,
                    }

                # 计算给定分量的营养
                calculated = food.calculate_for_amount(amount_grams)

                # 构建返回数据
                data = {
                    "food_name": food.food_name,
                    "food_category": food.food_category,
                    "amount_grams": amount_grams,
                    "nutrition_per_100g": {
                        "calories": float(food.calories) if food.calories else None,
                        "protein": float(food.protein) if food.protein else None,
                        "fat": float(food.fat) if food.fat else None,
                        "carbs": float(food.carbs) if food.carbs else None,
                        "fiber": float(food.fiber) if food.fiber else None,
                    },
                    "calculated": calculated,
                    "total_calories": calculated.get("calories"),
                }

                return {
                    "success": True,
                    "error": None,
                    "data": data,
                }

        except Exception as e:
            logger.error(f"Calculate nutrition failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Calculate failed: {str(e)}",
                "data": None,
            }


class EvaluateDietInput(BaseModel):
    """评估饮食是否满足需求输入参数。"""
    pet_id: Optional[UUID] = Field(None, description="宠物ID")
    daily_intake: List[Dict[str, Any]] = Field(..., description="今日摄入列表")


class EvaluateDietTool(BaseTool):
    """对比 AAFCO 标准评估饮食摄入工具。"""
    name: str = "evaluate_diet_vs_needs"
    description: str = "根据宠物需求评估今日饮食摄入是否符合AAFCO标准"
    args_schema: type[BaseModel] = EvaluateDietInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(
        self,
        daily_intake: List[Dict[str, Any]],
        pet_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """异步执行：基于 AAFCO 标准评估今日饮食摄入。

        根据宠物物种（狗/猫）和体重，计算推荐每日摄入量，与实际摄入对比。

        AAFCO 标准参考值（成年犬/猫，每 kg 体重）：
        - 狗：蛋白 ≥ 1.8g, 脂肪 ≥ 1.4g, 钙 1.25-2.5g, 磷 1.0-2.5g
        - 猫：蛋白 ≥ 2.5g, 脂肪 ≥ 3.3g, 钙 1.0-3.0g, 磷 0.8-2.5g

        Args:
            pet_id: 宠物ID（用于获取体重和物种）
            daily_intake: 今日摄入列表，每项包含 {food_name, amount_grams, calories, protein, fat, carbs, calcium, phosphorus}

        Returns:
            评估结果，包含达标/不达标项和建议
        """
        from sqlalchemy import select

        from models.pet import Pet
        from services.database import db

        try:
            # 获取宠物信息
            pet_weight = 10.0  # 默认值
            pet_species = "dog"
            if pet_id:
                async with db.get_session() as session:
                    stmt = select(Pet).where(Pet.id == pet_id)
                    result = await session.execute(stmt)
                    pet = result.scalar_one_or_none()
                    if pet:
                        pet_weight = float(pet.current_weight) if pet.current_weight else 10.0
                        pet_species = pet.species.value if pet.species else "dog"

            # AAFCO 标准参考值（每 kg 体重每天）
            standards: Dict[str, Union[float, Tuple[float, float]]] = {}
            if pet_species == "cat":
                standards = {
                    "protein_g_per_kg": 2.5,
                    "fat_g_per_kg": 3.3,
                    "calcium_g_per_kg": (1.0, 3.0),
                    "phosphorus_g_per_kg": (0.8, 2.5),
                }
            else:  # dog
                standards = {
                    "protein_g_per_kg": 1.8,
                    "fat_g_per_kg": 1.4,
                    "calcium_g_per_kg": (1.25, 2.5),
                    "phosphorus_g_per_kg": (1.0, 2.5),
                }

            # 汇总今日摄入
            total_calories = 0.0
            total_protein = 0.0
            total_fat = 0.0
            total_carbs = 0.0
            total_calcium = 0.0
            total_phosphorus = 0.0
            food_details = []

            for item in daily_intake:
                total_calories += item.get("calories", 0) or 0
                total_protein += item.get("protein", 0) or 0
                total_fat += item.get("fat", 0) or 0
                total_carbs += item.get("carbs", 0) or 0
                total_calcium += item.get("calcium", 0) or 0  # mg
                total_phosphorus += item.get("phosphorus", 0) or 0  # mg
                food_details.append({
                    "food_name": item.get("food_name", "未知"),
                    "amount_grams": item.get("amount_grams", 0),
                })

            # 计算每 kg 体重摄入量
            protein_per_kg = total_protein / pet_weight if pet_weight > 0 else 0
            fat_per_kg = total_fat / pet_weight if pet_weight > 0 else 0
            calcium_per_kg_g = (total_calcium / 1000) / pet_weight if pet_weight > 0 else 0
            phosphorus_per_kg_g = (total_phosphorus / 1000) / pet_weight if pet_weight > 0 else 0

            # 评估各项
            evaluations = []
            warnings = []

            # 蛋白质
            protein_standard = float(standards["protein_g_per_kg"])  # type: ignore[arg-type]
            if protein_per_kg >= protein_standard:
                evaluations.append({"nutrient": "蛋白质", "status": "达标", "actual": round(protein_per_kg, 2), "recommended": protein_standard})
            else:
                evaluations.append({"nutrient": "蛋白质", "status": "不足", "actual": round(protein_per_kg, 2), "recommended": protein_standard})
                warnings.append(f"蛋白质摄入不足：当前 {protein_per_kg:.1f}g/kg，建议 ≥ {protein_standard}g/kg")

            # 脂肪
            fat_standard = float(standards["fat_g_per_kg"])  # type: ignore[arg-type]
            if fat_per_kg >= fat_standard:
                evaluations.append({"nutrient": "脂肪", "status": "达标", "actual": round(fat_per_kg, 2), "recommended": fat_standard})
            else:
                evaluations.append({"nutrient": "脂肪", "status": "不足", "actual": round(fat_per_kg, 2), "recommended": fat_standard})
                warnings.append(f"脂肪摄入不足：当前 {fat_per_kg:.1f}g/kg，建议 ≥ {fat_standard}g/kg")

            # 钙
            ca_range = standards["calcium_g_per_kg"]  # type: ignore[assignment]
            ca_min, ca_max = ca_range  # type: ignore[misc]
            if ca_min <= calcium_per_kg_g <= ca_max:
                evaluations.append({"nutrient": "钙", "status": "达标", "actual": round(calcium_per_kg_g, 2), "recommended": f"{ca_min}-{ca_max}"})
            elif calcium_per_kg_g < ca_min:
                evaluations.append({"nutrient": "钙", "status": "不足", "actual": round(calcium_per_kg_g, 2), "recommended": f"{ca_min}-{ca_max}"})
                warnings.append(f"钙摄入不足：当前 {calcium_per_kg_g:.2f}g/kg，建议 {ca_min}-{ca_max}g/kg")
            else:
                evaluations.append({"nutrient": "钙", "status": "过量", "actual": round(calcium_per_kg_g, 2), "recommended": f"{ca_min}-{ca_max}"})
                warnings.append(f"⚠️ 钙摄入过量：当前 {calcium_per_kg_g:.2f}g/kg，建议 {ca_min}-{ca_max}g/kg，过量可能影响健康")

            # 磷
            p_range = standards["phosphorus_g_per_kg"]  # type: ignore[assignment]
            p_min, p_max = p_range  # type: ignore[misc]
            if p_min <= phosphorus_per_kg_g <= p_max:
                evaluations.append({"nutrient": "磷", "status": "达标", "actual": round(phosphorus_per_kg_g, 2), "recommended": f"{p_min}-{p_max}"})
            elif phosphorus_per_kg_g < p_min:
                evaluations.append({"nutrient": "磷", "status": "不足", "actual": round(phosphorus_per_kg_g, 2), "recommended": f"{p_min}-{p_max}"})
                warnings.append(f"磷摄入不足：当前 {phosphorus_per_kg_g:.2f}g/kg，建议 {p_min}-{p_max}g/kg")
            else:
                evaluations.append({"nutrient": "磷", "status": "过量", "actual": round(phosphorus_per_kg_g, 2), "recommended": f"{p_min}-{p_max}"})
                warnings.append(f"⚠️ 磷摄入过量：当前 {phosphorus_per_kg_g:.2f}g/kg，建议 {p_min}-{p_max}g/kg")

            passed_count = sum(1 for e in evaluations if e["status"] == "达标")
            overall = "良好" if passed_count >= 3 else ("一般" if passed_count >= 2 else "需改善")

            return {
                "success": True,
                "error": None,
                "data": {
                    "pet_weight_kg": pet_weight,
                    "pet_species": pet_species,
                    "overall_rating": overall,
                    "total_intake": {
                        "calories_kcal": round(total_calories, 1),
                        "protein_g": round(total_protein, 1),
                        "fat_g": round(total_fat, 1),
                        "carbs_g": round(total_carbs, 1),
                        "calcium_mg": round(total_calcium, 1),
                        "phosphorus_mg": round(total_phosphorus, 1),
                    },
                    "per_kg_bodyweight": {
                        "protein_g_per_kg": round(protein_per_kg, 2),
                        "fat_g_per_kg": round(fat_per_kg, 2),
                        "calcium_g_per_kg": round(calcium_per_kg_g, 2),
                        "phosphorus_g_per_kg": round(phosphorus_per_kg_g, 2),
                    },
                    "evaluations": evaluations,
                    "warnings": warnings,
                    "food_count": len(food_details),
                },
            }

        except Exception as e:
            logger.error(f"Evaluate diet failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Evaluate failed: {str(e)}",
                "data": None,
            }


class GenerateRecipeInput(BaseModel):
    """生成食谱输入参数。"""
    pet_id: Optional[UUID] = Field(None, description="宠物ID")
    goals: List[str] = Field(..., description="目标（减肥/增肌/过敏等）")
    restrictions: Optional[List[str]] = Field(None, description="忌口限制")


class GenerateRecipeTool(BaseTool):
    """生成个性化食谱工具。"""
    name: str = "generate_recipe"
    description: str = "根据宠物情况和目标生成个性化食谱"
    args_schema: type[BaseModel] = GenerateRecipeInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(
        self,
        goals: List[str],
        pet_id: Optional[UUID] = None,
        restrictions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """异步执行：基于宠物信息和营养数据库生成个性化食谱。

        根据宠物档案、目标（减肥/增肌/过敏回避等）和忌口限制，
        查询营养数据库，通过 LLM 生成食谱并写入数据库。

        Args:
            pet_id: 宠物ID
            goals: 目标列表（减肥/增肌/过敏回避等）
            restrictions: 忌口限制列表

        Returns:
            操作结果，包含生成的食谱
        """
        import uuid
        from decimal import Decimal

        from sqlalchemy import select

        from core.config import settings
        from models.pet import Pet
        from models.recipe import Recipe, RecipeIngredient, RecipeSource, RecipeType
        from services.database import db

        try:
            # 1. 获取宠物信息
            pet_info = {}
            if pet_id:
                async with db.get_session() as session:
                    stmt = select(Pet).where(Pet.id == pet_id)
                    result = await session.execute(stmt)
                    pet = result.scalar_one_or_none()
                    if pet:
                        pet_info = {
                            "name": pet.name,
                            "species": pet.species.value if pet.species else "dog",
                            "weight": float(pet.current_weight) if pet.current_weight else 10.0,
                            "ideal_weight": float(pet.ideal_weight) if pet.ideal_weight else None,
                            "allergy_blacklist": pet.allergy_blacklist,
                            "main_food_brand": pet.main_food_brand,
                            "known_diseases": pet.known_diseases,
                        }

            # 2. 确定 recipe_type
            goal_str = "、".join(goals) if goals else "日常"
            recipe_type = RecipeType.DAILY
            if any(g in str(goal_str) for g in ["减肥", "减重", "瘦身"]):
                recipe_type = RecipeType.WEIGHT_LOSS
            elif any(g in str(goal_str) for g in ["增重", "增肌"]):
                recipe_type = RecipeType.WEIGHT_GAIN
            elif any(g in str(goal_str) for g in ["自制"]):
                recipe_type = RecipeType.HOMEMADE

            # 3. 查询安全食材
            safe_foods = []
            async with db.get_session() as session:
                from models.nutrition import FoodNutrition
                food_stmt = select(FoodNutrition).where(FoodNutrition.is_pet_safe == True).limit(50)
                food_result = await session.execute(food_stmt)
                foods = food_result.scalars().all()
                safe_foods = [
                    {
                        "name": f.food_name,
                        "category": f.food_category,
                        "calories_100g": float(f.calories) if f.calories else 0,
                        "protein_100g": float(f.protein) if f.protein else 0,
                        "fat_100g": float(f.fat) if f.fat else 0,
                    }
                    for f in foods
                ]

            # 4. 用 LLM 生成食谱
            recipe_name = f"{pet_info.get('name', '宠物')}的{'、'.join(goals[:2]) if goals else '日常'}食谱"

            # 尝试调用 LLM 生成食谱内容
            recipe_content = None
            ingredients_data = []

            if settings.anthropic_api_key or settings.openai_api_key:
                try:
                    from langchain_anthropic import ChatAnthropic
                    from langchain_core.messages import HumanMessage

                    llm = ChatAnthropic(
                        model="claude-sonnet-4-20250514",
                        anthropic_api_key=settings.anthropic_api_key,  # type: ignore[call-arg]
                    ) if settings.anthropic_api_key else None  # type: ignore[call-arg]

                    if not llm and settings.openai_api_key:
                        from langchain_openai import ChatOpenAI
                        llm = ChatOpenAI(
                            model="gpt-4o-mini",
                            openai_api_key=settings.openai_api_key,  # type: ignore[call-arg]
                        )  # type: ignore[assignment]

                    if llm:
                        prompt = f"""你是一位宠物营养师。请根据以下信息生成一个一日食谱。

宠物信息：{pet_info}
目标：{goals}
忌口限制：{restrictions or '无'}
可用食材：{[f['name'] for f in safe_foods[:20]]}

请以 JSON 格式返回，格式如下：
{{
    "description": "食谱描述和喂养建议",
    "meals": [
        {{"meal_name": "早餐", "ingredients": [{{"food_name": "鸡胸肉", "amount_grams": 100, "calories_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carb_per_100g": 0}}]}}
    ]
}}

只返回 JSON，不要其他文字。"""

                        response = await llm.ainvoke([HumanMessage(content=prompt)])
                        import json
                        recipe_content = json.loads(str(response.content))
                        ingredients_data = recipe_content.get("meals", [])

                except Exception as llm_err:
                    logger.warning(f"LLM recipe generation failed, using fallback: {llm_err}")

            # 5. Fallback：如果没有 LLM 结果，使用简单规则生成
            if not recipe_content:
                recipe_content = {
                    "description": f"基于{'、'.join(goals) if goals else '日常需求'}的推荐食谱。建议根据宠物实际反应调整。",
                    "meals": [
                        {
                            "meal_name": "早餐",
                            "ingredients": [
                                {"food_name": "鸡胸肉", "amount_grams": 80, "calories_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carb_per_100g": 0},
                                {"food_name": "糙米", "amount_grams": 40, "calories_per_100g": 112, "protein_per_100g": 2.6, "fat_per_100g": 0.9, "carb_per_100g": 23},
                            ],
                        },
                        {
                            "meal_name": "晚餐",
                            "ingredients": [
                                {"food_name": "三文鱼", "amount_grams": 60, "calories_per_100g": 208, "protein_per_100g": 20, "fat_per_100g": 13, "carb_per_100g": 0},
                                {"food_name": "南瓜", "amount_grams": 50, "calories_per_100g": 26, "protein_per_100g": 1, "fat_per_100g": 0.1, "carb_per_100g": 5},
                            ],
                        },
                    ],
                }
                ingredients_data = recipe_content.get("meals", [])

            # 6. 写入数据库
            async with db.get_session() as session:
                recipe = Recipe(
                    id=uuid.uuid4(),
                    pet_id=pet_id,
                    name=recipe_name,
                    description=recipe_content.get("description", ""),
                    recipe_type=recipe_type,
                    source=RecipeSource.AI_GENERATED,
                    is_active=True,
                    notes=f"目标：{goal_str}" + (f" | 忌口：{'、'.join(restrictions)}" if restrictions else ""),
                )
                session.add(recipe)

                for meal in ingredients_data:
                    for ing in meal.get("ingredients", []):
                        ingredient = RecipeIngredient(
                            id=uuid.uuid4(),
                            recipe_id=recipe.id,
                            food_name=ing.get("food_name", "未知"),
                            amount=Decimal(str(ing.get("amount_grams", 0))),
                            unit="g",
                            calories_per_unit=Decimal(str(round(ing.get("calories_per_100g", 0) * (ing.get("amount_grams", 0) / 100), 1))) if ing.get("calories_per_100g") else None,
                            protein_per_unit=Decimal(str(round(ing.get("protein_per_100g", 0) * (ing.get("amount_grams", 0) / 100), 2))) if ing.get("protein_per_100g") else None,
                            fat_per_unit=Decimal(str(round(ing.get("fat_per_100g", 0) * (ing.get("amount_grams", 0) / 100), 2))) if ing.get("fat_per_100g") else None,
                            carb_per_unit=Decimal(str(round(ing.get("carb_per_100g", 0) * (ing.get("amount_grams", 0) / 100), 2))) if ing.get("carb_per_100g") else None,
                        )
                        session.add(ingredient)

                await session.commit()

                logger.info(f"食谱生成成功: id={recipe.id}, pet_id={pet_id}, name={recipe_name}")

                return {
                    "success": True,
                    "error": None,
                    "data": {
                        "recipe_id": str(recipe.id),
                        "recipe_name": recipe_name,
                        "recipe_type": recipe_type.value,
                        "description": recipe_content.get("description", ""),
                        "meals": [
                            {
                                "meal_name": meal.get("meal_name", ""),
                                "ingredients": [
                                    {"food_name": ing.get("food_name"), "amount_grams": ing.get("amount_grams")}
                                    for ing in meal.get("ingredients", [])
                                ],
                            }
                            for meal in ingredients_data
                        ],
                    },
                }

        except Exception as e:
            logger.error(f"Generate recipe failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Generate failed: {str(e)}",
                "data": None,
            }


# ========== 多媒体处理工具 ==========

class RecognizeFoodImageInput(BaseModel):
    """识别食物图片输入参数。"""
    image_url: str = Field(..., description="图片URL")


class RecognizeFoodImageTool(BaseTool):
    """识别图片中的食物工具。

    使用 GPT-4o Vision 识别照片中的食物。
    """
    name: str = "recognize_food_image"
    description: str = "识别图片中的食物，返回食物名称和大致分量"
    args_schema: type[BaseModel] = RecognizeFoodImageInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(self, image_url: str) -> Dict[str, Any]:
        """异步执行：通过 GPT-4o Vision 识别图片中的食物。

        Args:
            image_url: 图片URL

        Returns:
            识别结果，包含食物名称、估算分量、置信度
        """
        import base64
        import json

        import httpx

        from core.config import settings

        try:
            if not settings.openai_api_key:
                return {
                    "success": False,
                    "error": "OpenAI API key not configured. Cannot use image recognition.",
                    "data": None,
                }

            # 下载图片并转为 base64
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                image_base64 = base64.b64encode(resp.content).decode("utf-8")

            # 判断图片 MIME 类型
            content_type = resp.headers.get("content-type", "image/jpeg")
            data_url = f"data:{content_type};base64,{image_base64}"

            # 调用 GPT-4o Vision API
            async with httpx.AsyncClient(timeout=60.0) as client:
                api_response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "请识别这张图片中的宠物食物。以 JSON 格式返回：{\"foods\": [{\"food_name\": \"食物名称\", \"amount_grams\": 估算克数, \"confidence\": 0.9}]}\n\n只返回 JSON，不要其他文字。",
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": data_url},
                                    },
                                ],
                            }
                        ],
                        "max_tokens": 500,
                    },
                )

                api_response.raise_for_status()
                result = api_response.json()
                content = result["choices"][0]["message"]["content"]

                # 解析 JSON
                # 处理可能的 markdown 代码块包裹
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                parsed = json.loads(content)
                foods = parsed.get("foods", [])

                if not foods:
                    return {
                        "success": False,
                        "error": "No food identified in the image",
                        "data": None,
                    }

                logger.info(f"食物图片识别成功: 识别到 {len(foods)} 种食物")

                return {
                    "success": True,
                    "error": None,
                    "data": {
                        "foods": foods,
                        "image_url": image_url,
                    },
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Food image recognition API error: {e.response.status_code}")
            return {
                "success": False,
                "error": f"Image recognition API error: {e.response.status_code}",
                "data": None,
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse image recognition response: {e}")
            return {
                "success": False,
                "error": f"Failed to parse recognition result: {str(e)}",
                "data": None,
            }
        except Exception as e:
            logger.error(f"Recognize food image failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Recognition failed: {str(e)}",
                "data": None,
            }


class TranscribeVoiceInput(BaseModel):
    """语音转文字输入参数。"""
    voice_url: str = Field(..., description="语音文件URL")


class TranscribeVoiceTool(BaseTool):
    """语音转文字工具。"""
    name: str = "transcribe_voice"
    description: str = "将语音转换为文字"
    args_schema: type[BaseModel] = TranscribeVoiceInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(self, voice_url: str) -> Dict[str, Any]:
        """异步执行：通过腾讯云 ASR 将语音转为文字。

        使用腾讯云一句话识别 API（SentencesRecognition）进行语音转文字。
        也可 fallback 到 OpenAI Whisper API。

        Args:
            voice_url: 语音文件URL（支持 mp3/wav/amr 格式）

        Returns:
            转写结果，包含识别出的文字
        """
        from core.config import settings

        try:
            # 优先使用腾讯云 ASR
            if settings.tencent_secret_id and settings.tencent_secret_key:
                return await self._transcribe_tencent_asr(voice_url)

            # Fallback 到 OpenAI Whisper
            if settings.openai_api_key:
                return await self._transcribe_whisper(voice_url)

            return {
                "success": False,
                "error": "No speech recognition service configured. Set TENCENT_SECRET_ID/KEY or OPENAI_API_KEY.",
                "data": None,
            }

        except Exception as e:
            logger.error(f"Transcribe voice failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Transcription failed: {str(e)}",
                "data": None,
            }

    @staticmethod
    async def _transcribe_tencent_asr(voice_url: str) -> Dict[str, Any]:
        """使用腾讯云一句话识别 API。"""
        import base64
        import hashlib
        import hmac
        import time

        import httpx

        from core.config import settings

        # 下载音频文件
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(voice_url)
            resp.raise_for_status()
            audio_data = resp.content
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        # 腾讯云一句话识别 API
        timestamp = int(time.time())
        params = {
            "SecretId": settings.tencent_secret_id,
            "Timestamp": timestamp,
            "Expired": timestamp + 86400,
            "Nonce": 12345,
            "EngineModelType": "16k_zh",  # 16k 中文模型
        }

        # 排序参数并签名
        params_str = "&".join(f"{k}={params[k]}" for k in sorted(params))
        sign_str = "GETasr.cloud.tencent.com/asr/v2/?" + params_str
        secret_key_bytes = settings.tencent_secret_key.encode("utf-8")  # type: ignore[union-attr]
        signature = hmac.new(secret_key_bytes, sign_str.encode("utf-8"), hashlib.sha1).digest()
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        params["Signature"] = signature_b64
        params["EngSerViceType"] = "16k_zh"
        params["SourceType"] = 1  # 音频数据
        params["Data"] = audio_base64
        params["DataLen"] = len(audio_data)

        api_url = "https://asr.cloud.tencent.com/asr/v2/"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(api_url, params=params)
            resp.raise_for_status()
            result = resp.json()

        if result.get("Response", {}).get("Error", {}).get("Code"):
            error = result["Response"]["Error"]
            return {
                "success": False,
                "error": f"Tencent ASR error: {error.get('Code')} - {error.get('Message')}",
                "data": None,
            }

        text = result.get("Response", {}).get("Result", "")
        logger.info(f"腾讯云 ASR 转写成功: text length={len(text)}")

        return {
            "success": True,
            "error": None,
            "data": {
                "text": text,
                "provider": "tencent_asr",
            },
        }

    @staticmethod
    async def _transcribe_whisper(voice_url: str) -> Dict[str, Any]:
        """使用 OpenAI Whisper API 作为 fallback。"""

        import httpx

        from core.config import settings

        # 下载音频文件
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(voice_url)
            resp.raise_for_status()
            audio_data = resp.content

        # 调用 Whisper API
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                files={"file": ("audio.mp3", audio_data)},
                data={"model": "whisper-1", "language": "zh"},
            )
            resp.raise_for_status()
            result = resp.json()

        text = result.get("text", "")
        logger.info(f"Whisper 转写成功: text length={len(text)}")

        return {
            "success": True,
            "error": None,
            "data": {
                "text": text,
                "provider": "openai_whisper",
            },
        }


# ========== 实用工具 ==========

class SearchNearbyHospitalInput(BaseModel):
    """搜索附近医院输入参数。"""
    location: str = Field(..., description="位置（城市/区/经纬度）")
    radius_km: float = Field(default=5.0, description="搜索范围（公里）")


class SearchNearbyHospitalTool(BaseTool):
    """搜索附近宠物医院工具。"""
    name: str = "search_nearby_hospital"
    description: str = "搜索附近的宠物医院"
    args_schema: type[BaseModel] = SearchNearbyHospitalInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(
        self,
        location: str,
        radius_km: float = 5.0,
    ) -> Dict[str, Any]:
        """异步执行：通过腾讯地图 WebService API 搜索附近宠物医院。

        Args:
            location: 位置（城市名、区名或经纬度 "lat,lng"）
            radius_km: 搜索范围（公里）

        Returns:
            搜索结果，包含医院列表
        """
        import httpx

        from core.config import settings

        try:
            if not settings.tencent_secret_id or not settings.tencent_secret_key:
                return {
                    "success": False,
                    "error": "Tencent Cloud credentials not configured. Cannot search nearby hospitals.",
                    "data": None,
                }

            # 腾讯地图 WebService API - 地点搜索
            api_url = "https://apis.map.qq.com/ws/place/v1/search"

            # 如果传入的是文本位置（如"北京朝阳区"），先进行地理编码
            # 否则如果是经纬度格式，直接使用
            if "," in location and location.replace(",", "").replace(".", "").replace("-", "").replace(" ", "").isdigit():
                boundary = f"nearby({location},{int(radius_km * 1000)})"
            else:
                boundary = f"region({location})"

            params = {
                "keyword": "宠物医院",
                "boundary": boundary,
                "page_size": 10,
                "page_index": 1,
                "orderby": "_distance",
                "output": "json",
            }

            # 生成签名

            # 腾讯地图使用 key + sig 机制
            map_key = settings.tencent_map_key or settings.tencent_secret_id
            if not map_key:
                return {
                    "success": False,
                    "error": "Tencent Map API key not configured. Set TENCENT_MAP_KEY in .env",
                    "data": None,
                }
            params["key"] = map_key

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(api_url, params=params)  # type: ignore[arg-type]
                resp.raise_for_status()
                result = resp.json()

            if result.get("status") != 0:
                return {
                    "success": False,
                    "error": f"Map API error: {result.get('message', 'Unknown error')}",
                    "data": None,
                }

            hospitals = []
            for item in result.get("data", []):
                hospitals.append({
                    "name": item.get("title", ""),
                    "address": item.get("address", ""),
                    "lat": item.get("location", {}).get("lat"),
                    "lng": item.get("location", {}).get("lng"),
                    "tel": item.get("tel", ""),
                    "distance": item.get("_distance", ""),
                })

            logger.info(f"附近宠物医院搜索成功: location={location}, found={len(hospitals)}")

            return {
                "success": True,
                "error": None,
                "data": {
                    "location": location,
                    "radius_km": radius_km,
                    "total": result.get("count", 0),
                    "hospitals": hospitals,
                },
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Hospital search API error: {e.response.status_code}")
            return {
                "success": False,
                "error": f"Map API error: {e.response.status_code}",
                "data": None,
            }
        except Exception as e:
            logger.error(f"Search nearby hospital failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Search failed: {str(e)}",
                "data": None,
            }


class WebSearchInput(BaseModel):
    """联网搜索输入参数。"""
    query: str = Field(..., description="搜索关键词")


class WebSearchTool(BaseTool):
    """联网搜索工具。

    搜索宠物食品口碑、最新研究等外部信息。
    """
    name: str = "web_search"
    description: str = "联网搜索宠物食品、用品口碑或最新信息"
    args_schema: type[BaseModel] = WebSearchInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(self, query: str) -> Dict[str, Any]:
        """异步执行：通过 Bing Search API 进行联网搜索。

        Args:
            query: 搜索关键词

        Returns:
            搜索结果列表
        """
        import httpx


        try:
            # 方案 1: 使用 OpenAI 的 search tool (如果可用)
            # 方案 2: 使用 Bing Web Search API
            # 方案 3: fallback 到 DuckDuckGo（免费，无需 key）

            results = []

            # 尝试 DuckDuckGo Instant Answer API（免费，无需 key）
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1,
                        "skip_disambig": 1,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = data.get("Abstract", "")
                    if abstract:
                        results.append({
                            "title": data.get("Heading", ""),
                            "snippet": abstract[:300],
                            "url": data.get("AbstractURL", ""),
                        })
                    for topic in data.get("RelatedTopics", [])[:5]:
                        if isinstance(topic, dict) and topic.get("Text"):
                            results.append({
                                "title": topic.get("Text", "")[:80],
                                "snippet": topic.get("Text", "")[:300],
                                "url": topic.get("FirstURL", ""),
                            })

            if not results:
                return {
                    "success": False,
                    "error": f"No results found for query: {query}",
                    "data": None,
                }

            logger.info(f"联网搜索成功: query={query}, results={len(results)}")

            return {
                "success": True,
                "error": None,
                "data": {
                    "query": query,
                    "results": results,
                    "total": len(results),
                },
            }

        except Exception as e:
            logger.error(f"Web search failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Search failed: {str(e)}",
                "data": None,
            }


class ScheduleReminderInput(BaseModel):
    """安排提醒输入参数。"""
    reminder_type: str = Field(..., description="提醒类型（喂食/吃药/驱虫/疫苗等）")
    schedule: str = Field(..., description="提醒时间安排（每天/每周三等）")
    pet_id: Optional[UUID] = Field(None, description="宠物ID")
    user_id: Optional[UUID] = Field(None, description="用户ID，由 Agent 上下文注入")


class ScheduleReminderTool(BaseTool):
    """安排提醒工具。"""
    name: str = "schedule_reminder"
    description: str = "设置定时提醒，比如喂食、驱虫、疫苗"
    args_schema: type[BaseModel] = ScheduleReminderInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(
        self,
        reminder_type: str,
        schedule: str,
        pet_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """异步执行：创建提醒记录到数据库。

        Args:
            reminder_type: 提醒类型（喂食/吃药/驱虫/疫苗等）
            schedule: 提醒时间安排（每天/每周三等）
            pet_id: 宠物ID

        Returns:
            操作结果，包含提醒ID
        """
        import uuid
        from datetime import datetime, timedelta

        from models.reminder import Reminder, ReminderType, RepeatType
        from services.database import db

        if pet_id is None:
            return {
                "success": False,
                "error": "pet_id is required",
                "data": None,
            }

        try:
            # 映射提醒类型
            type_map = {
                "喂食": ReminderType.FEEDING, "feeding": ReminderType.FEEDING,
                "吃药": ReminderType.MEDICATION, "用药": ReminderType.MEDICATION, "medication": ReminderType.MEDICATION,
                "驱虫": ReminderType.DEWORMING, "deworming": ReminderType.DEWORMING,
                "疫苗": ReminderType.VACCINE, "vaccine": ReminderType.VACCINE,
                "称重": ReminderType.WEIGHING, "weighing": ReminderType.WEIGHING,
                "洗澡": ReminderType.BATH, "bath": ReminderType.BATH,
                "剪指甲": ReminderType.NAIL_TRIM, "nail_trim": ReminderType.NAIL_TRIM,
            }
            mapped_type = type_map.get(reminder_type.lower(), ReminderType.OTHER)

            # 解析重复类型
            repeat_type = RepeatType.NONE
            repeat_interval = None

            schedule_lower = schedule.lower()
            if "每天" in schedule or "每日" in schedule or schedule_lower == "daily":
                repeat_type = RepeatType.DAILY
            elif "每周" in schedule or schedule_lower == "weekly":
                repeat_type = RepeatType.WEEKLY
            elif "每月" in schedule or schedule_lower == "monthly":
                repeat_type = RepeatType.MONTHLY
            else:
                # 尝试解析 "每X天" 格式
                import re
                match = re.search(r"每(\d+)天", schedule)
                if match:
                    repeat_type = RepeatType.EVERY_X_DAYS
                    repeat_interval = int(match.group(1))

            # 计算提醒时间（设为明天同一时间）
            remind_at = datetime.now() + timedelta(days=1)

            # 创建提醒标题
            type_names = {
                ReminderType.FEEDING: "喂食",
                ReminderType.MEDICATION: "用药",
                ReminderType.DEWORMING: "驱虫",
                ReminderType.VACCINE: "疫苗",
                ReminderType.WEIGHING: "称重",
                ReminderType.BATH: "洗澡",
                ReminderType.NAIL_TRIM: "剪指甲",
                ReminderType.OTHER: "提醒",
            }
            type_name = type_names.get(mapped_type, "提醒")
            title = f"{type_name}提醒 - {schedule}"

            async with db.get_session() as session:
                reminder = Reminder(
                    id=uuid.uuid4(),
                    pet_id=pet_id,
                    user_id=user_id or pet_id,
                    reminder_type=mapped_type,
                    title=title,
                    remind_at=remind_at,
                    repeat_type=repeat_type,
                    repeat_interval=repeat_interval,
                )

                # 计算下次提醒时间
                reminder.next_remind_at = reminder.calculate_next_remind()

                session.add(reminder)
                await session.commit()

                logger.info(f"提醒创建成功: id={reminder.id}, pet_id={pet_id}, type={mapped_type.value}, schedule={schedule}")

                return {
                    "success": True,
                    "error": None,
                    "data": {
                        "reminder_id": str(reminder.id),
                        "title": title,
                        "reminder_type": mapped_type.value,
                        "repeat_type": repeat_type.value,
                        "remind_at": remind_at.isoformat(),
                        "next_remind_at": reminder.next_remind_at.isoformat() if reminder.next_remind_at else None,
                    },
                }

        except Exception as e:
            logger.error(f"Schedule reminder failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Schedule failed: {str(e)}",
                "data": None,
            }


class GenerateReportInput(BaseModel):
    """生成健康报告输入参数。"""
    pet_id: UUID = Field(..., description="宠物ID")
    period_days: int = Field(default=30, description="报告周期天数")
    report_type: str = Field(default="summary", description="报告类型")


class GenerateHealthReportTool(BaseTool):
    """生成健康报告工具。"""
    name: str = "generate_health_report"
    description: str = "生成一段时间的宠物健康报告"
    args_schema: type[BaseModel] = GenerateReportInput

    def _run(self, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Sync not supported, use async", "data": None}

    async def _arun(
        self,
        pet_id: UUID,
        period_days: int = 30,
        report_type: str = "summary",
    ) -> Dict[str, Any]:
        """异步执行：聚合宠物历史数据生成健康报告。

        从数据库汇总指定时间段内的饮食、体重、运动数据，
        由 LLM 整合为可读的健康报告文本。

        Args:
            pet_id: 宠物ID
            period_days: 报告周期天数
            report_type: 报告类型（summary/weekly/monthly）

        Returns:
            操作结果，包含健康报告
        """
        from datetime import datetime, timedelta

        from sqlalchemy import func, select

        from core.config import settings
        from models.log import ActivityLog, MealLog, WeightLog
        from models.pet import Pet
        from services.database import db

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            # 聚合数据
            async with db.get_session() as session:
                # 获取宠物基本信息
                pet_stmt = select(Pet).where(Pet.id == pet_id)
                pet_result = await session.execute(pet_stmt)
                pet = pet_result.scalar_one_or_none()

                if pet is None:
                    return {
                        "success": False,
                        "error": f"Pet not found: {pet_id}",
                        "data": None,
                    }

                # 饮食统计
                meal_stmt = select(
                    func.count(MealLog.id).label("total_meals"),
                    func.sum(MealLog.amount).label("total_food_g"),
                ).where(
                    MealLog.pet_id == pet_id,
                    MealLog.meal_time >= start_date,
                    MealLog.meal_time <= end_date,
                )
                meal_result = await session.execute(meal_stmt)
                meal_stats = meal_result.one()

                # 获取每日饮食明细
                daily_meals_stmt = select(MealLog).where(
                    MealLog.pet_id == pet_id,
                    MealLog.meal_time >= start_date,
                    MealLog.meal_time <= end_date,
                ).order_by(MealLog.meal_time.desc())
                daily_meals_result = await session.execute(daily_meals_stmt)
                recent_meals = daily_meals_result.scalars().all()[:10]

                # 运动统计
                activity_stmt = select(
                    func.count(ActivityLog.id).label("total_activities"),
                    func.sum(ActivityLog.duration_minutes).label("total_duration_min"),
                ).where(
                    ActivityLog.pet_id == pet_id,
                    ActivityLog.activity_time >= start_date,
                    ActivityLog.activity_time <= end_date,
                )
                activity_result = await session.execute(activity_stmt)
                activity_stats = activity_result.one()

                # 体重趋势
                weight_stmt = select(WeightLog).where(
                    WeightLog.pet_id == pet_id,
                    WeightLog.measurement_time >= start_date,
                    WeightLog.measurement_time <= end_date,
                ).order_by(WeightLog.measurement_time.asc())
                weight_result = await session.execute(weight_stmt)
                weight_records = weight_result.scalars().all()

            # 构建结构化数据
            weight_trend: List[Dict[str, Any]] = []
            prev_weight = None
            for w in weight_records:
                change = None
                if prev_weight:
                    change = round(float(w.weight) - float(prev_weight), 2)
                weight_trend.append({
                    "date": w.measurement_time.strftime("%m-%d"),
                    "weight_kg": float(w.weight),
                    "change_kg": change,
                })
                prev_weight = w.weight

            # LLM 生成报告文本
            report_text = ""
            if settings.anthropic_api_key or settings.openai_api_key:
                try:
                    llm = None
                    if settings.anthropic_api_key:
                        from langchain_anthropic import ChatAnthropic
                        from langchain_core.messages import HumanMessage
                        llm = ChatAnthropic(model="claude-sonnet-4-20250514", anthropic_api_key=settings.anthropic_api_key)  # type: ignore[call-arg]

                    if not llm and settings.openai_api_key:
                        from langchain_core.messages import HumanMessage
                        from langchain_openai import ChatOpenAI
                        llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=settings.openai_api_key)  # type: ignore[call-arg,assignment]

                    if llm:
                        summary_data = f"""宠物：{pet.name}（{pet.species.value}，{'已绝育' if pet.neutered_status.value == 'neutered' else '未绝育'}）
当前体重：{float(pet.current_weight) if pet.current_weight else '未知'}kg
报告周期：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}（{period_days}天）

饮食统计：
- 喂食次数：{meal_stats.total_meals or 0} 次
- 总投喂量：{float(meal_stats.total_food_g or 0):.0f}g
- 近期食物：{', '.join(m.food_name for m in recent_meals[:5])}

运动统计：
- 运动次数：{activity_stats.total_activities or 0} 次
- 总运动时长：{int(activity_stats.total_duration_min or 0)} 分钟

体重趋势：
{chr(10).join(f"  {w['date']}: {w['weight_kg']}kg ({'+' + str(w['change_kg']) if w['change_kg'] and float(w['change_kg']) > 0 else w['change_kg']})" for w in weight_trend[-5:]) if weight_trend else '  无记录'}

请基于以上数据，生成一份简洁的宠物健康报告。包括：
1. 总体健康评估（1-2句）
2. 饮食建议
3. 运动建议
4. 体重变化分析
5. 改善建议（如果有）"""

                        response = await llm.ainvoke([HumanMessage(content=summary_data)])
                        report_text = str(response.content)

                except Exception as llm_err:
                    logger.warning(f"LLM report generation failed, using template: {llm_err}")

            # Fallback：模板化报告
            if not report_text:
                weight_status = "稳定"
                if len(weight_trend) >= 2:
                    first_w = float(weight_trend[0]["weight_kg"])
                    last_w = float(weight_trend[-1]["weight_kg"])
                    diff = last_w - first_w
                    if abs(diff) > 0.3:
                        weight_status = f"{'增加' if diff > 0 else '减少'}了 {abs(diff):.1f}kg"

                report_text = f"""# {pet.name} 的健康报告

**报告周期：** {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}

## 总体评估
{pet.name} 在过去 {period_days} 天内状态{'良好' if (meal_stats.total_meals or 0) > 0 else '需要关注'}。

## 饮食情况
- 喂食次数：{meal_stats.total_meals or 0} 次
- 总投喂量：{float(meal_stats.total_food_g or 0):.0f}g
- 近期食物：{', '.join(m.food_name for m in recent_meals[:5]) if recent_meals else '无记录'}

## 运动情况
- 运动次数：{activity_stats.total_activities or 0} 次
- 总运动时长：{int(activity_stats.total_duration_min or 0)} 分钟

## 体重变化
- 体重趋势：{weight_status}
- 当前体重：{float(pet.current_weight) if pet.current_weight else '未知'}kg
- 最近测量：{weight_trend[-1] if weight_trend else '无记录'}

## 建议
请保持规律的喂食和适量运动，定期监测体重变化。"""

            logger.info(f"健康报告生成成功: pet_id={pet_id}, period={period_days}天")

            return {
                "success": True,
                "error": None,
                "data": {
                    "pet_id": str(pet_id),
                    "pet_name": pet.name,
                    "period_days": period_days,
                    "report_type": report_type,
                    "summary": {
                        "total_meals": meal_stats.total_meals or 0,
                        "total_food_grams": float(meal_stats.total_food_g or 0),
                        "total_activities": activity_stats.total_activities or 0,
                        "total_activity_minutes": int(activity_stats.total_duration_min or 0),
                        "weight_records": len(weight_records),
                    },
                    "weight_trend": weight_trend,
                    "report_text": report_text,
                    "generated_at": end_date.isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Generate health report failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Report generation failed: {str(e)}",
                "data": None,
            }


# ========== 获取所有工具 ==========

def get_all_tools() -> List[BaseTool]:
    """获取所有已注册的工具列表。"""
    return [
        # 宠物档案
        GetPetProfileTool(),
        CreatePetProfileTool(),
        UpdatePetProfileTool(),
        SwitchActivePetTool(),
        # 记录
        LogMealTool(),
        LogActivityTool(),
        LogWeightTool(),
        # 营养分析
        CalculateNutritionTool(),
        EvaluateDietTool(),
        GenerateRecipeTool(),
        # 多媒体
        RecognizeFoodImageTool(),
        TranscribeVoiceTool(),
        # 实用工具
        SearchNearbyHospitalTool(),
        WebSearchTool(),
        ScheduleReminderTool(),
        GenerateHealthReportTool(),
    ]


# 工具名称到实例的映射
TOOL_REGISTRY: Dict[str, BaseTool] = {
    tool.name: tool for tool in get_all_tools()
}
