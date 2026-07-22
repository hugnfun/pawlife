"""
文件上传路由集成测试。
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_image_success(async_client: AsyncClient, auth_headers):
    """测试上传有效图片。"""
    mock_cos = MagicMock()
    mock_cos.upload_bytes = MagicMock(return_value="https://cos.example.com/images/test.jpg")
    mock_cos.generate_key = MagicMock(return_value="images/2024/01/01/test.jpg")

    with patch("routers.upload.cos_service", mock_cos):
        image_data = io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
        response = await async_client.post(
            "/api/v1/upload/image",
            headers=auth_headers,
            files={"file": ("test.jpg", image_data, "image/jpeg")},
        )

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert data["url"] == "https://cos.example.com/images/test.jpg"


@pytest.mark.asyncio
async def test_upload_audio_success(async_client: AsyncClient, auth_headers):
    """测试上传音频。"""
    mock_cos = MagicMock()
    mock_cos.upload_bytes = MagicMock(return_value="https://cos.example.com/audio/test.m4a")
    mock_cos.generate_key = MagicMock(return_value="audio/2024/01/01/test.m4a")

    with patch("routers.upload.cos_service", mock_cos):
        audio_data = io.BytesIO(b'\x00' * 200)
        response = await async_client.post(
            "/api/v1/upload/audio",
            headers=auth_headers,
            files={"file": ("test.m4a", audio_data, "audio/mp4")},
        )

    assert response.status_code == 200
    data = response.json()
    assert "url" in data


@pytest.mark.asyncio
async def test_upload_requires_auth(async_client: AsyncClient):
    """测试上传接口无认证 → 401。"""
    image_data = io.BytesIO(b'\x00' * 100)
    response = await async_client.post(
        "/api/v1/upload/image",
        files={"file": ("test.jpg", image_data, "image/jpeg")},
    )
    assert response.status_code == 401
