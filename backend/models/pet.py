"""
宠物相关数据模型。

包含宠物档案、疫苗记录、驱虫记录等实体。
"""

import enum
import uuid
from typing import Optional, List
from datetime import date
from decimal import Decimal
from sqlalchemy import ForeignKey, Enum, Numeric, Text, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimeStampMixin


class PetSpecies(enum.Enum):
    """宠物物种枚举。"""
    DOG = "dog"
    CAT = "cat"
    BIRD = "bird"
    RABBIT = "rabbit"
    OTHER = "other"


class PetGender(enum.Enum):
    """宠物性别枚举。"""
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class NeuteredStatus(enum.Enum):
    """绝育状态枚举。"""
    NEUTERED = "neutered"      # 已绝育
    INTACT = "intact"          # 未绝育
    UNKNOWN = "unknown"        # 未知


class BodyConditionScore(enum.Enum):
    """体型评分枚举 (BCS 1-9)。"""
    BCS_1 = "1"   # 极瘦
    BCS_2 = "2"
    BCS_3 = "3"   # 瘦
    BCS_4 = "4"
    BCS_5 = "5"   # 理想
    BCS_6 = "6"
    BCS_7 = "7"   # 超重
    BCS_8 = "8"
    BCS_9 = "9"   # 肥胖


class Pet(Base, UUIDMixin, TimeStampMixin):
    """宠物档案模型。

    Attributes:
        name: 宠物名字
        species: 物种
        breed: 品种
        gender: 性别
        birth_date: 出生日期
        neutered_status: 绝育状态
        current_weight: 当前体重（kg）
        ideal_weight: 理想体重（kg）
        body_condition_score: 体型评分
        known_diseases: 已知疾病/过敏史
        long_term_medication: 长期用药
        main_food_brand: 主粮品牌
        allergy_blacklist: 过敏食材黑名单
        avatar_url: 宠物头像 URL
        is_active: 是否活跃
        owner_id: 拥有者用户ID
        family_id: 所属家庭ID
        owner: 拥有者关系
        family: 所属家庭关系
        meal_logs: 饮食记录关系
        activity_logs: 活动记录关系
        weight_logs: 体重记录关系
        vaccine_records: 疫苗记录关系
        deworming_records: 驱虫记录关系
    """

    # 基本信息
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="宠物名字",
    )
    species: Mapped[PetSpecies] = mapped_column(
        Enum(PetSpecies),
        nullable=False,
        comment="物种",
    )
    breed: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="品种",
    )
    gender: Mapped[PetGender] = mapped_column(
        Enum(PetGender),
        default=PetGender.UNKNOWN,
        nullable=False,
        comment="性别",
    )
    birth_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="出生日期",
    )
    neutered_status: Mapped[NeuteredStatus] = mapped_column(
        Enum(NeuteredStatus),
        default=NeuteredStatus.UNKNOWN,
        nullable=False,
        comment="绝育状态",
    )

    # 健康信息
    current_weight: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),  # 最大 999.99 kg
        nullable=True,
        comment="当前体重 (kg)",
    )
    ideal_weight: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="理想体重 (kg)",
    )
    body_condition_score: Mapped[Optional[BodyConditionScore]] = mapped_column(
        Enum(BodyConditionScore),
        nullable=True,
        comment="体型评分",
    )
    known_diseases: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="已知疾病/过敏史",
    )
    long_term_medication: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="长期用药",
    )

    # 喂养偏好
    main_food_brand: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="主粮品牌",
    )
    allergy_blacklist: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="过敏食材黑名单 (逗号分隔)",
    )

    # 媒体
    avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="宠物头像 URL",
    )

    # 状态
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="是否活跃",
    )

    # 外键
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="拥有者ID",
    )
    family_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("families.id", ondelete="SET NULL"),
        nullable=True,
        comment="家庭ID",
    )

    # 关系
    owner: Mapped["User"] = relationship(back_populates="pets")
    family: Mapped[Optional["Family"]] = relationship(back_populates="pets")
    meal_logs: Mapped[List["MealLog"]] = relationship(
        back_populates="pet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    activity_logs: Mapped[List["ActivityLog"]] = relationship(
        back_populates="pet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    weight_logs: Mapped[List["WeightLog"]] = relationship(
        back_populates="pet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    vaccine_records: Mapped[List["VaccineRecord"]] = relationship(
        back_populates="pet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    deworming_records: Mapped[List["DewormingRecord"]] = relationship(
        back_populates="pet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    memories: Mapped[List["PetMemory"]] = relationship(
        back_populates="pet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Pet(id={self.id}, name={self.name}, species={self.species})>"


class VaccineRecord(Base, UUIDMixin, TimeStampMixin):
    """疫苗记录模型。"""

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )
    vaccine_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="疫苗名称",
    )
    administered_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="接种日期",
    )
    next_due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="下次接种日期",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )

    # 关系
    pet: Mapped["Pet"] = relationship(back_populates="vaccine_records")

    def __repr__(self) -> str:
        return f"<VaccineRecord(id={self.id}, pet_id={self.pet_id}, vaccine={self.vaccine_name})>"


class DewormingRecord(Base, UUIDMixin, TimeStampMixin):
    """驱虫记录模型。"""

    class DewormingType(enum.Enum):
        INTERNAL = "internal"  # 体内驱虫
        EXTERNAL = "external"  # 体外驱虫
        BOTH = "both"          # 内外同驱

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )
    deworming_type: Mapped[DewormingType] = mapped_column(
        Enum(DewormingType),
        nullable=False,
        comment="驱虫类型",
    )
    product_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="产品名称",
    )
    administered_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="驱虫日期",
    )
    next_due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="下次驱虫日期",
    )
    cycle_days: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="驱虫周期 (天)",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )

    # 关系
    pet: Mapped["Pet"] = relationship(back_populates="deworming_records")

    def __repr__(self) -> str:
        return f"<DewormingRecord(id={self.id}, pet_id={self.pet_id}, type={self.deworming_type})>"