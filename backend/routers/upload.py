"""
文件上传 API 路由。

支持图片和音频上传，存储到腾讯云 COS（或本地降级）。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel

from models.user import User
from services.cos import cos_service
from services.database import get_db
from core.dependencies import get_current_user
from core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["文件上传"])


class UploadResult(BaseModel):
    """上传结果模型。"""
    url: str
    key: str
    file_type: str
    file_size: int


@router.post(
    "/image",
    summary="上传图片",
    description="上传图片文件，支持 jpg/png/gif/webp 格式，最大 10MB。",
    response_model=UploadResult,
)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传图片到 COS 或本地存储。"""
    # 验证文件类型
    if file.content_type not in settings.allowed_image_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}，支持: {settings.allowed_image_types}",
        )

    # 读取文件内容
    content = await file.read()

    # 验证文件大小
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件过大，最大 {settings.max_upload_size // 1024 // 1024}MB",
        )

    # 生成存储路径
    ext = _get_extension(file.filename or "image.jpg")
    key = cos_service.generate_key(prefix="images", ext=ext)

    # 上传
    url = cos_service.upload_bytes(
        data=content,
        key=key,
        content_type=file.content_type or "image/jpeg",
    )

    logger.info(f"图片上传成功: user={current_user.id}, key={key}, size={len(content)}")

    return UploadResult(
        url=url,
        key=key,
        file_type="image",
        file_size=len(content),
    )


@router.post(
    "/audio",
    summary="上传音频",
    description="上传音频文件，支持 mp3/wav/m4a/aac 格式，最大 10MB。",
    response_model=UploadResult,
)
async def upload_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传音频到 COS 或本地存储。"""
    allowed_audio = {"audio/mpeg", "audio/wav", "audio/mp4", "audio/aac", "audio/x-m4a"}

    if file.content_type not in allowed_audio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的音频类型: {file.content_type}",
        )

    content = await file.read()

    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件过大，最大 {settings.max_upload_size // 1024 // 1024}MB",
        )

    ext = _get_extension(file.filename or "audio.m4a")
    key = cos_service.generate_key(prefix="audio", ext=ext)

    url = cos_service.upload_bytes(
        data=content,
        key=key,
        content_type=file.content_type or "audio/mp4",
    )

    logger.info(f"音频上传成功: user={current_user.id}, key={key}, size={len(content)}")

    return UploadResult(
        url=url,
        key=key,
        file_type="audio",
        file_size=len(content),
    )


@router.get(
    "/presigned-url",
    summary="获取预签名 URL",
    description="获取 COS 文件的临时访问 URL（仅 COS 模式）。",
)
async def get_presigned_url(
    key: str,
    expires: int = 3600,
    current_user: User = Depends(get_current_user),
):
    """获取 COS 预签名 URL。"""
    url = cos_service.get_presigned_url(key, expires=expires)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="无法生成预签名 URL（COS 未配置或文件不存在）",
        )
    return {"url": url, "expires": expires}


def _get_extension(filename: str) -> str:
    """从文件名提取扩展名。"""
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "bin"
