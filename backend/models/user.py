"""
用户相关数据模型。

包含用户、家庭组等实体。
"""

import enum
import uuid
from typing import Optional, List
from datetime import datetime
from sqlalchemy import ForeignKey, Enum, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimeStampMixin


class UserRole(enum.Enum):
    """用户角色枚举。"""
    ADMIN = "admin"  # 系统管理员
    USER = "user"    # 普通用户


class FamilyRole(enum.Enum):
    """家庭角色枚举。"""
    OWNER = "owner"       # 家庭创建者，有管理权限
    MEMBER = "member"     # 普通成员，可以查看和记录
    GUEST = "guest"       # 访客，只能查看


class User(Base, UUIDMixin, TimeStampMixin):
    """用户模型。

    Attributes:
        wechat_openid: 微信 openid，唯一标识
        wechat_unionid: 微信 unionid，跨应用唯一标识
        nickname: 微信昵称
        avatar_url: 微信头像 URL
        phone_number: 手机号（可选）
        role: 用户角色
        is_active: 是否激活
        last_login_at: 最后登录时间
        families: 所属家庭组关系
        pets: 创建的宠物关系
        meal_logs: 饮食记录关系
    """

    # 微信相关字段
    wechat_openid: Mapped[str] = mapped_column(
        String(255),  # 使用 String 而不是 str_255，因为 str_255 是注解
        unique=True,
        nullable=False,
        index=True,
        comment="微信 openid",
    )
    wechat_unionid: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
        comment="微信 unionid",
    )
    nickname: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="用户昵称",
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="头像 URL",
    )
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        comment="手机号",
    )

    # 状态字段
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False,
        comment="用户角色",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="是否激活",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        comment="最后登录时间",
    )

    # 关系
    families: Mapped[List["FamilyMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    pets: Mapped[List["Pet"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    meal_logs: Mapped[List["MealLog"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, openid={self.wechat_openid}, nickname={self.nickname})>"


class Family(Base, UUIDMixin, TimeStampMixin):
    """家庭组模型。

    Attributes:
        name: 家庭组名称
        invite_code: 邀请码（6位随机字符串）
        members: 家庭成员关系
        pets: 家庭宠物关系
    """

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="家庭组名称",
    )
    invite_code: Mapped[str] = mapped_column(
        String(6),
        unique=True,
        nullable=False,
        index=True,
        comment="邀请码",
    )

    # 关系
    members: Mapped[List["FamilyMember"]] = relationship(
        back_populates="family",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    pets: Mapped[List["Pet"]] = relationship(
        back_populates="family",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Family(id={self.id}, name={self.name}, invite_code={self.invite_code})>"


class FamilyMember(Base, TimeStampMixin):
    """家庭组成员关系模型。

    多对多关系，包含用户在家庭中的角色。
    """

    # 复合主键
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"),
        primary_key=True,
        comment="家庭ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="用户ID",
    )

    # 角色字段
    role: Mapped[FamilyRole] = mapped_column(
        Enum(FamilyRole),
        default=FamilyRole.MEMBER,
        nullable=False,
        comment="在家庭中的角色",
    )
    joined_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        comment="加入时间",
    )

    # 关系
    family: Mapped["Family"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="families")

    def __repr__(self) -> str:
        return f"<FamilyMember(family_id={self.family_id}, user_id={self.user_id}, role={self.role})>"