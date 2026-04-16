"""
AI 对话 API 路由。

处理与 AI 宠物健康助手的对话交互。
"""

import logging
import json
import uuid
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from schemas.ai import (
    AIConversationRequest,
    AIConversationResponse,
    AIHealthReportRequest,
    AIHealthReportResponse,
    AINutritionAnalysisRequest,
    AINutritionAnalysisResponse,
)
from services.database import get_db
from services.redis import get_redis, RedisService
from core.dependencies import get_current_user

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/ai", tags=["AI 助手"])


@router.post(
    "/conversation",
    response_model=AIConversationResponse,
    summary="AI 对话",
    description="与 AI 宠物健康助手进行对话。支持流式响应。"
)
async def ai_conversation(
    request: AIConversationRequest,
    db: AsyncSession = Depends(get_db),
    redis_service: RedisService = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> AIConversationResponse:
    """AI 对话接口。

    Args:
        request: 对话请求
        db: 数据库会话
        redis_service: Redis 服务
        current_user: 当前登录用户

    Returns:
        AIConversationResponse: AI 回复
    """
    try:
        # 获取或创建会话ID
        session_id = request.session_id or f"session_{current_user.id}_{uuid.uuid4().hex[:8]}"

        # 获取会话上下文
        context = await redis_service.get_session_context(session_id) or {}

        # 获取活跃宠物
        active_pet_id = request.pet_id
        if not active_pet_id:
            active_pet_id_str = await redis_service.get_active_pet(str(current_user.id))
            if active_pet_id_str:
                active_pet_id = UUID(active_pet_id_str)

        # 构建 AI 请求上下文
        ai_context = {
            "user_id": str(current_user.id),
            "user_name": current_user.nickname or "用户",
            "session_id": session_id,
            "active_pet_id": str(active_pet_id) if active_pet_id else None,
            "message": request.message,
            "message_type": request.message_type,
            "history": context.get("conversation_history", [])[-10:],  # 最近10条历史
        }

        # 调用 AI 服务（这里是模拟实现）
        # 在实际项目中，这里应该调用 LangGraph 编排的 AI 工作流
        ai_response = await _call_ai_service(ai_context)

        # 更新会话上下文
        new_history = context.get("conversation_history", [])
        new_history.append({"role": "user", "content": request.message})
        new_history.append({"role": "assistant", "content": ai_response["response"]})

        updated_context = {
            **context,
            "conversation_history": new_history[-20:],  # 最多保存20条历史
            "last_active": ai_context.get("timestamp"),
            "active_pet_id": str(active_pet_id) if active_pet_id else None,
        }

        await redis_service.set_session_context(session_id, updated_context)

        logger.info(f"AI 对话: user_id={current_user.id}, session_id={session_id}, pet_id={active_pet_id}")

        return AIConversationResponse(
            response=ai_response["response"],
            session_id=session_id,
            tool_calls=ai_response.get("tool_calls"),
            pet_id=active_pet_id,
            suggestions=ai_response.get("suggestions"),
        )

    except Exception as e:
        logger.exception(f"AI 对话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 对话失败: {str(e)}"
        )


@router.post(
    "/conversation/stream",
    summary="AI 流式对话",
    description="与 AI 助手进行流式对话，实时返回响应。"
)
async def ai_conversation_stream(
    request: AIConversationRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """AI 流式对话接口。

    Args:
        request: 对话请求
        current_user: 当前登录用户

    Returns:
        StreamingResponse: 流式响应
    """
    # 模拟流式响应
    async def generate_stream():
        response_text = f"你好{current_user.nickname or '用户'}！我是你的宠物健康助手。你刚才说：{request.message}\n\n"
        response_text += "我可以帮助你管理宠物的饮食、健康记录，并提供专业的营养建议。\n"
        response_text += "你可以问我关于宠物喂养、健康监测、营养分析等问题。"

        # 模拟逐字输出
        words = response_text.split()
        for i, word in enumerate(words):
            yield f"data: {json.dumps({'chunk': word + ' ', 'is_final': i == len(words) - 1})}\n\n"
            import asyncio
            await asyncio.sleep(0.05)  # 模拟延迟

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
        }
    )


@router.post(
    "/health-report",
    response_model=AIHealthReportResponse,
    summary="生成健康报告",
    description="生成宠物健康报告，分析近期健康状况。"
)
async def generate_health_report(
    request: AIHealthReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIHealthReportResponse:
    """生成健康报告接口。

    Args:
        request: 健康报告请求
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        AIHealthReportResponse: 健康报告
    """
    try:
        # 检查宠物权限
        from sqlalchemy import select, and_
        from models.pet import Pet

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

        # 模拟 AI 生成的健康报告
        report = f"""# {pet.name} 健康报告（最近{request.period_days}天）

## 📊 总体评估
{pet.name} 的整体健康状况良好，饮食和活动记录保持规律。

## 🍽️ 饮食分析
- 平均每日进食量：{pet.current_weight * 0.02 if pet.current_weight else 0:.1f}kg（建议范围）
- 饮食多样性：中等（建议增加食物种类）
- 喂食规律性：良好

## 🏃‍♂️ 活动分析
- 平均每日活动时间：45分钟
- 活动强度：中等
- 建议：可适当增加户外活动时间

## ⚖️ 体重趋势
- 当前体重：{pet.current_weight if pet.current_weight else '未记录'}kg
- 理想体重：{pet.ideal_weight if pet.ideal_weight else '未设定'}kg
- 体重变化：稳定（建议定期监测）

## 💡 关键建议
1. 继续保持规律的饮食和活动习惯
2. 每月进行一次全面的健康检查
3. 关注体重变化，调整饮食量
4. 增加一些互动游戏，提升宠物幸福感

## 🔍 需要关注
- 近期体重略有上升趋势
- 建议减少零食摄入
- 增加每日运动量10-15分钟
"""

        logger.info(f"生成健康报告: pet_id={request.pet_id}, period={request.period_days}天")

        return AIHealthReportResponse(
            report=report,
            pet_id=request.pet_id,
            period_days=request.period_days,
            report_type=request.report_type,
            key_metrics={
                "avg_daily_food": pet.current_weight * 0.02 if pet.current_weight else 0,
                "avg_activity_minutes": 45,
                "weight_trend": "stable",
                "health_score": 85,
            },
            recommendations=[
                "继续保持规律的饮食和活动习惯",
                "每月进行一次全面的健康检查",
                "关注体重变化，调整饮食量",
                "增加一些互动游戏，提升宠物幸福感",
            ]
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
    description="分析饮食记录的营养成分。"
)
async def analyze_nutrition(
    request: AINutritionAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AINutritionAnalysisResponse:
    """营养分析接口。

    Args:
        request: 营养分析请求
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        AINutritionAnalysisResponse: 营养分析结果
    """
    try:
        # 检查饮食记录权限
        from sqlalchemy import select, and_
        from models.log import MealLog
        from models.pet import Pet

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

        # 模拟营养分析
        analysis = f"""# 营养分析报告

## 🍖 食物信息
- 食物：{meal_log.food_name}
- 分量：{meal_log.amount}{meal_log.unit}
- 类型：{meal_log.food_type.value}

## 📈 营养成分（估算）
根据标准营养数据库估算，这份食物的营养成分如下：

- 蛋白质：{meal_log.amount * 0.15:.1f}g（优质蛋白质来源）
- 脂肪：{meal_log.amount * 0.08:.1f}g（适中）
- 碳水化合物：{meal_log.amount * 0.60:.1f}g（主要能量来源）
- 纤维：{meal_log.amount * 0.02:.1f}g（有助于消化）
- 总卡路里：{meal_log.amount * 3.5:.0f}kcal

## 🏆 AAFCO 标准符合情况
✅ 蛋白质含量符合成犬/猫维持需求
✅ 脂肪含量在建议范围内
⚠️ 碳水化合物比例略高（建议增加蛋白质比例）
✅ 钙磷比例平衡

## 🎯 对 {pet.name} 的适用性
- 体重：{pet.current_weight if pet.current_weight else '未记录'}kg
- 理想体重：{pet.ideal_weight if pet.ideal_weight else '未设定'}kg
- 活动水平：中等

这份食物适合作为 {pet.name} 的{'主粮' if meal_log.food_type.value == 'main' else '零食'}。
"""

        logger.info(f"营养分析: meal_log_id={request.meal_log_id}")

        return AINutritionAnalysisResponse(
            analysis=analysis,
            meal_log_id=request.meal_log_id,
            nutrient_breakdown={
                "protein": float(meal_log.amount * 0.15),
                "fat": float(meal_log.amount * 0.08),
                "carbohydrates": float(meal_log.amount * 0.60),
                "fiber": float(meal_log.amount * 0.02),
                "moisture": float(meal_log.amount * 0.15),
            },
            calorie_total=float(meal_log.amount * 3.5),
            aafco_compliance={
                "protein": True,
                "fat": True,
                "carbohydrates": False,
                "calcium_phosphorus": True,
            },
            suggestions=[
                "建议增加蛋白质来源食物的比例",
                "可搭配一些蔬菜增加纤维摄入",
                "注意控制总热量摄入，避免超重",
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"营养分析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"营养分析失败: {str(e)}"
        )


async def _call_ai_service(context: Dict[str, Any]) -> Dict[str, Any]:
    """调用 AI 服务的模拟函数。

    在实际项目中，这里应该调用 LangGraph 编排的 AI 工作流，
    包括意图识别、工具调用、上下文管理等。

    Args:
        context: 对话上下文

    Returns:
        Dict[str, Any]: AI 响应
    """
    # 模拟 AI 响应
    user_message = context.get("message", "")
    pet_id = context.get("active_pet_id")

    # 简单的意图识别
    if any(keyword in user_message.lower() for keyword in ["吃饭", "喂食", "食物", "喂养"]):
        response = f"关于喂食的问题，我可以帮你记录饮食或分析营养。"
        if pet_id:
            response += f" 当前活跃宠物ID: {pet_id}"
        suggestions = ["记录一次喂食", "查看今日饮食记录", "分析食物营养"]

    elif any(keyword in user_message.lower() for keyword in ["活动", "运动", "散步", "跑步"]):
        response = f"关于活动的问题，我可以帮你记录运动或分析活动量。"
        if pet_id:
            response += f" 当前活跃宠物ID: {pet_id}"
        suggestions = ["记录一次活动", "查看活动历史", "分析活动量"]

    elif any(keyword in user_message.lower() for keyword in ["体重", "称重", "胖", "瘦"]):
        response = f"关于体重的问题，我可以帮你记录体重或分析体重趋势。"
        if pet_id:
            response += f" 当前活跃宠物ID: {pet_id}"
        suggestions = ["记录一次体重", "查看体重历史", "分析体重趋势"]

    elif any(keyword in user_message.lower() for keyword in ["健康", "报告", "状况"]):
        response = f"关于健康的问题，我可以为你生成健康报告。"
        if pet_id:
            response += f" 当前活跃宠物ID: {pet_id}"
        suggestions = ["生成健康报告", "查看健康指标", "设置健康提醒"]

    else:
        response = f"你好！我是你的宠物健康助手。我可以帮助你管理宠物的饮食、健康记录，并提供专业的营养建议。"
        if pet_id:
            response += f" 当前活跃宠物ID: {pet_id}"
        suggestions = ["记录一次喂食", "生成健康报告", "分析食物营养", "查看活动历史"]

    return {
        "response": response,
        "suggestions": suggestions,
        "tool_calls": None,
    }