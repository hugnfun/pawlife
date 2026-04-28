"""
对话 API 路由。

处理 SSE 流式对话交互。
支持新用户首次建档引导流程（多轮状态机）。
"""

import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from models.user import User
from schemas.chat import ChatStreamRequest
from core.dependencies import get_current_user
from services.agent.runner import run_agent_streaming

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/chat", tags=["对话"])


@router.post(
    "/",
    summary="非流式对话",
    description="与 AI 宠物健康助手进行对话（非流式，用于小程序降级）。"
)
async def chat_non_stream(
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """非流式对话接口（小程序降级使用）。

    Args:
        request: 对话请求
        current_user: 当前登录用户

    Returns:
        dict: 包含响应文本和建议
    """
    full_response = ""

    async for chunk in run_agent_streaming(
        user_id=current_user.id,
        session_id=request.session_id or "default",
        message=request.message,
        pet_id=request.pet_id,
        message_type=request.input_type or "text",
        input_url=request.input_url,
        history=None,
        onboarding_step=request.onboarding_step,
        onboarding_data=request.onboarding_data,
    ):
        full_response += chunk

    logger.info(f"非流式对话完成: user_id={current_user.id}")

    return {
        "response": full_response,
        "session_id": request.session_id or "default",
        "suggestions": [],
    }


@router.post(
    "/stream",
    summary="流式对话",
    description="与 AI 宠物健康助手进行流式对话，实时返回响应（SSE 格式）。"
)
async def chat_stream(
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """流式对话接口。

    Args:
        request: 流式对话请求
        current_user: 当前登录用户

    Returns:
        StreamingResponse: SSE 格式流式响应
    """
    # 真实流式响应生成器 - 调用 Agent 流式推理
    async def generate_stream():
        async for chunk in run_agent_streaming(
            user_id=current_user.id,
            session_id=request.session_id or "default",
            message=request.message,
            pet_id=request.pet_id,
            message_type=request.input_type or "text",
            input_url=request.input_url,
            history=None,  # 历史消息由 create_initial_state 从 Redis 读取
            onboarding_step=request.onboarding_step,
            onboarding_data=request.onboarding_data,
        ):
            # 每个 chunk 包装成 SSE 格式，is_final 始终为 False 直到结束
            yield f"data: {json.dumps({'chunk': chunk, 'is_final': False})}\n\n"

        # 发送结束标记
        yield f"data: {json.dumps({'chunk': '', 'is_final': True})}\n\n"
        yield "data: [DONE]\n\n"
        logger.info(f"流式对话完成: user_id={current_user.id}, session_id={request.session_id}, pet_id={request.pet_id}")

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )
