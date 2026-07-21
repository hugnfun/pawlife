"""
提醒数据模型。

包含提醒、定时任务等实体。
"""

import enum
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimeStampMixin, UUIDMixin

if TYPE_CHECKING:
    from .pet import Pet
    from .user import User


class ReminderType(enum.Enum):
    """提醒类型枚举。"""
    FEEDING = "feeding"          # 喂食提醒
    MEDICATION = "medication"    # 用药提醒
    DEWORMING = "deworming"      # 驱虫提醒
    VACCINE = "vaccine"          # 疫苗提醒
    WEIGHING = "weighing"        # 称重提醒
    BATH = "bath"                # 洗澡提醒
    NAIL_TRIM = "nail_trim"      # 剪指甲提醒
    OTHER = "other"              # 其他提醒


class RepeatType(enum.Enum):
    """重复类型枚举。"""
    NONE = "none"                # 不重复
    DAILY = "daily"              # 每天
    EVERY_X_DAYS = "every_x_days"  # 每X天
    WEEKLY = "weekly"            # 每周
    MONTHLY = "monthly"          # 每月
    YEARLY = "yearly"            # 每年


class ReminderStatus(enum.Enum):
    """提醒状态枚举。"""
    PENDING = "pending"          # 待处理
    SENT = "sent"                # 已发送
    COMPLETED = "completed"      # 已完成
    SKIPPED = "skipped"          # 已跳过
    CANCELLED = "cancelled"      # 已取消


class Reminder(Base, UUIDMixin, TimeStampMixin):
    """提醒模型。

    Attributes:
        pet_id: 宠物ID
        user_id: 创建用户ID
        reminder_type: 提醒类型
        title: 提醒标题
        description: 提醒描述
        status: 提醒状态
        remind_at: 提醒时间
        repeat_type: 重复类型
        repeat_interval: 重复间隔（天数）
        last_reminded_at: 上次提醒时间
        next_remind_at: 下次提醒时间
        is_active: 是否激活
        notes: 备注
        pet: 宠物关系
        user: 用户关系
    """

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建用户ID",
    )

    reminder_type: Mapped[ReminderType] = mapped_column(
        Enum(ReminderType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        comment="提醒类型",
    )
    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="提醒标题",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="提醒描述",
    )

    # 提醒时间
    remind_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="提醒时间",
    )

    # 重复设置
    repeat_type: Mapped[RepeatType] = mapped_column(
        Enum(RepeatType, values_callable=lambda x: [e.value for e in x]),
        default=RepeatType.NONE,
        nullable=False,
        comment="重复类型",
    )
    repeat_interval: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="重复间隔天数",
    )

    # 状态跟踪
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, values_callable=lambda x: [e.value for e in x]),
        default=ReminderStatus.PENDING,
        nullable=False,
        comment="提醒状态",
    )
    last_reminded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="上次提醒时间",
    )
    next_remind_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="下次提醒时间",
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="是否激活",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )

    # 关系
    pet: Mapped["Pet"] = relationship()
    user: Mapped["User"] = relationship()

    def calculate_next_remind(self) -> Optional[datetime]:
        """计算下次提醒时间。

        根据重复类型计算下次提醒时间。
        """
        if self.repeat_type == RepeatType.NONE:
            return None

        base_time = self.remind_at if self.next_remind_at is None else self.next_remind_at

        if self.repeat_type == RepeatType.DAILY:
            return base_time + timedelta(days=1)
        elif self.repeat_type == RepeatType.EVERY_X_DAYS and self.repeat_interval:
            return base_time + timedelta(days=self.repeat_interval)
        elif self.repeat_type == RepeatType.WEEKLY:
            return base_time + timedelta(weeks=1)
        elif self.repeat_type == RepeatType.MONTHLY:
            # 简单处理，加30天
            return base_time + timedelta(days=30)
        elif self.repeat_type == RepeatType.YEARLY:
            # 简单处理，加365天
            return base_time + timedelta(days=365)

        return None

    def __repr__(self) -> str:
        return f"<Reminder(id={self.id}, pet_id={self.pet_id}, type={self.reminder_type}, status={self.status})>"
