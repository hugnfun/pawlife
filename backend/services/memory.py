"""
长期记忆服务（L3）。

使用 pgvector 存储向量化的宠物记忆片段，支持语义相似度检索。
"""

import logging
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select

from core.config import settings
from models.memory import PetMemory
from services.database import db

logger = logging.getLogger(__name__)


class MemoryService:
    """长期记忆服务。"""

    def __init__(self):
        pass

    async def search_relevant_memories(
        self,
        pet_id: UUID,
        query: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """语义相似度检索相关记忆。

        Args:
            pet_id: 宠物ID
            query: 查询文本（会被向量化）
            limit: 返回结果数量

        Returns:
            相关记忆列表，按相似度降序排列
        """
        from openai import AsyncOpenAI

        if settings.openai_api_key is None:
            logger.warning("OpenAI API key not configured, skip memory search")
            return []

        try:
            # 对查询文本进行向量化
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            embedding_response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=query,
            )
            query_embedding = embedding_response.data[0].embedding

            # 使用 pgvector 余弦相似度搜索
            async with db.get_session() as session:
                stmt = (
                    select(PetMemory)
                    .where(PetMemory.pet_id == pet_id)
                    .order_by(PetMemory.embedding.cosine_distance(query_embedding))
                    .limit(limit)
                )
                result = await session.execute(stmt)
                memories = result.scalars().all()

            # 转换为字典返回
            return [
                {
                    "id": str(mem.id),
                    "content": mem.content,
                    "source": mem.source,
                    "importance": mem.importance,
                }
                for mem in memories
            ]

        except Exception as e:
            logger.error(f"Search relevant memories failed: {e}", exc_info=True)
            return []

    async def add_memory(
        self,
        pet_id: UUID,
        content: str,
        source: str = "conversation",
        importance: int = 3,
    ) -> Dict[str, Any]:
        """添加新的长期记忆。

        Args:
            pet_id: 宠物ID
            content: 记忆内容
            source: 来源
            importance: 重要性 1-5

        Returns:
            创建结果
        """
        from uuid import uuid4

        from openai import AsyncOpenAI

        from models.memory import PetMemory

        if settings.openai_api_key is None:
            return {
                "success": False,
                "error": "OpenAI API key not configured",
                "data": None,
            }

        try:
            # 向量化
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            embedding_response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=content,
            )
            embedding = embedding_response.data[0].embedding

            # 保存到数据库
            async with db.get_session() as session:
                memory = PetMemory(
                    id=uuid4(),
                    pet_id=pet_id,
                    content=content,
                    embedding=embedding,
                    source=source,
                    importance=importance,
                )
                session.add(memory)
                await session.commit()

            logger.info(f"Added memory: pet_id={pet_id}, memory_id={memory.id}")

            return {
                "success": True,
                "error": None,
                "data": {
                    "id": str(memory.id),
                    "content": memory.content,
                },
            }

        except Exception as e:
            logger.error(f"Add memory failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": None,
            }


# 创建全局实例
memory_service = MemoryService()
