"""
添加测试长期记忆数据脚本。

手动创建几条测试记忆用于验证语义搜索功能。
使用方法:
    python -m scripts.add_test_memories --pet-id <UUID>
"""

import asyncio
import argparse
from uuid import UUID

from core.config import settings
from services.database import db
from services.memory import memory_service


async def add_test_memories(pet_id: UUID):
    """添加测试记忆。"""

    test_memories = [
        {
            "content": "豆豆对鸡肉过敏，不能吃任何含鸡肉的食物",
            "source": "manual",
            "importance": 5,
        },
        {
            "content": "豆豆喜欢啃骨头，每周给它啃一次磨牙骨",
            "source": "conversation",
            "importance": 3,
        },
        {
            "content": "豆豆去年得过肠胃炎，恢复后肠胃比较敏感，需要注意饮食清淡",
            "source": "health_record",
            "importance": 5,
        },
        {
            "content": "豆豆体重最近在减肥，每日总热量控制在 600大卡以内",
            "source": "manual",
            "importance": 4,
        },
        {
            "content": "豆豆喜欢晚饭后散步 30 分钟",
            "source": "conversation",
            "importance": 2,
        },
    ]

    for mem in test_memories:
        result = await memory_service.add_memory(
            pet_id=pet_id,
            content=mem["content"],
            source=mem["source"],
            importance=mem["importance"],
        )
        if result["success"]:
            print(f"✓ Added: {mem['content'][:40]}...")
        else:
            print(f"✗ Failed: {result['error']}")

    print(f"\nDone! Added {len(test_memories)} test memories")


async def main():
    parser = argparse.ArgumentParser(description="Add test memories for a pet")
    parser.add_argument("--pet-id", required=True, help="Pet UUID")
    args = parser.parse_args()

    pet_id = UUID(args.pet_id)
    await add_test_memories(pet_id)


if __name__ == "__main__":
    asyncio.run(main())
