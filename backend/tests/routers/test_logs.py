"""
日志记录路由集成测试。

覆盖饮食记录和体重记录的 CRUD 接口，重点验证 Redis Cache-Aside 缓存机制：
- 缓存未命中 → DB 查询 → 回填缓存
- 缓存命中 → 直接返回
- 写入/删除 → 缓存失效
- 空结果 → 哨兵值防穿透
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient


# ==================== 饮食记录 ====================

@pytest.mark.asyncio
async def test_create_meal_log(async_client: AsyncClient, sample_pet, auth_headers):
    """测试创建饮食记录。"""
    response = await async_client.post(
        "/api/v1/logs/meals",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "food_name": "皇家猫粮",
            "food_type": "main",
            "amount": "50.00",
            "unit": "g",
            "meal_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["food_name"] == "皇家猫粮"
    assert data["pet_id"] == str(sample_pet.id)
    assert "id" in data
    assert "is_duplicate" in data


@pytest.mark.asyncio
async def test_create_meal_log_pet_not_found(async_client: AsyncClient, auth_headers):
    """测试创建饮食记录时宠物不存在返回 404。"""
    response = await async_client.post(
        "/api/v1/logs/meals",
        headers=auth_headers,
        json={
            "pet_id": "00000000-0000-0000-0000-000000000000",
            "food_name": "测试食物",
            "food_type": "main",
            "amount": "10.00",
            "unit": "g",
            "meal_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_meal_logs(async_client: AsyncClient, sample_pet, auth_headers):
    """测试获取饮食记录列表（缓存未命中 → DB 查询）。"""
    # 先创建一条记录
    await async_client.post(
        "/api/v1/logs/meals",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "food_name": "渴望狗粮",
            "food_type": "main",
            "amount": "100.00",
            "unit": "g",
            "meal_time": datetime.now(timezone.utc).isoformat(),
        },
    )

    # 查询列表
    response = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_meal_logs_empty(async_client: AsyncClient, sample_pet, auth_headers):
    """测试查询空饮食记录列表（验证缓存穿透防护）。"""
    response = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={
            "pet_id": str(sample_pet.id),
            "start_date": "2000-01-01T00:00:00",
            "end_date": "2000-01-02T00:00:00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_meal_logs_pet_not_found(async_client: AsyncClient, auth_headers):
    """测试查询不存在宠物的饮食记录返回 404。"""
    response = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_meal_logs_pagination(async_client: AsyncClient, sample_pet, auth_headers):
    """测试饮食记录列表分页。"""
    # 创建 3 条记录
    for i in range(3):
        await async_client.post(
            "/api/v1/logs/meals",
            headers=auth_headers,
            json={
                "pet_id": str(sample_pet.id),
                "food_name": f"食物_{i}",
                "food_type": "main",
                "amount": "30.00",
                "unit": "g",
                "meal_time": datetime.now(timezone.utc).isoformat(),
            },
        )

    # 第一页，每页 2 条
    response = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id), "page": 1, "page_size": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 3


# ==================== 体重记录 ====================

@pytest.mark.asyncio
async def test_create_weight_log(async_client: AsyncClient, sample_pet, auth_headers):
    """测试创建体重记录。"""
    response = await async_client.post(
        "/api/v1/logs/weights",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "weight": "5.20",
            "measurement_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["weight"] == "5.20"
    assert data["pet_id"] == str(sample_pet.id)


@pytest.mark.asyncio
async def test_create_weight_log_pet_not_found(async_client: AsyncClient, auth_headers):
    """测试创建体重记录时宠物不存在返回 404。"""
    response = await async_client.post(
        "/api/v1/logs/weights",
        headers=auth_headers,
        json={
            "pet_id": "00000000-0000-0000-0000-000000000000",
            "weight": "5.00",
            "measurement_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_weight_logs(async_client: AsyncClient, sample_pet, auth_headers):
    """测试获取体重记录列表。"""
    # 先创建一条体重记录
    await async_client.post(
        "/api/v1/logs/weights",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "weight": "5.50",
            "measurement_time": datetime.now(timezone.utc).isoformat(),
        },
    )

    response = await async_client.get(
        "/api/v1/logs/weights",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_weight_logs_pet_not_found(async_client: AsyncClient, auth_headers):
    """测试查询不存在宠物的体重记录返回 404。"""
    response = await async_client.get(
        "/api/v1/logs/weights",
        headers=auth_headers,
        params={"pet_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


# ==================== 缓存一致性 ====================

@pytest.mark.asyncio
async def test_cache_invalidated_on_create_meal(async_client: AsyncClient, sample_pet, auth_headers):
    """测试创建饮食记录后缓存被正确失效。

    流程：查询列表（缓存回填）→ 创建记录（缓存失效）→ 再次查询（应包含新记录）。
    """
    # 第一次查询，缓存回填
    resp1 = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert resp1.status_code == 200
    total_before = resp1.json()["total"]

    # 创建新记录（应触发缓存失效）
    await async_client.post(
        "/api/v1/logs/meals",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "food_name": "缓存测试食物",
            "food_type": "main",
            "amount": "20.00",
            "unit": "g",
            "meal_time": datetime.now(timezone.utc).isoformat(),
        },
    )

    # 再次查询，total 应增加
    resp2 = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert resp2.status_code == 200
    assert resp2.json()["total"] == total_before + 1


@pytest.mark.asyncio
async def test_cache_invalidated_on_create_weight(async_client: AsyncClient, sample_pet, auth_headers):
    """测试创建体重记录后缓存被正确失效。"""
    # 第一次查询
    resp1 = await async_client.get(
        "/api/v1/logs/weights",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert resp1.status_code == 200
    total_before = resp1.json()["total"]

    # 创建新体重记录
    await async_client.post(
        "/api/v1/logs/weights",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "weight": "6.00",
            "measurement_time": datetime.now(timezone.utc).isoformat(),
        },
    )

    # 再次查询
    resp2 = await async_client.get(
        "/api/v1/logs/weights",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert resp2.status_code == 200
    assert resp2.json()["total"] == total_before + 1
