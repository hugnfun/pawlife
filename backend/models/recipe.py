"""
食谱数据模型。

包含个性化食谱、食谱成分等实体。
"""

import enum
import uuid
from typing import Optional, List
from decimal import Decimal
from sqlalchemy import ForeignKey, Enum, Numeric, Text, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimeStampMixin


class RecipeSource(enum.Enum):
    """食谱来源枚举。"""
    AI_GENERATED = "ai_generated"      # AI 生成
    USER_CUSTOM = "user_custom"        # 用户自定义
    RECOMMENDED = "recommended"        # 系统推荐
    IMPORTED = "imported"              # 导入


class RecipeType(enum.Enum):
    """食谱类型枚举。"""
    DAILY = "daily"                    # 日常食谱
    WEIGHT_LOSS = "weight_loss"        # 减重食谱
    WEIGHT_GAIN = "weight_gain"        # 增重食谱
    SPECIAL = "special"                # 特殊需求（疾病等）
    HOMEMADE = "homemade"              # 自制食谱


class Recipe(Base, UUIDMixin, TimeStampMixin):
    """个性化食谱模型。

    Attributes:
        pet_id: 宠物ID
        name: 食谱名称
        description: 食谱描述
        recipe_type: 食谱类型
        source: 食谱来源
        daily_calories_target: 目标每日热量 (kcal)
        is_active: 是否当前使用
        notes: AI 生成备注/建议
        ingredients: 食材成分列表
        pet: 宠物关系
    """

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="食谱名称",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="食谱描述",
    )

    recipe_type: Mapped[RecipeType] = mapped_column(
        Enum(RecipeType),
        default=RecipeType.DAILY,
        nullable=False,
        comment="食谱类型",
    )
    source: Mapped[RecipeSource] = mapped_column(
        Enum(RecipeSource),
        default=RecipeSource.AI_GENERATED,
        nullable=False,
        comment="食谱来源",
    )

    # 营养目标
    daily_calories_target: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="目标每日热量 (kcal)",
    )
    protein_target_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="蛋白质目标百分比",
    )
    fat_target_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="脂肪目标百分比",
    )
    carb_target_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="碳水目标百分比",
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="是否当前使用",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI 生成备注/建议",
    )

    # 关系
    pet: Mapped["Pet"] = relationship()
    ingredients: Mapped[List["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Recipe(id={self.id}, pet_id={self.pet_id}, name={self.name}, type={self.recipe_type})>"


class RecipeIngredient(Base, UUIDMixin, TimeStampMixin):
    """食谱食材成分模型。

    记录食谱中每种食材的分量和营养信息。
    """

    recipe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        comment="食谱ID",
    )

    food_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="食物名称",
    )
    brand: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="品牌",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(7, 2),
        nullable=False,
        comment="分量",
    )
    unit: Mapped[str] = mapped_column(
        String(20),
        default="g",
        nullable=False,
        comment="单位",
    )

    # 营养信息（每单位）
    calories_per_unit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="每单位热量 (kcal)",
    )
    protein_per_unit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="每单位蛋白质 (g)",
    )
    fat_per_unit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="每单位脂肪 (g)",
    )
    carb_per_unit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="每单位碳水 (g)",
    )

    is_allergy_risk: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否为过敏风险食材",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )

    # 关系
    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")

    @property
    def total_calories(self) -> Optional[Decimal]:
        """计算总热量。"""
        if self.calories_per_unit:
            return self.amount * self.calories_per_unit
        return None

    @property
    def total_protein(self) -> Optional[Decimal]:
        """计算总蛋白质。"""
        if self.protein_per_unit:
            return self.amount * self.protein_per_unit
        return None

    @property
    def total_fat(self) -> Optional[Decimal]:
        """计算总脂肪。"""
        if self.fat_per_unit:
            return self.amount * self.fat_per_unit
        return None

    @property
    def total_carb(self) -> Optional[Decimal]:
        """计算总碳水。"""
        if self.carb_per_unit:
            return self.amount * self.carb_per_unit
        return None

    def __repr__(self) -> str:
        return f"<RecipeIngredient(id={self.id}, recipe_id={self.recipe_id}, food={self.food_name}, amount={self.amount})>"
