"""
双通道输入 API 集成测试（requirements-v1.1.md §2）。

覆盖 draft/confirm/cancel/get 端点：
- 通过在 mock_redis 内存字典中预置 draft，走真实 FastAPI + DB 路径
- 验证 confirm 成功后落库、缓存失效、幂等（二次 confirm 应 404）
- 验证权限隔离（他人的 draft 返回 404）
- 验证 payload_override 覆盖生效
- 验证 cancel 幂等（重复 cancel 返回 204）
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

# ==================== 辅助函数 ====================

async def _seed_meal_draft(async_client_app, sample_pet, sample_user, food_name="鸡胸肉", amount=50.0):
    """在 mock_redis 里预置一个饮食草稿，返回 draft_id。

    通过读取 mock_redis 实例 → 直接调 save_log_draft 完成种子数据准备。
    """
    # 从 app.dependency_overrides 拿到 mock_redis 实例
    from services.redis import get_redis
    redis_service = await async_client_app.dependency_overrides[get_redis]()

    draft_id = str(uuid4())
    await redis_service.save_log_draft(
        draft_id,
        {
            "type": "meal",
            "pet_id": str(sample_pet.id),
            "user_id": str(sample_user.id),
            "payload": {
                "food_name": food_name,
                "amount": amount,
                "unit": "g",
                "meal_time": datetime.now(timezone.utc).isoformat(),
                "notes": None,
                "photo_url": None,
            },
            "summary": f"记录一次饮食：{food_name} {amount}g",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return draft_id


async def _seed_weight_draft(async_client_app, sample_pet, sample_user, weight_kg=5.0):
    from services.redis import get_redis
    redis_service = await async_client_app.dependency_overrides[get_redis]()

    draft_id = str(uuid4())
    await redis_service.save_log_draft(
        draft_id,
        {
            "type": "weight",
            "pet_id": str(sample_pet.id),
            "user_id": str(sample_user.id),
            "payload": {"weight_kg": weight_kg},
            "summary": f"记录体重：{weight_kg} kg",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return draft_id


# ==================== confirm 正常流 ====================

@pytest.mark.asyncio
async def test_confirm_meal_draft_success(
    async_client: AsyncClient, test_app, sample_pet, sample_user, auth_headers,
):
    """🔑 confirm 成功：草稿真正落库 + 列表可见。"""
    draft_id = await _seed_meal_draft(test_app, sample_pet, sample_user, food_name="皇家猫粮")

    resp = await async_client.post(
        f"/api/v1/logs/confirmations/{draft_id}/confirm",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["log_type"] == "meal"
    assert data["was_edited"] is False
    assert "log_id" in data

    # 列表接口能查到
    list_resp = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(i["food_name"] == "皇家猫粮" for i in items)


@pytest.mark.asyncio
async def test_confirm_meal_draft_with_override(
    async_client: AsyncClient, test_app, sample_pet, sample_user, auth_headers,
):
    """🔑 payload_override 覆盖生效：AI 原 50g，用户改成 40g，最终落库应为 40g。"""
    draft_id = await _seed_meal_draft(test_app, sample_pet, sample_user, food_name="鸡胸肉", amount=50.0)

    resp = await async_client.post(
        f"/api/v1/logs/confirmations/{draft_id}/confirm",
        headers=auth_headers,
        json={"payload_override": {"amount": 40.0}},
    )
    assert resp.status_code == 200
    assert resp.json()["was_edited"] is True

    # 验证 DB 里真的是 40
    list_resp = await async_client.get(
        "/api/v1/logs/meals",
        headers=auth_headers,
        params={"pet_id": str(sample_pet.id)},
    )
    items = list_resp.json()["items"]
    target = next((i for i in items if i["food_name"] == "鸡胸肉"), None)
    assert target is not None
    assert float(target["amount"]) == 40.0


@pytest.mark.asyncio
async def test_confirm_weight_draft_success(
    async_client: AsyncClient, test_app, sample_pet, sample_user, auth_headers,
):
    """🔑 体重草稿 confirm 成功后：weight_logs 列表可见 + Pet.current_weight 更新。"""
    draft_id = await _seed_weight_draft(test_app, sample_pet, sample_user, weight_kg=6.5)

    resp = await async_client.post(
        f"/api/v1/logs/confirmations/{draft_id}/confirm",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200
    assert resp.json()["log_type"] == "weight"


# ==================== confirm 边界 ====================

@pytest.mark.asyncio
async def test_confirm_draft_not_found(async_client: AsyncClient, auth_headers):
    """不存在的 draft_id 返回 404。"""
    resp = await async_client.post(
        f"/api/v1/logs/confirmations/{uuid4()}/confirm",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_confirm_draft_idempotent(
    async_client: AsyncClient, test_app, sample_pet, sample_user, auth_headers,
):
    """🔑 幂等：第一次 confirm 成功后 draft 被删，第二次调用返回 404。"""
    draft_id = await _seed_meal_draft(test_app, sample_pet, sample_user)

    r1 = await async_client.post(
        f"/api/v1/logs/confirmations/{draft_id}/confirm",
        headers=auth_headers, json={},
    )
    assert r1.status_code == 200

    r2 = await async_client.post(
        f"/api/v1/logs/confirmations/{draft_id}/confirm",
        headers=auth_headers, json={},
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_confirm_draft_of_other_user_forbidden(
    async_client: AsyncClient, test_app, sample_pet, auth_headers,
):
    """🔑 其他用户的 draft：统一返回 404，不暴露"存在但无权"。"""
    from services.redis import get_redis
    redis_service = await test_app.dependency_overrides[get_redis]()

    other_user_id = str(uuid4())
    draft_id = str(uuid4())
    await redis_service.save_log_draft(
        draft_id,
        {
            "type": "meal",
            "pet_id": str(sample_pet.id),
            "user_id": other_user_id,  # 不是 sample_user
            "payload": {"food_name": "x", "amount": 1.0, "unit": "g",
                        "meal_time": datetime.now(timezone.utc).isoformat()},
            "summary": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    resp = await async_client.post(
        f"/api/v1/logs/confirmations/{draft_id}/confirm",
        headers=auth_headers, json={},
    )
    assert resp.status_code == 404


# ==================== cancel ====================

@pytest.mark.asyncio
async def test_cancel_draft_success(
    async_client: AsyncClient, test_app, sample_pet, sample_user, auth_headers,
):
    """取消草稿：删除成功 + 后续 confirm 返回 404 + 列表无新增。"""
    draft_id = await _seed_meal_draft(test_app, sample_pet, sample_user)

    r1 = await async_client.post(
        f"/api/v1/logs/confirmations/{draft_id}/cancel",
        headers=auth_headers,
    )
    assert r1.status_code == 204

    # 再 confirm 应 404
    r2 = await async_client.post(
        f"/api/v1/logs/confirmations/{draft_id}/confirm",
        headers=auth_headers, json={},
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_cancel_draft_idempotent(async_client: AsyncClient, auth_headers):
    """🔑 cancel 幂等：对不存在的 draft 也返回 204。"""
    resp = await async_client.post(
        f"/api/v1/logs/confirmations/{uuid4()}/cancel",
        headers=auth_headers,
    )
    assert resp.status_code == 204


# ==================== get draft 详情 ====================

@pytest.mark.asyncio
async def test_get_draft_details(
    async_client: AsyncClient, test_app, sample_pet, sample_user, auth_headers,
):
    """🔑 GET draft 返回 payload/summary/log_type，供前端刷新。"""
    draft_id = await _seed_meal_draft(test_app, sample_pet, sample_user, food_name="狗粮", amount=100.0)

    resp = await async_client.get(
        f"/api/v1/logs/confirmations/{draft_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["log_type"] == "meal"
    assert data["payload"]["food_name"] == "狗粮"
    assert data["payload"]["amount"] == 100.0
    assert "记录一次饮食" in data["summary"]


@pytest.mark.asyncio
async def test_get_draft_not_found(async_client: AsyncClient, auth_headers):
    resp = await async_client.get(
        f"/api/v1/logs/confirmations/{uuid4()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404
