"""
测试共享 fixtures。

提供测试数据库、HTTP 客户端、Mock Redis、认证头等。
"""

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models.base import Base
from models.pet import NeuteredStatus, Pet, PetGender, PetSpecies
from models.user import User, UserRole

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
    from models.audit import AuditLog
    from models.memory import PetMemory

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
    from core.config import settings
    from main import app
    from services.database import get_db
    from services.redis import get_redis, redis_service

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
    # 日志缓存方法（Cache-Aside）
    mock_redis.get_log_cache = AsyncMock(return_value=None)  # 默认缓存未命中
    mock_redis.set_log_cache = AsyncMock(return_value=True)
    mock_redis.invalidate_log_cache = AsyncMock(return_value=0)
    mock_redis._build_log_cache_key = MagicMock(return_value="cache:test:key")
    # Round 2：宠物权限校验缓存（默认未命中，走 DB）
    mock_redis.get_pet_permission_cached = AsyncMock(return_value=None)
    mock_redis.set_pet_permission_cached = AsyncMock(return_value=True)
    mock_redis.invalidate_pet_permission_cached = AsyncMock(return_value=0)
    # Round 3：日志草稿（双通道输入 §2）—— 用内存字典模拟 Redis，让集成测试可以走完 confirm 路径
    _draft_store: dict = {}

    async def _save_draft(draft_id, data):
        _draft_store[draft_id] = data
        return True

    async def _get_draft(draft_id):
        return _draft_store.get(draft_id)

    async def _delete_draft(draft_id):
        return 1 if _draft_store.pop(draft_id, None) is not None else 0

    mock_redis.save_log_draft = AsyncMock(side_effect=_save_draft)
    mock_redis.get_log_draft = AsyncMock(side_effect=_get_draft)
    mock_redis.delete_log_draft = AsyncMock(side_effect=_delete_draft)
    # 缓存常量
    mock_redis.CACHE_PREFIX_MEAL_LOGS = "cache:meal_logs"
    mock_redis.CACHE_PREFIX_WEIGHT_LOGS = "cache:weight_logs"
    mock_redis.CACHE_PREFIX_ACTIVITY_LOGS = "cache:activity_logs"
    mock_redis.CACHE_PREFIX_PET_PERMISSION = "cache:pet_perm"
    mock_redis.CACHE_NULL_SENTINEL = "__NULL__"
    mock_redis.CACHE_TTL_NORMAL = 300
    mock_redis.CACHE_TTL_NULL = 60
    mock_redis.CACHE_TTL_PERMISSION = 30
    # Round 3：日志草稿常量
    mock_redis.LOG_DRAFT_PREFIX = "cache:log_draft"
    mock_redis.LOG_DRAFT_TTL = 900

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

    # 日志缓存方法（基于 _data 实现，可用于集成测试）
    from services.redis import RedisService

    def _build_key(prefix, pet_id, **kwargs):
        parts = [prefix, pet_id]
        for k in sorted(kwargs.keys()):
            v = kwargs[k]
            if v is not None:
                parts.append(f"{k}={v}")
        return ":".join(parts)

    async def mock_get_log_cache(prefix, pet_id, **kwargs):
        key = _build_key(prefix, pet_id, **kwargs)
        return redis._data.get(key)

    async def mock_set_log_cache(prefix, pet_id, data, **kwargs):
        key = _build_key(prefix, pet_id, **kwargs)
        if data is None or (isinstance(data, dict) and data.get("total", 1) == 0):
            redis._data[key] = RedisService.CACHE_NULL_SENTINEL
            redis._expire[key] = RedisService.CACHE_TTL_NULL
        else:
            redis._data[key] = data
            redis._expire[key] = RedisService.CACHE_TTL_NORMAL
        return True

    async def mock_invalidate_log_cache(pet_id, prefix=None):
        prefixes = [prefix] if prefix else [
            RedisService.CACHE_PREFIX_MEAL_LOGS,
            RedisService.CACHE_PREFIX_WEIGHT_LOGS,
        ]
        deleted = 0
        keys_to_delete = []
        for p in prefixes:
            pattern_prefix = f"{p}:{pet_id}:"
            for k in redis._data:
                if k.startswith(pattern_prefix):
                    keys_to_delete.append(k)
        for k in keys_to_delete:
            del redis._data[k]
            redis._expire.pop(k, None)
            deleted += 1
        return deleted

    redis.get_log_cache = AsyncMock(side_effect=mock_get_log_cache)
    redis.set_log_cache = AsyncMock(side_effect=mock_set_log_cache)
    redis.invalidate_log_cache = AsyncMock(side_effect=mock_invalidate_log_cache)
    redis._build_log_cache_key = MagicMock(side_effect=_build_key)
    # 避免 MagicMock 自动生成的 async 属性在 GC 时触发 "coroutine never awaited" warning
    redis._cancel = MagicMock()
    redis.CACHE_PREFIX_MEAL_LOGS = RedisService.CACHE_PREFIX_MEAL_LOGS
    redis.CACHE_PREFIX_WEIGHT_LOGS = RedisService.CACHE_PREFIX_WEIGHT_LOGS
    redis.CACHE_NULL_SENTINEL = RedisService.CACHE_NULL_SENTINEL
    redis.CACHE_TTL_NORMAL = RedisService.CACHE_TTL_NORMAL
    redis.CACHE_TTL_NULL = RedisService.CACHE_TTL_NULL

    return redis
