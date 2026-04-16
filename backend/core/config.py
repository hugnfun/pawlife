"""
配置文件模块。

使用 Pydantic BaseSettings 管理应用配置，支持从环境变量加载。
遵循 12-factor app 原则，将配置存储在环境变量中。
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类。

    Attributes:
        app_name: 应用名称
        app_version: 应用版本
        debug: 是否开启调试模式
        environment: 运行环境 (development, testing, production)
        cors_origins: CORS 允许的来源
        api_prefix: API 路径前缀
    """

    # 应用基础配置
    app_name: str = "PawLife Backend"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:8080"]
    api_prefix: str = "/api/v1"

    # 数据库配置 (PostgreSQL)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pawlife"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False

    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"
    redis_pool_size: int = 10

    # AI 服务配置
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_key: Optional[str] = None
    azure_openai_deployment: Optional[str] = None

    # 腾讯云配置
    tencent_secret_id: Optional[str] = None
    tencent_secret_key: Optional[str] = None
    tencent_cos_region: str = "ap-beijing"
    tencent_cos_bucket: str = "pawlife"

    # 微信小程序配置
    wechat_app_id: Optional[str] = None
    wechat_app_secret: Optional[str] = None
    wechat_login_url: str = "https://api.weixin.qq.com/sns/jscode2session"

    # JWT 安全配置
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # 文件上传配置
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_image_types: List[str] = ["image/jpeg", "image/png", "image/gif"]

    # 模型配置
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例。

    Returns:
        Settings 实例
    """
    return settings