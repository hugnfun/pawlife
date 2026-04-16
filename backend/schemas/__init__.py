"""
Pydantic 模型模块。

集中定义所有 API 请求/响应的数据模型。
"""

from .auth import (
    WechatLoginRequest,
    UserProfile,
    TokenResponse,
    WechatLoginResponse,
)
from .pets import (
    PetCreate,
    PetUpdate,
    PetResponse,
    PetListResponse,
)
from .logs import (
    MealLogCreate,
    MealLogResponse,
    ActivityLogCreate,
    ActivityLogResponse,
    WeightLogCreate,
    WeightLogResponse,
    LogListResponse,
)
from .ai import (
    AIMessage,
    AIConversationRequest,
    AIConversationResponse,
    AIHealthReportRequest,
    AIHealthReportResponse,
    AINutritionAnalysisRequest,
    AINutritionAnalysisResponse,
)
from .families import (
    FamilyCreate,
    FamilyResponse,
    FamilyMemberResponse,
    FamilyJoinRequest,
    FamilyInviteResponse,
)

__all__ = [
    # 认证
    "WechatLoginRequest",
    "UserProfile",
    "TokenResponse",
    "WechatLoginResponse",
    # 宠物
    "PetCreate",
    "PetUpdate",
    "PetResponse",
    "PetListResponse",
    # 日志
    "MealLogCreate",
    "MealLogResponse",
    "ActivityLogCreate",
    "ActivityLogResponse",
    "WeightLogCreate",
    "WeightLogResponse",
    "LogListResponse",
    # AI
    "AIMessage",
    "AIConversationRequest",
    "AIConversationResponse",
    "AIHealthReportRequest",
    "AIHealthReportResponse",
    "AINutritionAnalysisRequest",
    "AINutritionAnalysisResponse",
    # 家庭组
    "FamilyCreate",
    "FamilyResponse",
    "FamilyMemberResponse",
    "FamilyJoinRequest",
    "FamilyInviteResponse",
]