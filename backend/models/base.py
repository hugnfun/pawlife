"""
数据库模型基类模块。

提供所有模型共享的基类和混入类。
"""

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr
from sqlalchemy.dialects.postgresql import UUID


# 自定义类型注解
str_255 = Annotated[str, 255]
str_500 = Annotated[str, 500]
str_1000 = Annotated[str, 1000]


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。

    所有模型都继承自此基类。
    """

    # 表名约定：使用复数形式，下划线分隔
    @declared_attr.directive
    def __tablename__(cls) -> str:
        """自动生成表名。

        将类名转换为复数形式，下划线分隔。
        例如：User -> users, PetProfile -> pet_profiles
        """
        import re
        name = cls.__name__
        # 将 PascalCase 转换为 snake_case
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        # 添加复数形式（简单规则）
        if name.endswith('y'):
            name = name[:-1] + 'ies'
        elif name.endswith('s') or name.endswith('x') or name.endswith('z'):
            name = name + 'es'
        else:
            name = name + 's'
        return name


class TimeStampMixin:
    """时间戳混入类。

    为模型添加 created_at 和 updated_at 字段。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
        comment="更新时间",
    )


class UUIDMixin:
    """UUID 主键混入类。

    为模型添加 UUID 主键字段。
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="唯一标识",
    )