"""
数据库服务模块。

提供数据库连接、会话管理、事务处理等功能。
使用 SQLAlchemy 2.0 异步 API。
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings


class DatabaseService:
    """数据库服务类。

    管理数据库连接池和会话工厂。
    """

    def __init__(self) -> None:
        """初始化数据库服务。

        根据环境配置创建异步引擎和会话工厂。
        """
        # 创建异步引擎
        # 注意：异步引擎不支持 pool_class 参数，连接池由 asyncpg 管理
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,  # 连接前检查连接是否有效
        )

        # 创建异步会话工厂
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话的上下文管理器。

        Yields:
            AsyncSession: 异步数据库会话

        Example:
            async with db.get_session() as session:
                result = await session.execute(query)
                await session.commit()
        """
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def create_tables(self) -> None:
        """创建所有数据库表。

        只在开发环境或测试环境使用，生产环境使用 Alembic 迁移。
        """
        from models.base import Base
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """删除所有数据库表。

        只在测试环境使用。
        """
        from models.base import Base
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def health_check(self) -> bool:
        """数据库健康检查。

        Returns:
            bool: 数据库连接是否正常
        """
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def dispose(self) -> None:
        """释放数据库连接池。

        在应用关闭时调用。
        """
        await self.engine.dispose()


# 创建全局数据库服务实例
db = DatabaseService()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """依赖注入函数，用于 FastAPI 路由。

    Yields:
        AsyncSession: 异步数据库会话

    Example:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with db.get_session() as session:
        yield session
