"""
日志记录数据模型。

包含饮食记录、活动记录、体重记录等时间序列数据。
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimeStampMixin, UUIDMixin

if TYPE_CHECKING:
    from .pet import Pet
    from .user import User


class MealLog(Base, UUIDMixin, TimeStampMixin):
    """饮食记录模型。

    Attributes:
        pet_id: 宠物ID
        user_id: 记录用户ID
        food_name: 食物名称
        food_type: 食物类型 (主粮/零食/辅食等)
        amount: 分量 (g)
        unit: 单位 (g/ml/个等)
        meal_time: 喂食时间
        notes: 备注
        photo_url: 照片URL
        is_duplicate: 是否重复喂食标记
        duplicate_of: 重复的记录ID
        pet: 宠物关系
        user: 用户关系
    """

    class FoodType(enum.Enum):
        MAIN = "main"      # 主粮
        TREAT = "treat"    # 零食
        SUPPLEMENT = "supplement"  # 辅食/补充剂
        OTHER = "other"    # 其他

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="记录用户ID",
    )
    food_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="食物名称",
    )
    food_type: Mapped[FoodType] = mapped_column(
        Enum(FoodType),
        default=FoodType.MAIN,
        nullable=False,
        comment="食物类型",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(7, 2),  # 最大 99999.99 g
        nullable=False,
        comment="分量",
    )
    unit: Mapped[str] = mapped_column(
        String(20),
        default="g",
        nullable=False,
        comment="单位",
    )
    meal_time: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="喂食时间",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )
    photo_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="照片URL",
    )

    # 重复喂食检测相关字段
    is_duplicate: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否重复喂食",
    )
    duplicate_of: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("meal_logs.id", ondelete="SET NULL"),
        nullable=True,
        comment="重复的记录ID",
    )

    # 关系
    pet: Mapped["Pet"] = relationship(back_populates="meal_logs")
    user: Mapped["User"] = relationship(back_populates="meal_logs")
    duplicate_record: Mapped[Optional["MealLog"]] = relationship(
        foreign_keys=[duplicate_of],
        remote_side="MealLog.id",
        post_update=True,
    )

    def __repr__(self) -> str:
        return f"<MealLog(id={self.id}, pet_id={self.pet_id}, food={self.food_name}, amount={self.amount})>"


class ActivityLog(Base, UUIDMixin, TimeStampMixin):
    """活动记录模型。"""

    class ActivityType(enum.Enum):
        WALK = "walk"          # 散步
        RUN = "run"            # 跑步
        PLAY = "play"          # 玩耍
        SWIM = "swim"          # 游泳
        TRAINING = "training"  # 训练
        OTHER = "other"        # 其他

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="记录用户ID",
    )
    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType),
        nullable=False,
        comment="活动类型",
    )
    duration_minutes: Mapped[int] = mapped_column(
        nullable=False,
        comment="持续时间 (分钟)",
    )
    activity_time: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="活动时间",
    )
    intensity: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="强度 (低/中/高)",
    )
    calories_estimated: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(7, 2),
        nullable=True,
        comment="预估消耗卡路里",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )

    # 关系
    pet: Mapped["Pet"] = relationship(back_populates="activity_logs")
    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<ActivityLog(id={self.id}, pet_id={self.pet_id}, type={self.activity_type}, duration={self.duration_minutes})>"


class WeightLog(Base, UUIDMixin, TimeStampMixin):
    """体重记录模型。"""

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="记录用户ID",
    )
    weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),  # 最大 999.99 kg
        nullable=False,
        comment="体重 (kg)",
    )
    measurement_time: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="测量时间",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )
    photo_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="照片URL",
    )

    # 关系
    pet: Mapped["Pet"] = relationship(back_populates="weight_logs")
    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<WeightLog(id={self.id}, pet_id={self.pet_id}, weight={self.weight})>"
