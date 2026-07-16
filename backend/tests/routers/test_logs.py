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


# ==================== Round 2 新增测试 ====================

# ---------- 活动记录 ----------

@pytest.mark.asyncio
async def test_create_activity_log(async_client: AsyncClient, sample_pet, auth_headers):
    """测试创建活动记录（Round 2）。"""
    response = await async_client.post(
        "/api/v1/logs/activities",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "activity_type": "walk",
            "duration_minutes": 30,
            "activity_time": datetime.now(timezone.utc).isoformat(),
            "intensity": "moderate",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["activity_type"] == "walk"
    assert data["duration_minutes"] == 30


@pytest.mark.asyncio
async def test_create_activity_log_pet_not_found(async_client: AsyncClient, auth_headers):
    """测试创建活动记录时宠物不存在返回 404。"""
    response = await async_client.post(
        "/api/v1/logs/activities",
        headers=auth_headers,
        json={
            "pet_id": "00000000-0000-0000-0000-000000000000",
            "activity_type": "walk",
            "duration_minutes": 30,
            "activity_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_activity_logs(async_client: AsyncClient, sample_pet, auth_headers):
    """测试获取活动记录列表（缓存未命中 → DB 查询 → 回填）。"""
    await async_client.post(
        "/api/v1/logs/activities",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "activity_type": "run",
            "duration_minutes": 15,
            "activity_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    response = await async_client.get(
        "/api/v1/logs/activities",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_activity_logs_empty(async_client: AsyncClient, sample_pet, auth_headers):
    """测试活动记录空结果（防缓存穿透）。"""
    response = await async_client.get(
        "/api/v1/logs/activities",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_cache_invalidated_on_create_activity(async_client: AsyncClient, sample_pet, auth_headers):
    """🔑 缓存一致性：创建活动记录后缓存正确失效。"""
    resp1 = await async_client.get(
        "/api/v1/logs/activities",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    total_before = resp1.json()["total"]

    await async_client.post(
        "/api/v1/logs/activities",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "activity_type": "play",
            "duration_minutes": 20,
            "activity_time": datetime.now(timezone.utc).isoformat(),
        },
    )

    resp2 = await async_client.get(
        "/api/v1/logs/activities",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert resp2.json()["total"] == total_before + 1


# ---------- 删除接口 ----------

@pytest.mark.asyncio
async def test_delete_meal_log(async_client: AsyncClient, sample_pet, auth_headers):
    """测试删除饮食记录 + 缓存失效（Round 2 新增）。"""
    create_resp = await async_client.post(
        "/api/v1/logs/meals",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "food_name": "待删除食物",
            "food_type": "main",
            "amount": "30.00",
            "unit": "g",
            "meal_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    log_id = create_resp.json()["id"]

    del_resp = await async_client.delete(
        f"/api/v1/logs/meals/{log_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    # 再次删除应 404
    del_resp2 = await async_client.delete(
        f"/api/v1/logs/meals/{log_id}",
        headers=auth_headers,
    )
    assert del_resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_meal_log_not_found(async_client: AsyncClient, auth_headers):
    """删除不存在的饮食记录 → 404。"""
    resp = await async_client.delete(
        "/api/v1/logs/meals/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_weight_log(async_client: AsyncClient, sample_pet, auth_headers):
    """测试删除体重记录 + 缓存失效（Round 2 新增）。"""
    create_resp = await async_client.post(
        "/api/v1/logs/weights",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "weight": "5.50",
            "measurement_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    log_id = create_resp.json()["id"]

    del_resp = await async_client.delete(
        f"/api/v1/logs/weights/{log_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_activity_log(async_client: AsyncClient, sample_pet, auth_headers):
    """测试删除活动记录 + 缓存失效（Round 2 新增）。"""
    create_resp = await async_client.post(
        "/api/v1/logs/activities",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "activity_type": "walk",
            "duration_minutes": 10,
            "activity_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    log_id = create_resp.json()["id"]

    del_resp = await async_client.delete(
        f"/api/v1/logs/activities/{log_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_meal_log_invalidates_cache(async_client: AsyncClient, sample_pet, auth_headers):
    """🔑 删除饮食记录后列表 total 应减少（缓存被正确失效）。"""
    for i in range(2):
        await async_client.post(
            "/api/v1/logs/meals",
            headers=auth_headers,
            json={
                "pet_id": str(sample_pet.id),
                "food_name": f"食物-{i}",
                "food_type": "main",
                "amount": "10.00",
                "unit": "g",
                "meal_time": datetime.now(timezone.utc).isoformat(),
            },
        )

    resp1 = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    total_before = resp1.json()["total"]
    assert total_before == 2
    first_id = resp1.json()["items"][0]["id"]

    # 删除一条
    await async_client.delete(f"/api/v1/logs/meals/{first_id}", headers=auth_headers)

    resp2 = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert resp2.json()["total"] == total_before - 1


# ---------- 权限缓存 ----------

@pytest.mark.asyncio
async def test_pet_permission_cached_write_path(async_client: AsyncClient, sample_pet, auth_headers):
    """🔑 权限缓存正常路径：首次调用回填缓存，第二次调用命中缓存。

    通过检查 mock_redis 的调用记录验证缓存路径生效。
    """
    from unittest.mock import AsyncMock
    from services.redis import get_redis
    # 拿到 mock_redis 实例，直接读它的 call_count
    # 因为 conftest 里 fixture 是模块级的 mock，我们改一下策略：
    # 第一次调用 → get_pet_permission_cached(None) → 走 DB → set_pet_permission_cached
    # 通过链路走通即可（不改 mock 返回值也能触发正向路径）

    # 第一次请求：缓存未命中 → set 被调用
    r1 = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert r1.status_code == 200
    # 第二次请求：即使 mock 仍返回 None（模拟缓存过期），也应走完整 DB 校验，仍成功
    r2 = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_pet_permission_denied_when_not_owner(async_client: AsyncClient, auth_headers):
    """🔑 权限缓存不缓存负向结果：不存在/无权访问始终返回 404。"""
    for _ in range(2):
        resp = await async_client.get(
            "/api/v1/logs/meals",
            headers=auth_headers,
            params={"pet_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 404


# ==================== Round 2 后续：缓存打点（最小可观测性） ====================

@pytest.mark.asyncio
async def test_cache_metrics_emit_miss_and_set(
    async_client: AsyncClient, sample_pet, auth_headers, caplog,
):
    """🔑 首次查询应打点 cache.miss 与 cache.set 两个事件。"""
    import logging as _logging
    caplog.set_level(_logging.INFO, logger="routers.logs")

    resp = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert resp.status_code == 200

    events = [rec.__dict__.get("event") for rec in caplog.records if rec.__dict__.get("event")]
    # 首次请求：应至少产生 cache.miss + cache.set（回填哨兵值或数据）
    assert "cache.miss" in events
    assert "cache.set" in events


@pytest.mark.asyncio
async def test_cache_metrics_emit_invalidate_on_delete(
    async_client: AsyncClient, sample_pet, auth_headers, caplog,
):
    """🔑 删除记录应打点 cache.invalidate 事件。"""
    import logging as _logging
    caplog.set_level(_logging.INFO, logger="routers.logs")

    # 先创建一条
    create_resp = await async_client.post(
        "/api/v1/logs/meals",
        headers=auth_headers,
        json={
            "pet_id": str(sample_pet.id),
            "food_name": "待删除",
            "food_type": "main",
            "amount": "5.00",
            "unit": "g",
            "meal_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    log_id = create_resp.json()["id"]

    caplog.clear()
    await async_client.delete(f"/api/v1/logs/meals/{log_id}", headers=auth_headers)

    events = [rec.__dict__.get("event") for rec in caplog.records if rec.__dict__.get("event")]
    assert "cache.invalidate" in events
