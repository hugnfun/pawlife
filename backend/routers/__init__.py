"""
API 路由模块聚合。

统一导入所有路由模块并注册到 FastAPI 应用。
"""

from .auth import router as auth_router
from .pets import router as pets_router
from .logs import router as logs_router
from .ai import router as ai_router
from .families import router as families_router

# 所有路由列表
__all__ = [
    "auth_router",
    "pets_router",
    "logs_router",
    "ai_router",
    "families_router",
]