"""
AI 对话相关的 Pydantic 模型。
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AIMessage(BaseModel):
    """AI 消息模型。"""

    role: str = Field(..., description="角色 (user/assistant/system)")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[float] = Field(None, description="时间戳")


class AIConversationRequest(BaseModel):
    """AI 对话请求模型。"""

    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID（用于继续对话）")
    pet_id: Optional[UUID] = Field(None, description="当前活跃宠物ID")
    message_type: str = Field(default="text", description="消息类型 (text/voice/image)")
    voice_url: Optional[str] = Field(None, description="语音文件URL（当 message_type 为 voice 时）")
    image_url: Optional[str] = Field(None, description="图片URL（当 message_type 为 image 时）")


class AIConversationResponse(BaseModel):
    """AI 对话响应模型。"""

    response: str = Field(..., description="AI 回复内容")
    session_id: str = Field(..., description="会话ID（用于后续对话）")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用信息")
    pet_id: Optional[UUID] = Field(None, description="当前活跃宠物ID")
    suggestions: Optional[List[str]] = Field(None, description="建议的后续问题")


class AIHealthReportRequest(BaseModel):
    """AI 健康报告请求模型。"""

    pet_id: UUID = Field(..., description="宠物ID")
    period_days: int = Field(default=30, ge=1, le=365, description="报告周期（天）")
    report_type: str = Field(default="summary", description="报告类型 (summary/detail/comparison)")


class AIHealthReportResponse(BaseModel):
    """AI 健康报告响应模型。"""

    report: str = Field(..., description="健康报告内容")
    pet_id: UUID = Field(..., description="宠物ID")
    period_days: int = Field(..., description="报告周期")
    report_type: str = Field(..., description="报告类型")
    key_metrics: Dict[str, Any] = Field(..., description="关键指标")
    recommendations: List[str] = Field(..., description="建议列表")


class AINutritionAnalysisRequest(BaseModel):
    """AI 营养分析请求模型。"""

    meal_log_id: UUID = Field(..., description="饮食记录ID")
    analysis_type: str = Field(default="basic", description="分析类型 (basic/detailed/comparison)")


class AINutritionAnalysisResponse(BaseModel):
    """AI 营养分析响应模型。"""

    analysis: str = Field(..., description="营养分析内容")
    meal_log_id: UUID = Field(..., description="饮食记录ID")
    nutrient_breakdown: Dict[str, float] = Field(..., description="营养成分分解")
    calorie_total: float = Field(..., description="总卡路里")
    aafco_compliance: Dict[str, Optional[bool]] = Field(..., description="AAFCO 标准符合情况")
    suggestions: List[str] = Field(..., description="改进建议")
