"""
Pydantic 模型模块。

集中定义所有 API 请求/响应的数据模型。
"""

from .ai import (
    AIConversationRequest,
    AIConversationResponse,
    AIHealthReportRequest,
    AIHealthReportResponse,
    AIMessage,
    AINutritionAnalysisRequest,
    AINutritionAnalysisResponse,
)
from .auth import (
    TokenResponse,
    UserProfile,
    WechatLoginRequest,
    WechatLoginResponse,
)
from .families import (
    FamilyCreate,
    FamilyInviteResponse,
    FamilyJoinRequest,
    FamilyMemberResponse,
    FamilyResponse,
)
from .logs import (
    ActivityLogCreate,
    ActivityLogResponse,
    LogListResponse,
    MealLogCreate,
    MealLogResponse,
    WeightLogCreate,
    WeightLogResponse,
)
from .pets import (
    PetCreate,
    PetListResponse,
    PetResponse,
    PetUpdate,
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
