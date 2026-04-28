"""
API 路由模块聚合。

统一导入所有路由模块并注册到 FastAPI 应用。
"""

from .auth import router as auth_router
from .pets import router as pets_router, pet_detail_router
from .logs import router as logs_router
from .ai import router as ai_router
from .families import router as families_router
from .chat import router as chat_router
from .account import router as account_router
from .upload import router as upload_router

# 所有路由列表
__all__ = [
    "auth_router",
    "pets_router",
    "pet_detail_router",
    "logs_router",
    "ai_router",
    "families_router",
    "chat_router",
    "account_router",
    "upload_router",
]