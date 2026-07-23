"""
PawLife 后端应用入口。

基于 FastAPI 构建的 AI Native 宠物健康管理后端。
遵循 CLAUDE.md 中的技术栈和架构原则。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from core.config import settings
from routers import (
    account_router,
    ai_router,
    auth_router,
    chat_router,
    families_router,
    logs_router,
    pet_detail_router,
    pets_router,
    upload_router,
)
from services.database import db
from services.redis import redis_service

# 配置日志
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    管理数据库和 Redis 的连接池。
    """
    # 启动时
    logger.info("PawLife 后端服务启动中...")
    logger.info(f"环境: {settings.environment}")
    logger.info(f"调试模式: {settings.debug}")
    logger.info(f"数据库 URL: {settings.database_url[:20]}...")
    logger.info(f"Redis URL: {settings.redis_url[:20]}...")

    # 健康检查
    try:
        db_healthy = await db.health_check()
        redis_healthy = await redis_service.health_check()

        if db_healthy and redis_healthy:
            logger.info("✅ 数据库和 Redis 连接正常")
        else:
            logger.error("❌ 数据库或 Redis 连接异常")

    except Exception as e:
        logger.error(f"健康检查失败: {e}")

    yield  # 应用运行中

    # 关闭时
    logger.info("PawLife 后端服务关闭中...")
    await db.dispose()
    await redis_service.dispose()
    logger.info("✅ 资源已释放")


# 创建 FastAPI 应用
app = FastAPI(
    title="PawLife API",
    description="AI Native 宠物健康管理平台后端 API",
    version="1.0.0",
    docs_url=None,  # 自定义文档路由
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 自定义 API 文档
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """自定义 Swagger UI 文档。"""
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="PawLife API - Swagger UI",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    """自定义 ReDoc 文档。"""
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title="PawLife API - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )


def custom_openapi():
    """自定义 OpenAPI 文档。"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # 添加安全方案
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    # 添加全局安全要求
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器。"""
    logger.error(f"未捕获的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.debug else "请稍后重试",
        },
    )


# 注册路由
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(pets_router, prefix=settings.api_prefix)
app.include_router(logs_router, prefix=settings.api_prefix)
app.include_router(ai_router, prefix=settings.api_prefix)
app.include_router(families_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(account_router, prefix=settings.api_prefix)
app.include_router(pet_detail_router, prefix=settings.api_prefix)
app.include_router(upload_router, prefix=settings.api_prefix)


# 根路由
@app.get("/")
async def root():
    """根路由，返回 API 基本信息。"""
    return {
        "app": "PawLife Backend",
        "version": "1.0.0",
        "description": "AI Native 宠物健康管理平台",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/api/openapi.json",
    }


@app.get("/health")
async def health_check():
    """健康检查端点。"""
    try:
        db_healthy = await db.health_check()
        redis_healthy = await redis_service.health_check()

        if db_healthy and redis_healthy:
            return {
                "status": "healthy",
                "database": "connected",
                "redis": "connected",
                "timestamp": "now",
            }
        else:
            return {
                "status": "unhealthy",
                "database": "connected" if db_healthy else "disconnected",
                "redis": "connected" if redis_healthy else "disconnected",
                "timestamp": "now",
            }, status.HTTP_503_SERVICE_UNAVAILABLE

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": "now",
        }, status.HTTP_503_SERVICE_UNAVAILABLE


@app.get("/api/info")
async def api_info():
    """API 信息端点。"""
    return {
        "name": "PawLife API",
        "version": "1.0.0",
        "environment": settings.environment,
        "debug": settings.debug,
        "features": [
            "AI Native 对话接口",
            "宠物健康档案管理",
            "饮食/活动/体重记录",
            "家庭协作管理",
            "营养分析与报告",
        ],
        "endpoints": {
            "auth": "/api/auth",
            "pets": "/api/pets",
            "logs": "/api/logs",
            "ai": "/api/ai",
            "families": "/api/families",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )
