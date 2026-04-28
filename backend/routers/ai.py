"""
AI 分析 API 路由。

处理健康报告生成和营养分析等 AI 分析类请求。
对话类请求已迁移至 chat.py（基于 LangGraph）。
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.user import User
from models.log import MealLog
from models.pet import Pet
from schemas.ai import (
    AIHealthReportRequest,
    AIHealthReportResponse,
    AINutritionAnalysisRequest,
    AINutritionAnalysisResponse,
)
from services.database import get_db
from core.dependencies import get_current_user

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/ai", tags=["AI 分析"])


@router.post(
    "/health-report",
    response_model=AIHealthReportResponse,
    summary="生成健康报告",
    description="生成宠物健康报告，分析近期健康状况。",
    deprecated=True,
)
async def generate_health_report(
    request: AIHealthReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIHealthReportResponse:
    """生成健康报告接口。

    调用 GenerateHealthReportTool 聚合真实数据库数据生成报告。
    建议通过 AI 对话（/chat/stream）触发，本端点保留用于直接调用场景。

    Args:
        request: 健康报告请求
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        AIHealthReportResponse: 健康报告
    """
    try:
        # 检查宠物权限
        stmt = select(Pet).where(
            and_(
                Pet.id == request.pet_id,
                Pet.owner_id == current_user.id,
                Pet.is_active == True,
            )
        )
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()

        if pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="宠物不存在或无权访问"
            )

        # 调用 GenerateHealthReportTool 聚合真实数据
        from services.agent.tools import TOOL_REGISTRY

        tool = TOOL_REGISTRY["generate_health_report"]
        tool_result = await tool._arun(
            pet_id=request.pet_id,
            period_days=request.period_days,
            report_type=request.report_type,
        )

        if not tool_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"健康报告生成失败: {tool_result['error']}"
            )

        data = tool_result["data"]
        summary = data.get("summary", {})

        logger.info(f"生成健康报告: pet_id={request.pet_id}, period={request.period_days}天")

        return AIHealthReportResponse(
            report=data.get("report_text", ""),
            pet_id=request.pet_id,
            period_days=request.period_days,
            report_type=request.report_type,
            key_metrics={
                "avg_daily_food_g": summary.get("total_food_grams", 0) / max(request.period_days, 1),
                "total_meals": summary.get("total_meals", 0),
                "total_activities": summary.get("total_activities", 0),
                "total_activity_minutes": summary.get("total_activity_minutes", 0),
                "weight_records": summary.get("weight_records", 0),
                "weight_trend": data.get("weight_trend", []),
            },
            recommendations=["请保持规律的喂食和适量运动，定期监测体重变化。"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"生成健康报告失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成健康报告失败: {str(e)}"
        )


@router.post(
    "/nutrition-analysis",
    response_model=AINutritionAnalysisResponse,
    summary="营养分析",
    description="分析饮食记录的营养成分。",
    deprecated=True,
)
async def analyze_nutrition(
    request: AINutritionAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AINutritionAnalysisResponse:
    """营养分析接口。

    根据饮食记录中的食物名称和分量，调用 CalculateNutritionTool 查询真实营养数据。
    建议通过 AI 对话（/chat/stream）触发，本端点保留用于直接调用场景。

    Args:
        request: 营养分析请求
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        AINutritionAnalysisResponse: 营养分析结果
    """
    try:
        # 查询饮食记录
        stmt = select(MealLog, Pet).join(Pet).where(
            and_(
                MealLog.id == request.meal_log_id,
                Pet.owner_id == current_user.id,
            )
        )
        result = await db.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="饮食记录不存在或无权访问"
            )

        meal_log, pet = row

        # 调用 CalculateNutritionTool 查询真实营养数据
        from services.agent.tools import TOOL_REGISTRY

        tool = TOOL_REGISTRY["calculate_nutrition"]
        tool_result = await tool._arun(
            food_name=meal_log.food_name,
            amount_grams=float(meal_log.amount),
        )

        if not tool_result["success"]:
            # 营养数据库未收录该食物，返回基于通用比例的估算
            logger.warning(f"营养数据库未收录: {meal_log.food_name}，使用通用估算")
            amount = float(meal_log.amount)
            nutrient_breakdown = {
                "protein": round(amount * 0.15, 1),
                "fat": round(amount * 0.08, 1),
                "carbohydrates": round(amount * 0.60, 1),
                "fiber": round(amount * 0.02, 1),
                "moisture": round(amount * 0.15, 1),
            }
            calorie_total = round(amount * 3.5)
            analysis = (
                f"# 营养分析报告\n\n"
                f"## 食物信息\n"
                f"- 食物：{meal_log.food_name}\n"
                f"- 分量：{meal_log.amount}{meal_log.unit}\n"
                f"- 类型：{meal_log.food_type.value}\n\n"
                f"## 营养成分（通用估算）\n"
                f"营养数据库中暂未收录「{meal_log.food_name}」，以下为基于通用比例的粗略估算。\n\n"
                f"- 蛋白质：{nutrient_breakdown['protein']}g\n"
                f"- 脂肪：{nutrient_breakdown['fat']}g\n"
                f"- 碳水化合物：{nutrient_breakdown['carbohydrates']}g\n"
                f"- 纤维：{nutrient_breakdown['fiber']}g\n"
                f"- 总卡路里：约 {calorie_total}kcal\n"
            )
        else:
            nutrition_data = tool_result["data"]
            calculated = nutrition_data.get("calculated", {})
            nutrition_per_100g = nutrition_data.get("nutrition_per_100g", {})

            nutrient_breakdown = {
                "protein": calculated.get("protein", 0),
                "fat": calculated.get("fat", 0),
                "carbohydrates": calculated.get("carbs", 0),
                "fiber": calculated.get("fiber", 0),
                "moisture": calculated.get("moisture", 0),
            }
            calorie_total = calculated.get("calories", nutrition_data.get("total_calories", 0))

            # 判断数据来源是数据库还是估算
            source_note = ""
            if nutrition_per_100g.get("calories") is not None:
                source_note = f"（数据来源：营养数据库 {nutrition_data.get('food_category', '')}类）"
            else:
                source_note = "（数据来源：AI 估算）"

            analysis = (
                f"# 营养分析报告\n\n"
                f"## 食物信息\n"
                f"- 食物：{meal_log.food_name}\n"
                f"- 分量：{meal_log.amount}{meal_log.unit}\n"
                f"- 类型：{meal_log.food_type.value}\n"
                f"- 类别：{nutrition_data.get('food_category', '未知')}\n\n"
                f"## 营养成分 {source_note}\n"
                f"- 蛋白质：{nutrient_breakdown['protein']}g\n"
                f"- 脂肪：{nutrient_breakdown['fat']}g\n"
                f"- 碳水化合物：{nutrient_breakdown['carbohydrates']}g\n"
                f"- 纤维：{nutrient_breakdown['fiber']}g\n"
                f"- 总卡路里：约 {calorie_total}kcal\n"
            )

        # 构造 AAFCO 符合性提示（简化版，详细评估建议通过 AI 对话获取）
        aafco_compliance = {
            "protein": True,
            "fat": True,
            "carbohydrates": None,  # AAFCO 不要求碳水指标
            "calcium_phosphorus": None,  # 单次食物无法评估
        }

        suggestions = [
            "建议通过 AI 对话获取更详细的 AAFCO 标准评估",
            "可搭配不同食物增加营养均衡性",
            "注意控制总热量摄入，避免超重",
        ]

        logger.info(f"营养分析: meal_log_id={request.meal_log_id}, source={'db' if tool_result['success'] else 'estimate'}")

        return AINutritionAnalysisResponse(
            analysis=analysis,
            meal_log_id=request.meal_log_id,
            nutrient_breakdown=nutrient_breakdown,
            calorie_total=float(calorie_total),
            aafco_compliance=aafco_compliance,
            suggestions=suggestions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"营养分析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"营养分析失败: {str(e)}"
        )
