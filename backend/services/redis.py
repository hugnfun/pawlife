"""
Redis 服务模块。

提供 Redis 连接池管理、会话上下文存储、缓存操作等功能。
"""

import json
from typing import Any, Optional, Union, Dict, List
from contextlib import asynccontextmanager
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool

from core.config import settings


class RedisService:
    """Redis 服务类。

    管理 Redis 连接池和提供常用操作方法。
    """

    def __init__(self) -> None:
        """初始化 Redis 服务。

        创建 Redis 连接池。
        """
        # 创建连接池
        self.pool: ConnectionPool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            decode_responses=False,  # 原始字节数据，需要自己解码
        )

    @property
    def client(self) -> Redis:
        """获取 Redis 客户端。

        Returns:
            Redis: Redis 异步客户端
        """
        return redis.Redis(connection_pool=self.pool)

    @asynccontextmanager
    async def get_client(self) -> Redis:
        """获取 Redis 客户端的上下文管理器。

        Yields:
            Redis: Redis 异步客户端

        Example:
            async with redis_service.get_client() as client:
                await client.set("key", "value")
        """
        client = self.client
        try:
            yield client
        finally:
            await client.aclose()

    # 基础操作方法
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """设置键值对。

        Args:
            key: 键名
            value: 值（支持任意可序列化类型）
            expire: 过期时间（秒或 timedelta 对象）

        Returns:
            bool: 是否设置成功
        """
        async with self.get_client() as client:
            # 序列化值 (JSON 安全)
            serialized = json.dumps(value).encode('utf-8')
            if expire:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                return await client.setex(key, expire, serialized)
            else:
                return await client.set(key, serialized)

    async def get(self, key: str, default: Any = None) -> Any:
        """获取键值。

        Args:
            key: 键名
            default: 默认值（当键不存在时返回）

        Returns:
            Any: 反序列化后的值或默认值
        """
        async with self.get_client() as client:
            value = await client.get(key)
            if value is None:
                return default
            try:
                return json.loads(value.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 如果解码失败，尝试直接返回字符串
                try:
                    return value.decode("utf-8")
                except UnicodeDecodeError:
                    return value

    async def delete(self, *keys: str) -> int:
        """删除一个或多个键。

        Args:
            *keys: 要删除的键名

        Returns:
            int: 成功删除的键数量
        """
        async with self.get_client() as client:
            return await client.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """检查一个或多个键是否存在。

        Args:
            *keys: 要检查的键名

        Returns:
            int: 存在的键数量
        """
        async with self.get_client() as client:
            return await client.exists(*keys)

    async def expire(self, key: str, time: Union[int, timedelta]) -> bool:
        """设置键的过期时间。

        Args:
            key: 键名
            time: 过期时间（秒或 timedelta 对象）

        Returns:
            bool: 是否设置成功
        """
        async with self.get_client() as client:
            if isinstance(time, timedelta):
                time = int(time.total_seconds())
            return await client.expire(key, time)

    async def ttl(self, key: str) -> int:
        """获取键的剩余生存时间。

        Args:
            key: 键名

        Returns:
            int: 剩余生存时间（秒），-1 表示永不过期，-2 表示键不存在
        """
        async with self.get_client() as client:
            return await client.ttl(key)

    # 会话上下文管理
    async def set_session_context(
        self,
        session_id: str,
        context: Dict[str, Any],
        expire: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """设置会话上下文。

        Args:
            session_id: 会话ID
            context: 上下文数据
            expire: 过期时间（默认 30 分钟）

        Returns:
            bool: 是否设置成功
        """
        if expire is None:
            expire = timedelta(minutes=30)
        key = f"session:{session_id}"
        return await self.set(key, context, expire)

    async def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话上下文。

        Args:
            session_id: 会话ID

        Returns:
            Optional[Dict[str, Any]]: 上下文数据，不存在则返回 None
        """
        key = f"session:{session_id}"
        return await self.get(key)

    async def delete_session_context(self, session_id: str) -> int:
        """删除会话上下文。

        Args:
            session_id: 会话ID

        Returns:
            int: 成功删除的数量
        """
        key = f"session:{session_id}"
        return await self.delete(key)

    # 宠物活跃上下文管理
    async def set_active_pet(
        self,
        user_id: str,
        pet_id: str,
        expire: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """设置用户的活跃宠物。

        Args:
            user_id: 用户ID
            pet_id: 宠物ID
            expire: 过期时间（默认 24 小时）

        Returns:
            bool: 是否设置成功
        """
        if expire is None:
            expire = timedelta(hours=24)
        key = f"active_pet:{user_id}"
        return await self.set(key, pet_id, expire)

    async def get_active_pet(self, user_id: str) -> Optional[str]:
        """获取用户的活跃宠物。

        Args:
            user_id: 用户ID

        Returns:
            Optional[str]: 宠物ID，不存在则返回 None
        """
        key = f"active_pet:{user_id}"
        return await self.get(key)

    async def delete_active_pet(self, user_id: str) -> int:
        """删除用户的活跃宠物记录。

        Args:
            user_id: 用户ID

        Returns:
            int: 成功删除的数量
        """
        key = f"active_pet:{user_id}"
        return await self.delete(key)

    # 重复喂食检测
    async def check_duplicate_feeding(
        self,
        pet_id: str,
        timestamp: int,
        window_seconds: int = 7200,  # 2小时
    ) -> bool:
        """检查是否重复喂食。

        Args:
            pet_id: 宠物ID
            timestamp: 时间戳（秒）
            window_seconds: 检测窗口（秒）

        Returns:
            bool: 是否在窗口期内有喂食记录
        """
        key = f"feeding:{pet_id}"
        last_feeding = await self.get(key)
        if last_feeding is None:
            # 记录本次喂食时间
            await self.set(key, timestamp, expire=window_seconds)
            return False
        if timestamp - last_feeding < window_seconds:
            return True
        # 更新最后一次喂食时间
        await self.set(key, timestamp, expire=window_seconds)
        return False

    # ========== L1 工作记忆：会话对话历史 ==========
    async def get_session_history(
        self,
        session_id: str,
        max_messages: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取会话历史（L1 工作记忆）。

        Args:
            session_id: 会话ID
            max_messages: 保留最大消息条数

        Returns:
            消息列表，每个元素包含 role 和 content
        """
        key = f"session:{session_id}:history"
        history = await self.get(key, default=[])
        # 只返回最近 max_messages 条
        if len(history) > max_messages:
            history = history[-max_messages:]
        return history

    async def append_session_history(
        self,
        session_id: str,
        role: str,
        content: str,
        ttl_seconds: int = 7200,  # 2小时
    ) -> bool:
        """追加消息到会话历史（L1 工作记忆）。

        Args:
            session_id: 会话ID
            role: 角色 (user/assistant)
            content: 内容
            ttl_seconds: 过期时间（秒）

        Returns:
            是否设置成功
        """
        key = f"session:{session_id}:history"
        history = await self.get(key, default=[])
        history.append({
            "role": role,
            "content": content,
            "timestamp": int(__import__('time').time()),
        })
        return await self.set(key, history, expire=ttl_seconds)

    async def clear_session_history(
        self,
        session_id: str,
    ) -> int:
        """清空会话历史。

        Args:
            session_id: 会话ID

        Returns:
            删除的键数量
        """
        key = f"session:{session_id}:history"
        return await self.delete(key)

    # 健康检查
    async def health_check(self) -> bool:
        """Redis 健康检查。

        Returns:
            bool: Redis 连接是否正常
        """
        try:
            async with self.get_client() as client:
                await client.ping()
            return True
        except Exception:
            return False

    async def dispose(self) -> None:
        """释放 Redis 连接池。

        在应用关闭时调用。
        """
        await self.pool.disconnect()


# 创建全局 Redis 服务实例
redis_service = RedisService()


async def get_redis() -> RedisService:
    """依赖注入函数，用于 FastAPI 路由。

    Returns:
        RedisService: Redis 服务实例
    """
    return redis_service