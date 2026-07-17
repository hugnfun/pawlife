"""
数据模型模块。

所有 SQLAlchemy ORM 模型都在此导出。
"""

from .audit import AuditLog
from .base import Base, TimeStampMixin, UUIDMixin
from .log import ActivityLog, MealLog, WeightLog
from .memory import PetMemory
from .nutrition import FoodNutrition
from .pet import (
    BodyConditionScore,
    DewormingRecord,
    NeuteredStatus,
    Pet,
    PetGender,
    PetSpecies,
    VaccineRecord,
)
from .recipe import Recipe, RecipeIngredient, RecipeSource, RecipeType
from .reminder import Reminder, ReminderStatus, ReminderType, RepeatType
from .user import Family, FamilyMember, FamilyRole, User, UserRole

__all__ = [
    # 基类
    "Base",
    "TimeStampMixin",
    "UUIDMixin",

    # 用户和家庭
    "User",
    "Family",
    "FamilyMember",
    "UserRole",
    "FamilyRole",

    # 宠物
    "Pet",
    "PetSpecies",
    "PetGender",
    "NeuteredStatus",
    "BodyConditionScore",
    "VaccineRecord",
    "DewormingRecord",

    # 日志记录
    "MealLog",
    "ActivityLog",
    "WeightLog",

    # 提醒
    "Reminder",
    "ReminderType",
    "RepeatType",
    "ReminderStatus",

    # 食谱
    "Recipe",
    "RecipeIngredient",
    "RecipeType",
    "RecipeSource",

    # 宠物记忆
    "PetMemory",

    # 营养数据库
    "FoodNutrition",

    # 审计日志
    "AuditLog",
]
