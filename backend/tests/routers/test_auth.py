"""
认证路由集成测试。
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_wechat_login_success(async_client: AsyncClient, test_app):
    """测试微信登录成功。"""
    mock_wechat_data = {
        "openid": "test_openid_123",
        "session_key": "test_session_key",
        "unionid": "test_unionid",
    }

    with patch("routers.auth._get_wechat_session", new_callable=AsyncMock, return_value=mock_wechat_data):
        response = await async_client.post(
            "/api/v1/auth/wechat-login",
            json={
                "code": "test_code",
                "nickname": "测试用户",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "token" in data
    assert data["token"]["access_token"] is not None


@pytest.mark.asyncio
async def test_wechat_login_invalid_code(async_client: AsyncClient, test_app):
    """测试微信登录无效 code。"""
    from fastapi import HTTPException

    with patch("routers.auth._get_wechat_session", new_callable=AsyncMock, side_effect=HTTPException(
        status_code=400, detail="微信登录失败: 微信登录 code 无效或已过期"
    )):
        response = await async_client.post(
            "/api/v1/auth/wechat-login",
            json={"code": "invalid_code"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_profile_authenticated(async_client: AsyncClient, sample_user, auth_headers):
    """测试带 token 获取用户资料。"""
    response = await async_client.get(
        "/api/v1/auth/profile",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_user.id)
    assert data["nickname"] == sample_user.nickname


@pytest.mark.asyncio
async def test_get_profile_unauthenticated(async_client: AsyncClient):
    """测试无 token 获取用户资料 → 401。"""
    response = await async_client.get("/api/v1/auth/profile")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(async_client: AsyncClient, test_app):
    """测试登出接口。"""
    response = await async_client.post(
        "/api/v1/auth/logout",
        params={"session_id": "test_session"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
