"""
Redis 服务测试。

使用 MockRedis 测试业务逻辑。
"""

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_session_context(mock_redis):
    """测试会话上下文读写。"""
    # 设置会话
    await mock_redis.set("session:test_123", {"user_id": "u1", "openid": "o1"})
    # 读取会话
    result = await mock_redis.get("session:test_123")
    assert result == {"user_id": "u1", "openid": "o1"}
    # 删除会话
    count = await mock_redis.delete("session:test_123")
    assert count == 1
    # 验证删除
    result = await mock_redis.get("session:test_123")
    assert result is None


@pytest.mark.asyncio
async def test_active_pet(mock_redis):
    """测试活跃宠物管理。"""
    # 设置活跃宠物
    await mock_redis.set("active_pet:user_1", "pet_abc")
    # 读取
    result = await mock_redis.get("active_pet:user_1")
    assert result == "pet_abc"
    # 切换宠物
    await mock_redis.set("active_pet:user_1", "pet_xyz")
    result = await mock_redis.get("active_pet:user_1")
    assert result == "pet_xyz"


@pytest.mark.asyncio
async def test_duplicate_feeding_detection(mock_redis):
    """测试重复喂食检测逻辑。"""
    pet_id = "pet_1"
    # 第一次喂食
    key = f"last_feeding:{pet_id}"
    await mock_redis.set(key, "2024-01-01T08:00:00")
    # 检查是否近期喂食过
    last_feeding = await mock_redis.get(key)
    assert last_feeding is not None
    # 更新喂食时间
    await mock_redis.set(key, "2024-01-01T12:00:00")
    result = await mock_redis.get(key)
    assert result == "2024-01-01T12:00:00"


@pytest.mark.asyncio
async def test_session_history(mock_redis):
    """测试对话历史读写。"""
    # 添加对话历史
    history_key = "history:session_1"
    await mock_redis.set(history_key, [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
    ])
    # 读取
    result = await mock_redis.get(history_key)
    assert len(result) == 2
    assert result[0]["role"] == "user"


@pytest.mark.asyncio
async def test_exists_and_ttl(mock_redis):
    """测试键存在检查。"""
    await mock_redis.set("key1", "value1")
    # 存在
    count = await mock_redis.exists("key1")
    assert count == 1
    # 不存在
    count = await mock_redis.exists("nonexistent")
    assert count == 0


@pytest.mark.asyncio
async def test_delete_multiple(mock_redis):
    """测试批量删除。"""
    await mock_redis.set("k1", "v1")
    await mock_redis.set("k2", "v2")
    await mock_redis.set("k3", "v3")
    count = await mock_redis.delete("k1", "k2", "k4")
    assert count == 2  # k4 不存在
