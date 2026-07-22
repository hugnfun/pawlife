"""
宠物路由集成测试。
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_pet(async_client: AsyncClient, auth_headers):
    """测试创建宠物。"""
    response = await async_client.post(
        "/api/v1/pets",
        headers=auth_headers,
        json={
            "name": "小黑",
            "species": "cat",
            "breed": "英短",
            "gender": "male",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "小黑"
    assert data["species"] == "cat"


@pytest.mark.asyncio
async def test_list_pets(async_client: AsyncClient, sample_pet, auth_headers):
    """测试列出用户宠物。"""
    response = await async_client.get(
        "/api/v1/pets",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_pet_detail(async_client: AsyncClient, sample_pet, auth_headers):
    """测试获取宠物详情。"""
    response = await async_client.get(
        f"/api/v1/pets/{sample_pet.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == sample_pet.name


@pytest.mark.asyncio
async def test_update_pet(async_client: AsyncClient, sample_pet, auth_headers):
    """测试更新宠物信息。"""
    response = await async_client.put(
        f"/api/v1/pets/{sample_pet.id}",
        headers=auth_headers,
        json={"name": "大白", "breed": "拉布拉多"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "大白"


@pytest.mark.asyncio
async def test_delete_pet(async_client: AsyncClient, sample_pet, auth_headers):
    """测试软删除宠物。"""
    response = await async_client.delete(
        f"/api/v1/pets/{sample_pet.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_pet_not_found(async_client: AsyncClient, auth_headers):
    """测试访问不存在的宠物 → 404。"""
    import uuid
    response = await async_client.get(
        f"/api/v1/pets/{uuid.uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_pets_requires_auth(async_client: AsyncClient):
    """测试宠物接口无认证 → 401。"""
    response = await async_client.get("/api/v1/pets")
    assert response.status_code == 401
