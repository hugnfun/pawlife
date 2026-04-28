"""
通用营养数据库模型。

存储常见食材的基础营养数据（每100克可食部分）。
数据来源于 USDA FoodData Central。
"""

from typing import Optional
from decimal import Decimal
from sqlalchemy import String, Numeric, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimeStampMixin


class FoodNutrition(Base, UUIDMixin, TimeStampMixin):
    """通用食材营养数据模型。

    存储常见食材每100克可食部分的营养成分。
    数据来源于 USDA FoodData Central 开放 API。

    Attributes:
        food_name: 食材中文名称
        food_name_en: 食材英文名称
        food_category: 食材分类（肉类/谷物/蔬菜/内脏等）
        is_common: 是否为常见食材（前端快速选择使用）
        is_pet_safe: 是否对宠物安全
        calories: 热量 (kcal / 100g)
        protein: 蛋白质 (g / 100g)
        fat: 脂肪 (g / 100g)
        carbs: 碳水化合物 (g / 100g)
        fiber: 膳食纤维 (g / 100g)
        ash: 灰分 (g / 100g)
        calcium: 钙 (mg / 100g)
        phosphorus: 磷 (mg / 100g)
        omega3: ω-3 脂肪酸 (g / 100g)
        omega6: ω-6 脂肪酸 (g / 100g)
        water: 水分 (g / 100g)
        usda_fdc_id: USDA FoodData Central 的食品 ID
        notes: 备注信息
    """

    # 基本信息
    food_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="食材中文名称",
    )
    food_name_en: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="食材英文名称",
    )
    food_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="食材分类",
    )

    # 标记
    is_common: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="是否为常见食材（前端快速选择）",
    )
    is_pet_safe: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="是否对宠物安全",
    )

    # 宏量营养素（每100g可食部分）
    calories: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="热量 (kcal / 100g)",
    )
    protein: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="蛋白质 (g / 100g)",
    )
    fat: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="脂肪 (g / 100g)",
    )
    carbs: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="碳水化合物 (g / 100g)",
    )
    fiber: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="膳食纤维 (g / 100g)",
    )
    ash: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="灰分 (g / 100g)",
    )

    # 矿物质
    calcium: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="钙 (mg / 100g)",
    )
    phosphorus: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="磷 (mg / 100g)",
    )

    # 脂肪酸
    omega3: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="ω-3 脂肪酸 (g / 100g)",
    )
    omega6: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="ω-6 脂肪酸 (g / 100g)",
    )

    # 水分
    water: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="水分 (g / 100g)",
    )

    # 来源信息
    usda_fdc_id: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="USDA FoodData Central 食品ID",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注信息",
    )

    def __repr__(self) -> str:
        return f"<FoodNutrition(id={self.id}, food_name={self.food_name}, calories={self.calories})>"

    def calculate_for_amount(self, amount_grams: float) -> dict[str, Optional[float]]:
        """根据给定分量（克）计算营养成分。

        Args:
            amount_grams: 食物重量（克）

        Returns:
            计算后的营养成分字典
        """
        factor = float(amount_grams) / 100.0

        def scale(val: Optional[Decimal]) -> Optional[float]:
            if val is None:
                return None
            return round(float(val) * factor, 2)

        return {
            "calories": scale(self.calories),
            "protein": scale(self.protein),
            "fat": scale(self.fat),
            "carbs": scale(self.carbs),
            "fiber": scale(self.fiber),
            "ash": scale(self.ash),
            "calcium": scale(self.calcium),
            "phosphorus": scale(self.phosphorus),
            "omega3": scale(self.omega3),
            "omega6": scale(self.omega6),
            "water": scale(self.water),
        }
