"""
对话路由集成测试。
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_non_stream(async_client: AsyncClient, auth_headers):
    """测试非流式对话。"""
    # Mock agent runner 返回
    async def mock_stream(*args, **kwargs):
        yield "你好！"
        yield "我是你的宠物健康助手。"

    with patch("routers.chat.run_agent_streaming", side_effect=mock_stream):
        response = await async_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "你好",
                "input_type": "text",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "你好" in data["response"]


@pytest.mark.asyncio
async def test_chat_non_stream_with_pet_id(
    async_client: AsyncClient, sample_pet, auth_headers
):
    """测试带 pet_id 的非流式对话。"""
    async def mock_stream(*args, **kwargs):
        yield "这是关于你家宠物的建议。"

    with patch("routers.chat.run_agent_streaming", side_effect=mock_stream):
        response = await async_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "我家宠物最近怎么样？",
                "pet_id": str(sample_pet.id),
                "input_type": "text",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data


@pytest.mark.asyncio
async def test_chat_requires_auth(async_client: AsyncClient):
    """测试对话接口无认证 → 401。"""
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "你好"},
    )
    assert response.status_code == 401
