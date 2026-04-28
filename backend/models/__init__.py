"""
数据模型模块。

所有 SQLAlchemy ORM 模型都在此导出。
"""

from .base import Base, TimeStampMixin, UUIDMixin
from .user import User, Family, FamilyMember, UserRole, FamilyRole
from .pet import Pet, PetSpecies, PetGender, NeuteredStatus, BodyConditionScore, VaccineRecord, DewormingRecord
from .log import MealLog, ActivityLog, WeightLog
from .reminder import Reminder, ReminderType, RepeatType, ReminderStatus
from .recipe import Recipe, RecipeIngredient, RecipeType, RecipeSource
from .memory import PetMemory
from .nutrition import FoodNutrition
from .audit import AuditLog

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
