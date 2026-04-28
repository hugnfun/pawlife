"""
测试共享 fixtures。

提供测试数据库、HTTP 客户端、Mock Redis、认证头等。
"""

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import Text

from models.base import Base
from models.user import User, UserRole
from models.pet import Pet, PetSpecies, PetGender, NeuteredStatus


# 使用 SQLite 内存数据库替代 PostgreSQL
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """创建测试用异步引擎（SQLite 内存数据库）。

    在创建表之前，将 pgvector 和 JSONB 类型替换为 SQLite 兼容类型。
    """
    # 替换 pgvector.Vector 为 Text，JSONB 为 Text
    from pgvector.sqlalchemy import Vector
    from sqlalchemy.dialects.postgresql import JSONB
    from models.memory import PetMemory
    from models.audit import AuditLog

    # 保存原始类型以便恢复
    orig_embedding_type = PetMemory.__table__.c.embedding.type
    orig_detail_type = AuditLog.__table__.c.detail.type

    # 替换为 SQLite 兼容类型
    PetMemory.__table__.c.embedding.type = Text()
    AuditLog.__table__.c.detail.type = Text()

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

    # 恢复原始类型
    PetMemory.__table__.c.embedding.type = orig_embedding_type
    AuditLog.__table__.c.detail.type = orig_detail_type


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """提供测试数据库会话，每个测试用例独立事务。"""
    session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_app(test_engine):
    """创建测试用 FastAPI 应用，替换数据库和 Redis 依赖。"""
    from main import app
    from services.database import get_db
    from services.redis import redis_service, get_redis
    from core.config import settings

    # 临时切换到 testing 环境，避免开发模式 mock 用户
    orig_env = settings.environment
    settings.environment = "testing"

    session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_maker() as session:
            yield session

    # Mock RedisService
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.exists = AsyncMock(return_value=0)
    mock_redis.health_check = AsyncMock(return_value=True)
    mock_redis.dispose = AsyncMock()
    mock_redis.get_session_context = AsyncMock(return_value=None)
    mock_redis.set_session_context = AsyncMock(return_value=True)
    mock_redis.delete_session_context = AsyncMock(return_value=1)
    mock_redis.get_active_pet = AsyncMock(return_value=None)
    mock_redis.set_active_pet = AsyncMock(return_value=True)
    mock_redis.delete_active_pet = AsyncMock(return_value=1)
    mock_redis.check_duplicate_feeding = AsyncMock(return_value=False)
    mock_redis.get_session_history = AsyncMock(return_value=[])
    mock_redis.append_session_history = AsyncMock(return_value=True)
    mock_redis.clear_session_history = AsyncMock(return_value=1)

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with patch.object(redis_service, "health_check", new_callable=AsyncMock, return_value=True):
        yield app

    app.dependency_overrides.clear()
    settings.environment = orig_env  # 恢复原始环境


@pytest_asyncio.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """提供异步 HTTP 测试客户端。"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def sample_user(test_db: AsyncSession) -> User:
    """创建测试用户。"""
    user = User(
        id=uuid.uuid4(),
        wechat_openid=f"test_openid_{uuid.uuid4().hex[:8]}",
        nickname="测试用户",
        role=UserRole.USER,
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_pet(test_db: AsyncSession, sample_user: User) -> Pet:
    """创建测试宠物。"""
    pet = Pet(
        id=uuid.uuid4(),
        name="测试宠物",
        species=PetSpecies.DOG,
        breed="金毛",
        gender=PetGender.MALE,
        neutered_status=NeuteredStatus.NEUTERED,
        owner_id=sample_user.id,
    )
    test_db.add(pet)
    await test_db.commit()
    await test_db.refresh(pet)
    return pet


@pytest.fixture
def auth_headers(sample_user: User) -> dict:
    """提供带 JWT token 的认证头。"""
    from core.security import create_access_token
    token = create_access_token(subject=sample_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_redis():
    """提供 Mock Redis 实例。"""
    redis = MagicMock()
    redis._data = {}
    redis._expire = {}

    async def mock_get(key, default=None):
        val = redis._data.get(key)
        return val if val is not None else default

    async def mock_set(key, value, expire=None):
        redis._data[key] = value
        if expire:
            redis._expire[key] = expire
        return True

    async def mock_delete(*keys):
        count = 0
        for k in keys:
            if k in redis._data:
                del redis._data[k]
                count += 1
        return count

    async def mock_exists(*keys):
        return sum(1 for k in keys if k in redis._data)

    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock(side_effect=mock_set)
    redis.delete = AsyncMock(side_effect=mock_delete)
    redis.exists = AsyncMock(side_effect=mock_exists)
    redis.health_check = AsyncMock(return_value=True)
    redis.dispose = AsyncMock()
    return redis
