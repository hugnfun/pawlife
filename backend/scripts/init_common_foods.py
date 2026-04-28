#!/usr/bin/env python3
"""
初始化常见宠物食材营养数据脚本。

从 USDA FoodData Central API 下载指定食材的营养数据，
并保存到数据库中（每100克可食部分）。

需要的食材列表：
鸡胸肉、鸡腿肉、牛肉、猪肉、三文鱼、鸡蛋、
白米饭、南瓜、胡萝卜、西兰花、牛肝、鸡肝

Usage:
    python scripts/init_common_foods.py [--api-key KEY]
"""

import argparse
import asyncio
import logging
from typing import Optional, Dict, Any
from decimal import Decimal

import httpx

from core.config import settings
from models.nutrition import FoodNutrition
from services.database import db

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 需要导入的食材列表（中文名称 -> 搜索关键词英文）
TARGET_FOODS = [
    # 肉类
    ("鸡胸肉", "chicken breast, raw", "meat", 171058),
    ("鸡腿肉", "chicken thigh, raw", "meat", 171070),
    ("牛肉", "beef, ground, raw", "meat", 167782),
    ("猪肉", "pork, fresh, loin, raw", "meat", 167851),
    ("三文鱼", "salmon, raw", "meat", 173673),
    ("鸡蛋", "egg, whole, raw", "egg", 170903),
    # 谷物
    ("白米饭", "rice, white, cooked", "grain", 168991),
    # 蔬菜
    ("南瓜", "pumpkin, raw", "vegetable", 169827),
    ("胡萝卜", "carrots, raw", "vegetable", 169329),
    ("西兰花", "broccoli, raw", "vegetable", 169356),
    # 内脏
    ("牛肝", "beef liver, raw", "organ", 167820),
    ("鸡肝", "chicken liver, raw", "organ", 171090),
]

# 营养素编号映射 (USDA FoodData Central nutrient numbers)
NUTRIENT_MAP = {
    "calories": 1008,  # Energy (kcal)
    "protein": 1003,   # Protein (g)
    "fat": 1004,       # Total lipid (fat) (g)
    "carbs": 1005,     # Carbohydrate, by difference (g)
    "fiber": 1079,     # Dietary fiber (g)
    "ash": 1007,       # Ash (g)
    "calcium": 10051,  # Calcium (mg)
    "phosphorus": 10054,  # Phosphorus (mg)
    "omega3": 1269,    # Total omega-3 fatty acids (g)
    "omega6": 1272,    # Total omega-6 fatty acids (g)
    "water": 1051,     # Water (g)
}


class USDAFetcher:
    """USDA FoodData Central API 数据获取器。"""

    def __init__(self, api_key: str, base_url: str = "https://api.nal.usda.gov/fdc/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def get_food_by_fdc_id(self, fdc_id: int) -> Optional[Dict[str, Any]]:
        """通过 FDC ID 获取食品详情。"""
        url = f"{self.base_url}/food/{fdc_id}"
        params = {"api_key": self.api_key}

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get food {fdc_id}: {e}")
            return None

    def extract_nutrients(self, food_data: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """从食品数据中提取我们需要的营养素。"""
        nutrients: Dict[str, Optional[float]] = {
            key: None for key in NUTRIENT_MAP.keys()
        }

        if "foodNutrients" not in food_data:
            return nutrients

        for nutrient in food_data["foodNutrients"]:
            nutrient_id = nutrient.get("nutrient", {}).get("id")
            amount = nutrient.get("amount")

            if amount is None:
                continue

            for key, target_id in NUTRIENT_MAP.items():
                if nutrient_id == target_id:
                    nutrients[key] = float(amount)
                    break

        return nutrients

    def close(self):
        """关闭 HTTP 客户端。"""
        self.client.close()


async def import_food(
    fetcher: USDAFetcher,
    chinese_name: str,
    english_search: str,
    category: str,
    fdc_id: int,
) -> bool:
    """导入单个食品到数据库。"""
    logger.info(f"Processing {chinese_name} (FDC ID: {fdc_id})...")

    food_data = fetcher.get_food_by_fdc_id(fdc_id)
    if not food_data:
        logger.error(f"Failed to get data for {chinese_name}")
        return False

    nutrients = fetcher.extract_nutrients(food_data)
    logger.info(f"Extracted nutrients for {chinese_name}: {nutrients}")

    # 转换为 Decimal
    def to_dec(v: Optional[float]) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(round(v, 3)))

    async with db.get_session() as session:
        # 检查是否已存在
        from sqlalchemy import select
        stmt = select(FoodNutrition).where(FoodNutrition.food_name == chinese_name)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Food {chinese_name} already exists, updating...")
            existing.food_name_en = english_search
            existing.food_category = category
            existing.usda_fdc_id = fdc_id
            existing.calories = to_dec(nutrients["calories"])
            existing.protein = to_dec(nutrients["protein"])
            existing.fat = to_dec(nutrients["fat"])
            existing.carbs = to_dec(nutrients["carbs"])
            existing.fiber = to_dec(nutrients["fiber"])
            existing.ash = to_dec(nutrients["ash"])
            existing.calcium = to_dec(nutrients["calcium"])
            existing.phosphorus = to_dec(nutrients["phosphorus"])
            existing.omega3 = to_dec(nutrients["omega3"])
            existing.omega6 = to_dec(nutrients["omega6"])
            existing.water = to_dec(nutrients["water"])
        else:
            logger.info(f"Creating new record for {chinese_name}...")
            food = FoodNutrition(
                food_name=chinese_name,
                food_name_en=english_search,
                food_category=category,
                is_common=True,
                is_pet_safe=True,
                usda_fdc_id=fdc_id,
                calories=to_dec(nutrients["calories"]),
                protein=to_dec(nutrients["protein"]),
                fat=to_dec(nutrients["fat"]),
                carbs=to_dec(nutrients["carbs"]),
                fiber=to_dec(nutrients["fiber"]),
                ash=to_dec(nutrients["ash"]),
                calcium=to_dec(nutrients["calcium"]),
                phosphorus=to_dec(nutrients["phosphorus"]),
                omega3=to_dec(nutrients["omega3"]),
                omega6=to_dec(nutrients["omega6"]),
                water=to_dec(nutrients["water"]),
            )
            session.add(food)

        await session.commit()

    logger.info(f"Successfully imported {chinese_name}")
    return True


async def main():
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="Initialize common food nutrition data from USDA FoodData Central"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="USDA API key (overrides environment variable)",
    )
    args = parser.parse_args()

    # 获取 API key
    api_key = args.api_key or settings.usda_api_key
    if not api_key:
        logger.error(
            "USDA API key is required. "
            "Set it via --api-key or add USDA_API_KEY to your .env file."
        )
        exit(1)

    logger.info("Database initialized")

    # 创建获取器
    fetcher = USDAFetcher(api_key, settings.usda_api_base_url)

    # 逐个导入
    success_count = 0
    total_count = len(TARGET_FOODS)

    for chinese_name, english_name, category, fdc_id in TARGET_FOODS:
        success = await import_food(fetcher, chinese_name, english_name, category, fdc_id)
        if success:
            success_count += 1
        # 限速，避免 hitting API 限制
        await asyncio.sleep(1)

    fetcher.close()
    await db.dispose()

    logger.info(f"Import completed: {success_count}/{total_count} succeeded")

    if success_count != total_count:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
