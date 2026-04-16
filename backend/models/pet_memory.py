"""
宠物记忆数据模型。

包含长期记忆向量存储，用于语义检索和AI上下文。
使用 pgvector 进行向量相似性搜索。
"""

import uuid
from typing import Optional
from sqlalchemy import ForeignKey, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from .base import Base, UUIDMixin, TimeStampMixin


class MemoryType:
    """记忆类型常量。"""
    CONVERSATION = "conversation"      # 对话记忆
    OBSERVATION = "observation"        # 行为观察
    HEALTH_EVENT = "health_event"      # 健康事件
    PREFERENCE = "preference"          # 偏好记录
    DIET_CHANGE = "diet_change"        # 饮食变化
    BEHAVIOR_PATTERN = "behavior_pattern"  # 行为模式


class PetMemory(Base, UUIDMixin, TimeStampMixin):
    """宠物长期记忆模型。

    使用 pgvector 存储文本向量化，支持语义检索。
    用于AI长期记忆和个性化对话。

    Attributes:
        pet_id: 宠物ID
        user_id: 创建用户ID
        memory_type: 记忆类型
        content: 原始文本内容
        embedding: 向量嵌入
        metadata: 额外元数据（JSON格式）
        importance: 重要性评分 (1-5)，用于检索优先级
        pet: 宠物关系
    """

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="创建用户ID",
    )

    memory_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="记忆类型",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="原始文本内容",
    )

    # pgvector 向量嵌入，默认使用 text-embedding-3-small 维度是 1536
    # 如果使用其他模型，维度可能不同
    embedding: Mapped[Optional[Vector[1536]]] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="向量嵌入",
    )

    meta_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="额外元数据 (JSON格式)",
    )

    importance: Mapped[int] = mapped_column(
        default=3,
        nullable=False,
        comment="重要性评分 (1-5)",
    )

    # 关系
    pet: Mapped["Pet"] = relationship()
    user: Mapped[Optional["User"]] = relationship()

    def __repr__(self) -> str:
        return f"<PetMemory(id={self.id}, pet_id={self.pet_id}, type={self.memory_type}, importance={self.importance})>"
