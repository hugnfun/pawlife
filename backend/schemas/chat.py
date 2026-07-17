"""
对话相关的 Pydantic 模型。
"""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    """流式对话请求模型。"""

    message: str = Field(..., description="用户消息")
    pet_id: Optional[UUID] = Field(None, description="宠物ID（可选）")
    input_type: str = Field(default="text", description="输入类型 (text/voice/image)，默认为 text")
    input_url: Optional[str] = Field(None, description="图片/音频文件URL（input_type 为 voice/image 时必填）")
    session_id: Optional[str] = Field(None, description="会话ID（可选，用于继续对话）")
    # 新用户建档引导状态（多轮收集需要保持上下文）
    onboarding_step: Optional[str] = Field(None, description="当前建档引导步骤（进行中时传递）")
    onboarding_data: Optional[Dict[str, Any]] = Field(None, description="已收集的建档数据（进行中时传递）")
