#!/usr/bin/env python3
"""
预置常见宠物食材营养数据脚本。

如果没有 USDA API key，可以使用这个脚本直接导入预先整理好的
12种常见宠物食材营养数据（来源于 USDA FoodData Central）。

数据是每100克可食部分的营养成分。
"""

import asyncio
import logging
from typing import Optional
from decimal import Decimal

from models.nutrition import FoodNutrition
from services.database import db

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 预先整理好的营养数据 (每100g可食部)
# 数据来源: USDA FoodData Central
PRESET_DATA = [
    {
        "food_name": "鸡胸肉",
        "food_name_en": "chicken breast, raw",
        "food_category": "meat",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 171058,
        "calories": 165,
        "protein": 31.0,
        "fat": 3.6,
        "carbs": 0.0,
        "fiber": 0.0,
        "ash": 1.2,
        "calcium": 5,
        "phosphorus": 214,
        "omega3": 0.03,
        "omega6": 0.32,
        "water": 65.0,
    },
    {
        "food_name": "鸡腿肉",
        "food_name_en": "chicken thigh, raw",
        "food_category": "meat",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 171070,
        "calories": 185,
        "protein": 23.0,
        "fat": 9.0,
        "carbs": 0.0,
        "fiber": 0.0,
        "ash": 0.8,
        "calcium": 6,
        "phosphorus": 186,
        "omega3": 0.05,
        "omega6": 1.10,
        "water": 67.0,
    },
    {
        "food_name": "牛肉",
        "food_name_en": "beef, ground, raw",
        "food_category": "meat",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 167782,
        "calories": 254,
        "protein": 19.5,
        "fat": 19.0,
        "carbs": 0.0,
        "fiber": 0.0,
        "ash": 0.8,
        "calcium": 9,
        "phosphorus": 170,
        "omega3": 0.12,
        "omega6": 0.85,
        "water": 60.0,
    },
    {
        "food_name": "猪肉",
        "food_name_en": "pork, fresh, loin, raw",
        "food_category": "meat",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 167851,
        "calories": 143,
        "protein": 21.0,
        "fat": 6.3,
        "carbs": 0.0,
        "fiber": 0.0,
        "ash": 1.0,
        "calcium": 6,
        "phosphorus": 190,
        "omega3": 0.08,
        "omega6": 0.98,
        "water": 71.0,
    },
    {
        "food_name": "三文鱼",
        "food_name_en": "salmon, raw",
        "food_category": "meat",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 173673,
        "calories": 208,
        "protein": 20.4,
        "fat": 13.4,
        "carbs": 0.0,
        "fiber": 0.0,
        "ash": 1.1,
        "calcium": 9,
        "phosphorus": 200,
        "omega3": 2.26,
        "omega6": 0.38,
        "water": 65.0,
    },
    {
        "food_name": "鸡蛋",
        "food_name_en": "egg, whole, raw",
        "food_category": "egg",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 170903,
        "calories": 143,
        "protein": 12.6,
        "fat": 9.5,
        "carbs": 0.7,
        "fiber": 0.0,
        "ash": 0.9,
        "calcium": 56,
        "phosphorus": 198,
        "omega3": 0.11,
        "omega6": 1.35,
        "water": 75.0,
    },
    {
        "food_name": "白米饭",
        "food_name_en": "rice, white, cooked",
        "food_category": "grain",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 168991,
        "calories": 112,
        "protein": 2.6,
        "fat": 0.2,
        "carbs": 24.1,
        "fiber": 0.3,
        "ash": 0.2,
        "calcium": 3,
        "phosphorus": 35,
        "omega3": 0.00,
        "omega6": 0.05,
        "water": 72.0,
    },
    {
        "food_name": "南瓜",
        "food_name_en": "pumpkin, raw",
        "food_category": "vegetable",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 169827,
        "calories": 26,
        "protein": 1.0,
        "fat": 0.1,
        "carbs": 6.5,
        "fiber": 0.5,
        "ash": 0.8,
        "calcium": 21,
        "phosphorus": 44,
        "omega3": 0.00,
        "omega6": 0.02,
        "water": 91.0,
    },
    {
        "food_name": "胡萝卜",
        "food_name_en": "carrots, raw",
        "food_category": "vegetable",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 169329,
        "calories": 41,
        "protein": 0.9,
        "fat": 0.2,
        "carbs": 9.6,
        "fiber": 2.8,
        "ash": 0.8,
        "calcium": 33,
        "phosphorus": 35,
        "omega3": 0.00,
        "omega6": 0.01,
        "water": 88.0,
    },
    {
        "food_name": "西兰花",
        "food_name_en": "broccoli, raw",
        "food_category": "vegetable",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 169356,
        "calories": 34,
        "protein": 2.8,
        "fat": 0.4,
        "carbs": 6.6,
        "fiber": 2.4,
        "ash": 0.7,
        "calcium": 47,
        "phosphorus": 66,
        "omega3": 0.12,
        "omega6": 0.04,
        "water": 89.0,
    },
    {
        "food_name": "牛肝",
        "food_name_en": "beef liver, raw",
        "food_category": "organ",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 167820,
        "calories": 135,
        "protein": 19.0,
        "fat": 4.5,
        "carbs": 3.9,
        "fiber": 0.0,
        "ash": 1.4,
        "calcium": 5,
        "phosphorus": 300,
        "omega3": 0.10,
        "omega6": 0.65,
        "water": 70.0,
    },
    {
        "food_name": "鸡肝",
        "food_name_en": "chicken liver, raw",
        "food_category": "organ",
        "is_common": True,
        "is_pet_safe": True,
        "usda_fdc_id": 171090,
        "calories": 167,
        "protein": 21.0,
        "fat": 7.5,
        "carbs": 1.1,
        "fiber": 0.0,
        "ash": 1.4,
        "calcium": 8,
        "phosphorus": 250,
        "omega3": 0.05,
        "omega6": 1.30,
        "water": 68.0,
    },
]


async def seed_food(data_item: dict) -> bool:
    """导入单个食品到数据库。"""
    logger.info(f"Processing {data_item['food_name']}...")

    def to_dec(v: Optional[float]) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v))

    async with db.get_session() as session:
        from sqlalchemy import select
        stmt = select(FoodNutrition).where(FoodNutrition.food_name == data_item["food_name"])
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Food {data_item['food_name']} already exists, updating...")
            for key, value in data_item.items():
                if key in ["food_name", "food_name_en", "food_category", "is_common", "is_pet_safe", "usda_fdc_id"]:
                    setattr(existing, key, value)
                elif key in ["calories", "protein", "fat", "carbs", "fiber", "ash", "calcium", "phosphorus", "omega3", "omega6", "water"]:
                    setattr(existing, key, to_dec(value))
        else:
            logger.info(f"Creating new record for {data_item['food_name']}...")
            food = FoodNutrition(
                food_name=data_item["food_name"],
                food_name_en=data_item["food_name_en"],
                food_category=data_item["food_category"],
                is_common=data_item["is_common"],
                is_pet_safe=data_item["is_pet_safe"],
                usda_fdc_id=data_item["usda_fdc_id"],
                calories=to_dec(data_item["calories"]),
                protein=to_dec(data_item["protein"]),
                fat=to_dec(data_item["fat"]),
                carbs=to_dec(data_item["carbs"]),
                fiber=to_dec(data_item["fiber"]),
                ash=to_dec(data_item["ash"]),
                calcium=to_dec(data_item["calcium"]),
                phosphorus=to_dec(data_item["phosphorus"]),
                omega3=to_dec(data_item["omega3"]),
                omega6=to_dec(data_item["omega6"]),
                water=to_dec(data_item["water"]),
            )
            session.add(food)

        await session.commit()

    logger.info(f"Successfully imported {data_item['food_name']}")
    return True


async def main():
    """主函数。"""
    logger.info("Database initialized")

    # 逐个导入
    success_count = 0
    total_count = len(PRESET_DATA)

    for food_data in PRESET_DATA:
        success = await seed_food(food_data)
        if success:
            success_count += 1

    await db.dispose()

    logger.info(f"Import completed: {success_count}/{total_count} succeeded")

    if success_count != total_count:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
