"""
宠物长期记忆数据模型。

使用 pgvector 存储向量化的记忆片段，支持语义相似度检索。
"""

import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from .base import Base, UUIDMixin, TimeStampMixin


class PetMemory(Base, UUIDMixin, TimeStampMixin):
    """宠物长期记忆模型。

    存储宠物相关的重要信息片段，向量化后支持语义检索。
    每次对话中根据用户问题检索最相关的记忆注入上下文。

    Attributes:
        pet_id: 宠物ID
        content: 记忆内容文本
        embedding: 向量化表示（1536 维，text-embedding-3-small）
        source: 记忆来源（conversation / manual / health_record）
        importance: 重要性评分 1-5，高重要性会优先检索
        metadata: 额外元数据（JSON 格式）
    """

    pet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        comment="宠物ID",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="记忆内容文本",
    )
    embedding: Mapped[Vector] = mapped_column(
        Vector(1536),  # text-embedding-3-small 输出是 1536 维
        nullable=False,
        comment="向量化表示",
    )
    source: Mapped[str] = mapped_column(
        String(20),
        default="conversation",
        nullable=False,
        comment="记忆来源: conversation / manual / health_record",
    )
    importance: Mapped[int] = mapped_column(
        default=3,
        nullable=False,
        comment="重要性评分 1-5",
    )

    # 关系
    pet: Mapped["Pet"] = relationship(back_populates="memories")
