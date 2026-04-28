"""手动创建数据库表（排除需要 pgvector 的 PetMemory）"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    engine = create_async_engine(
        "postgresql+asyncpg://pawlife:pawlife_dev@localhost:5432/pawlife",
        echo=True,
    )

    # 导入 Base 和需要的模型（不导入 memory.py）
    from models.base import Base
    from models.user import User, Family, FamilyMember
    from models.pet import Pet, VaccineRecord, DewormingRecord
    from models.log import MealLog, ActivityLog, WeightLog
    from models.reminder import Reminder
    from models.recipe import Recipe, RecipeIngredient
    from models.nutrition import FoodNutrition

    # 移除 PetMemory 的表（如果被 __init__.py 间接导入）
    if "pet_memories" in Base.metadata.tables:
        Base.metadata.remove(Base.metadata.tables["pet_memories"])

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 打印所有已创建的表
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        )
        tables = [r[0] for r in result.fetchall()]
        print(f"\n已创建 {len(tables)} 个表: {tables}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
