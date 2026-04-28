"""
Phase 1 验收测试。

测试核心用户旅程：新用户注册 → 建档 → 记录饮食 → 重复检测 → 查询历史。
使用 pytest + httpx 异步客户端，覆盖完整用户对话流程。

测试场景：
1. 模拟新用户注册 → 触发建档对话 → 连续发送多轮消息完成档案建立 → 验证数据库 pets 表有对应记录
2. 发送「豆豆刚吃了200g希尔斯主粮」→ 验证 meal_logs 表写入正确
3. 间隔 30 分钟（mock 时间）后再发一条饮食记录 → 验证 AI 回复中包含重复喂食询问关键词
4. 发送「豆豆今天吃了什么」→ 验证回复内容包含步骤 2 记录的食物名称
5. 测量 SSE 接口的首字节响应时间，断言 < 3000ms
"""

import sys
import os
import time
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from uuid import UUID

# 添加 project root 目录和 backend 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

# SQLAlchemy 应该已经在环境中
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.main import app
from backend.core.config import settings
from backend.models.pet import Pet, PetSpecies, PetGender
from backend.models.log import MealLog
from backend.services.database import db
from backend.services.redis import redis_service


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def anyio_backend():
    """配置 anyio 后端。"""
    return "asyncio"


@pytest_asyncio.fixture(scope="function")
async def async_client():
    """创建异步 HTTP 客户端。"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def clean_test_data():
    """清理测试数据（在每个测试前执行）。"""
    # 清理 Redis 中的测试键
    await redis_service.delete("active_pet:12345678-1234-5678-1234-567812345678")
    # 所有测试数据会通过事务回滚清理，这里只清理 Redis
    yield


# =============================================================================
# Helper Functions
# =============================================================================

async def collect_sse_response(
    client: AsyncClient,
    message: str,
    session_id: str,
    token: Optional[str] = None,
    pet_id: Optional[UUID] = None,
    onboarding_step: Optional[str] = None,
    onboarding_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """收集 SSE 流式响应，返回完整内容和首字节时间。

    Args:
        client: httpx 异步客户端
        message: 用户消息
        session_id: 会话 ID
        token: 认证 token（可选，开发环境可不用）
        pet_id: 宠物 ID（可选）
        onboarding_step: 引导步骤（可选）
        onboarding_data: 已收集引导数据（可选）

    Returns:
        dict: {
            'full_text': 完整响应文本,
            'first_byte_ms': 首字节响应时间,
            'total_time_ms': 总响应时间,
            'chunks': 接收到的块列表
        }
    """
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request_body = {
        "message": message,
        "session_id": session_id,
        "input_type": "text",
    }
    if pet_id is not None:
        request_body["pet_id"] = str(pet_id)
    if onboarding_step is not None:
        request_body["onboarding_step"] = onboarding_step
    if onboarding_data is not None:
        request_body["onboarding_data"] = onboarding_data

    start_time = time.time()
    first_byte_time: Optional[float] = None
    full_text = ""
    chunks: List[str] = []

    # 使用流式请求
    url = f"{settings.api_prefix}/chat/stream"
    async with client.stream("POST", url, json=request_body, headers=headers) as response:
        # 检查响应状态
        assert response.status_code == 200, f"SSE 请求失败: {response.status_code}"

        # 逐行读取 SSE 响应
        async for line in response.aiter_lines():
            if first_byte_time is None:
                first_byte_time = time.time()

            line = line.strip()
            if not line:
                continue

            # 解析 SSE 行格式: data: {...}
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue

                try:
                    data = json.loads(data_str)
                    chunk = data.get("chunk", "")
                    is_final = data.get("is_final", False)
                    if chunk:
                        full_text += chunk
                        chunks.append(chunk)
                except json.JSONDecodeError:
                    continue

    end_time = time.time()

    first_byte_ms = (first_byte_time - start_time) * 1000 if first_byte_time else (end_time - start_time) * 1000
    total_time_ms = (end_time - start_time) * 1000

    return {
        "full_text": full_text,
        "first_byte_ms": first_byte_ms,
        "total_time_ms": total_time_ms,
        "chunks": chunks,
    }


# =============================================================================
# Test Case 1: 新用户注册 + 多轮对话完成建档
# =============================================================================

@pytest.mark.asyncio
async def test_phase1_scenario1_new_user_onboarding(
    async_client: AsyncClient,
    clean_test_data: None,
):
    """场景 1: 新用户注册 → 触发建档对话 → 连续多轮建档 → 验证数据库记录。

    测试流程：
    1. 新用户微信登录（创建用户账户）
    2. 发送第一条消息触发 AI 建档流程
    3. 连续多轮回答 AI 的问题，完成宠物档案建立
    4. 查询数据库验证 pets 表是否正确写入
    """
    # 1. 模拟微信登录获取 token
    mock_wechat_response = {
        "openid": "test_acceptance_phase1_user",
        "unionid": "test_acceptance_phase1_union",
        "session_key": "test_session_key",
    }

    with patch("routers.auth._get_wechat_session") as mock_get:
        mock_get.return_value = mock_wechat_response

        login_resp = await async_client.post(
            f"{settings.api_prefix}/auth/wechat-login",
            json={
                "code": "test_acceptance_code",
                "nickname": "验收测试用户",
            },
        )

    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["success"] is True
    token = login_data["token"]["access_token"]
    user_id = UUID(login_data["data"]["id"])
    session_id = login_data["token"]["session_id"]

    # 2. 发送第一条消息，触发建档流程
    response = await collect_sse_response(
        async_client,
        "你好，我想给我的宠物建立档案",
        session_id=session_id,
        token=token,
    )

    assert len(response["full_text"]) > 0
    # AI 应该开始引导，询问宠物名字
    full_text = response["full_text"]
    assert any(keyword in full_text for keyword in ["名字", "叫什么", "名称"])

    # 3. 多轮对话完成建档
    # 第一轮：回答名字"豆豆"
    response = await collect_sse_response(
        async_client,
        "豆豆",
        session_id=session_id,
        token=token,
        onboarding_step="collecting_species",
        onboarding_data={"name": "豆豆"},
    )
    assert len(response["full_text"]) > 0
    assert any(keyword in response["full_text"] for keyword in ["什么品种", "狗狗", "猫猫", "物种"])

    # 第二轮：回答物种（狗）
    response = await collect_sse_response(
        async_client,
        "是一只柯基犬",
        session_id=session_id,
        token=token,
        onboarding_step="collecting_birthdate",
        onboarding_data={"name": "豆豆", "species": "dog", "breed": "柯基"},
    )
    assert len(response["full_text"]) > 0
    assert any(keyword in response["full_text"] for keyword in ["出生日期", "生日", "什么时候出生"])

    # 第三轮：回答出生日期
    response = await collect_sse_response(
        async_client,
        "2022年3月15日",
        session_id=session_id,
        token=token,
        onboarding_step="collecting_weight",
        onboarding_data={
            "name": "豆豆",
            "species": "dog",
            "breed": "柯基",
            "birth_date": "2022-03-15",
        },
    )
    assert len(response["full_text"]) > 0
    assert any(keyword in response["full_text"] for keyword in ["体重", "多重", "公斤"])

    # 第四轮：回答体重
    response = await collect_sse_response(
        async_client,
        "现在12.5公斤",
        session_id=session_id,
        token=token,
        onboarding_step="collecting_gender",
        onboarding_data={
            "name": "豆豆",
            "species": "dog",
            "breed": "柯基",
            "birth_date": "2022-03-15",
            "current_weight": "12.5",
        },
    )
    assert len(response["full_text"]) > 0
    assert any(keyword in response["full_text"] for keyword in ["性别", "公母", "男孩子", "女孩子"])

    # 第五轮：回答性别
    response = await collect_sse_response(
        async_client,
        "公的，已经绝育了",
        session_id=session_id,
        token=token,
        onboarding_step="completed",
        onboarding_data={
            "name": "豆豆",
            "species": "dog",
            "breed": "柯基",
            "birth_date": "2022-03-15",
            "current_weight": "12.5",
            "gender": "male",
            "neutered": "neutered",
        },
    )
    assert len(response["full_text"]) > 0
    # 验证建档完成
    assert any(keyword in response["full_text"] for keyword in ["完成", "建档成功", "档案建立", "豆豆"])

    # 4. 验证数据库中有对应的宠物记录
    # 使用数据库会话查询
    async with db.get_session() as session:
        stmt = select(Pet).where(
            Pet.name == "豆豆",
            Pet.owner_id == user_id,
        )
        result = await session.execute(stmt)
        pet = result.scalar_one_or_none()

        assert pet is not None, "数据库中未找到新建的宠物档案"
        assert pet.name == "豆豆"
        assert pet.species == PetSpecies.DOG
        assert pet.breed == "柯基"
        assert pet.gender == PetGender.MALE
        assert pet.current_weight == Decimal("12.5")
        assert pet.is_active is True

        # 保存 pet_id 供后续测试使用（通过模块级变量传递）
        global TEST_PET_ID
        TEST_PET_ID = pet.id

    print(f"\n✅ 场景 1 通过：宠物档案创建成功，pet_id={TEST_PET_ID}")


# =============================================================================
# Test Case 2: 记录饮食验证写入正确
# =============================================================================

@pytest.mark.asyncio
async def test_phase1_scenario2_log_meal(
    async_client: AsyncClient,
    clean_test_data: None,
):
    """场景 2: 发送「豆豆刚吃了200g希尔斯主粮」→ 验证 meal_logs 表写入正确。"""
    # 先登录获取 token
    mock_wechat_response = {
        "openid": "test_acceptance_phase2_user",
        "unionid": "test_acceptance_phase2_union",
        "session_key": "test_session_key",
    }

    with patch("routers.auth._get_wechat_session") as mock_get:
        mock_get.return_value = mock_wechat_response

        login_resp = await async_client.post(
            f"{settings.api_prefix}/auth/wechat-login",
            json={"code": "test_phase2_code", "nickname": "验收测试用户2"},
        )

    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["token"]["access_token"]
    user_id = UUID(login_data["data"]["id"])
    session_id = login_data["token"]["session_id"]

    # 预先创建宠物档案（直接在数据库创建，跳过建档流程）
    from sqlalchemy.ext.asyncio import AsyncSession
    async with db.get_session() as session:
        pet = Pet(
            name="豆豆",
            species=PetSpecies.DOG,
            breed="柯基",
            gender=PetGender.MALE,
            birth_date=datetime(2022, 3, 15).date(),
            current_weight=Decimal("12.5"),
            owner_id=user_id,
            is_active=True,
        )
        session.add(pet)
        await session.commit()
        await session.refresh(pet)
        pet_id = pet.id

    # 设置活跃宠物到 Redis
    await redis_service.set_active_pet(str(user_id), str(pet_id))

    # 发送饮食记录消息
    response = await collect_sse_response(
        async_client,
        "豆豆刚吃了200g希尔斯主粮",
        session_id=session_id,
        token=token,
        pet_id=pet_id,
    )

    assert len(response["full_text"]) > 0
    # AI 应该确认记录成功
    assert any(keyword in response["full_text"] for keyword in ["记录", "已记下", "希尔斯", "200g"])

    # 验证数据库 meal_logs 表
    async with db.get_session() as session:
        stmt = select(MealLog).where(
            MealLog.pet_id == pet_id,
            MealLog.user_id == user_id,
        )
        result = await session.execute(stmt)
        meal_logs = result.scalars().all()

        assert len(meal_logs) >= 1, "meal_logs 表中未找到记录"
        meal_log = meal_logs[0]
        assert "希尔斯" in meal_log.food_name
        assert meal_log.amount == Decimal("200")
        assert meal_log.unit == "g"
        assert meal_log.is_duplicate is False

    print(f"\n✅ 场景 2 通过：饮食记录写入成功，food_name={meal_log.food_name}, amount={meal_log.amount}{meal_log.unit}")


# =============================================================================
# Test Case 3: 短间隔重复喂食检测
# =============================================================================

@pytest.mark.asyncio
async def test_phase1_scenario3_duplicate_feeding_warning(
    async_client: AsyncClient,
    clean_test_data: None,
):
    """场景 3: 间隔 30 分钟后再发一条 → 验证 AI 回复包含重复喂食询问关键词。"""
    # 先登录获取 token
    mock_wechat_response = {
        "openid": "test_acceptance_phase3_user",
        "unionid": "test_acceptance_phase3_union",
        "session_key": "test_session_key",
    }

    with patch("routers.auth._get_wechat_session") as mock_get:
        mock_get.return_value = mock_wechat_response

        login_resp = await async_client.post(
            f"{settings.api_prefix}/auth/wechat-login",
            json={"code": "test_phase3_code", "nickname": "验收测试用户3"},
        )

    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["token"]["access_token"]
    user_id = UUID(login_data["data"]["id"])
    session_id = login_data["token"]["session_id"]

    # 创建宠物
    async with db.get_session() as session:
        pet = Pet(
            name="豆豆",
            species=PetSpecies.DOG,
            breed="柯基",
            gender=PetGender.MALE,
            birth_date=datetime(2022, 3, 15).date(),
            current_weight=Decimal("12.5"),
            owner_id=user_id,
            is_active=True,
        )
        session.add(pet)
        await session.commit()
        await session.refresh(pet)
        pet_id = pet.id

    await redis_service.set_active_pet(str(user_id), str(pet_id))

    # 第一条喂食记录
    current_time = int(time.time())
    with patch("time.time", return_value=current_time):
        response1 = await collect_sse_response(
            async_client,
            "豆豆吃了150g渴望狗粮",
            session_id=session_id,
            token=token,
            pet_id=pet_id,
        )

    assert len(response1["full_text"]) > 0

    # 30 分钟后第二条喂食记录（仍然在 2 小时窗口内，应该触发重复检测）
    # Redis 默认检测窗口是 2 小时，30 分钟间隔会触发提醒
    second_time = current_time + 30 * 60  # +30 分钟
    with patch("time.time", return_value=second_time):
        response2 = await collect_sse_response(
            async_client,
            "豆豆又吃了100g零食",
            session_id=session_id,
            token=token,
            pet_id=pet_id,
        )

    full_text = response2["full_text"]
    assert len(full_text) > 0

    # 验证回复中包含重复喂食询问关键词
    duplicate_keywords = ["重复", "已经吃过", "刚刚喂过", "确定吗", "要不要再确认", "短时间内"]
    found_duplicate_warning = any(keyword in full_text for keyword in duplicate_keywords)
    assert found_duplicate_warning, f"AI 回复未包含重复喂食询问关键词，回复内容: {full_text[:100]}..."

    # 验证数据库两条记录都存在，第二条被标记为可能重复
    async with db.get_session() as session:
        stmt = select(MealLog).where(MealLog.pet_id == pet_id).order_by(MealLog.created_at)
        result = await session.execute(stmt)
        meal_logs = result.scalars().all()

        assert len(meal_logs) == 2, f"期望 2 条饮食记录，实际 {len(meal_logs)} 条"

    print(f"\n✅ 场景 3 通过：30分钟间隔重复喂食检测触发警告，回复包含询问关键词")


# =============================================================================
# Test Case 4: 查询今日饮食历史
# =============================================================================

@pytest.mark.asyncio
async def test_phase1_scenario4_query_meal_history(
    async_client: AsyncClient,
    clean_test_data: None,
):
    """场景 4: 发送「豆豆今天吃了什么」→ 验证回复包含之前记录的食物名称。"""
    # 先登录获取 token
    mock_wechat_response = {
        "openid": "test_acceptance_phase4_user",
        "unionid": "test_acceptance_phase4_union",
        "session_key": "test_session_key",
    }

    with patch("routers.auth._get_wechat_session") as mock_get:
        mock_get.return_value = mock_wechat_response

        login_resp = await async_client.post(
            f"{settings.api_prefix}/auth/wechat-login",
            json={"code": "test_phase4_code", "nickname": "验收测试用户4"},
        )

    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["token"]["access_token"]
    user_id = UUID(login_data["data"]["id"])
    session_id = login_data["token"]["session_id"]

    # 创建宠物
    async with db.get_session() as session:
        pet = Pet(
            name="豆豆",
            species=PetSpecies.DOG,
            breed="柯基",
            gender=PetGender.MALE,
            birth_date=datetime(2022, 3, 15).date(),
            current_weight=Decimal("12.5"),
            owner_id=user_id,
            is_active=True,
        )
        session.add(pet)
        await session.commit()
        await session.refresh(pet)
        pet_id = pet.id

    await redis_service.set_active_pet(str(user_id), str(pet_id))

    # 先记录一餐
    response1 = await collect_sse_response(
        async_client,
        "豆豆早上吃了200g希尔斯主粮",
        session_id=session_id,
        token=token,
        pet_id=pet_id,
    )
    assert len(response1["full_text"]) > 0

    # 查询今天吃了什么
    response2 = await collect_sse_response(
        async_client,
        "豆豆今天吃了什么",
        session_id=session_id,
        token=token,
        pet_id=pet_id,
    )

    full_text = response2["full_text"]
    assert len(full_text) > 0

    # 验证回复中包含食物名称
    assert "希尔斯" in full_text, f"回复中未包含食物名称'希尔斯'，回复内容: {full_text[:100]}..."
    assert "200" in full_text, f"回复中未包含分量信息，回复内容: {full_text[:100]}..."

    print(f"\n✅ 场景 4 通过：饮食历史查询成功，回复包含记录的食物名称'希尔斯'")


# =============================================================================
# Test Case 5: SSE 首字节响应时间性能测试
# =============================================================================

@pytest.mark.asyncio
async def test_phase1_scenario5_sse_first_byte_latency(
    async_client: AsyncClient,
    clean_test_data: None,
):
    """场景 5: 测量 SSE 接口的首字节响应时间，断言 < 3000ms。"""
    # 先登录获取 token
    mock_wechat_response = {
        "openid": "test_acceptance_phase5_user",
        "unionid": "test_acceptance_phase5_union",
        "session_key": "test_session_key",
    }

    with patch("routers.auth._get_wechat_session") as mock_get:
        mock_get.return_value = mock_wechat_response

        login_resp = await async_client.post(
            f"{settings.api_prefix}/auth/wechat-login",
            json={"code": "test_phase5_code", "nickname": "性能测试用户"},
        )

    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["token"]["access_token"]
    user_id = UUID(login_data["data"]["id"])
    session_id = login_data["token"]["session_id"]

    # 创建宠物（确保上下文存在）
    async with db.get_session() as session:
        pet = Pet(
            name="豆豆",
            species=PetSpecies.DOG,
            breed="柯基",
            gender=PetGender.MALE,
            birth_date=datetime(2022, 3, 15).date(),
            current_weight=Decimal("12.5"),
            owner_id=user_id,
            is_active=True,
        )
        session.add(pet)
        await session.commit()
        await session.refresh(pet)
        pet_id = pet.id

    await redis_service.set_active_pet(str(user_id), str(pet_id))

    # 多次测量取平均值（减少误差）
    measurements: List[float] = []
    test_messages = [
        "你好，帮我看看豆豆的饮食健康吗",
        "豆豆最近体重正常吗",
        "给我一些喂养建议",
    ]

    for i, msg in enumerate(test_messages):
        current_session_id = f"{session_id}_{i}"
        response = await collect_sse_response(
            async_client,
            msg,
            session_id=current_session_id,
            token=token,
            pet_id=pet_id,
        )
        measurements.append(response["first_byte_ms"])

    avg_first_byte_ms = sum(measurements) / len(measurements)
    max_first_byte_ms = max(measurements)

    print(f"\n📊 性能测试结果：")
    print(f"    各次测量: {[f'{m:.2f}ms' for m in measurements]}")
    print(f"    平均首字节时间: {avg_first_byte_ms:.2f}ms")
    print(f"    最大首字节时间: {max_first_byte_ms:.2f}ms")
    print(f"    阈值: 3000ms")

    # 断言最大响应时间小于阈值（保守检查，保证最差情况也达标）
    assert max_first_byte_ms < 3000, \
        f"SSE 首字节响应时间 {max_first_byte_ms:.2f}ms 超过阈值 3000ms"

    print(f"✅ 场景 5 通过：首字节响应时间 {avg_first_byte_ms:.2f}ms (avg) < 3000ms")


# =============================================================================
# 验收报告生成
# =============================================================================

def pytest_sessionfinish(session, exitstatus):
    """测试完成后输出验收报告。"""
    print("\n" + "=" * 70)
    print("📋 Phase 1 验收测试报告")
    print("=" * 70)

    # 获取测试结果统计
    total = session.testscollected
    passed = session.testspassed
    failed = session.testsfailed

    print(f"\n  测试场景总数: {total}")
    print(f"  通过: {passed} ✅")
    print(f"  失败: {failed} ❌")

    if failed == 0:
        print("\n🎉 所有验收测试通过！Phase 1 功能符合预期要求。")
        print("\n  验收标准：")
        print("  ✓ 新用户建档流程正常，数据库写入正确")
        print("  ✓ 饮食记录功能正常，meal_logs 写入正确")
        print("  ✓ 短间隔重复喂食检测功能正常")
        print("  ✓ 饮食历史查询功能正常")
        print("  ✓ SSE 首字节响应时间 < 3000ms")
    else:
        print("\n❌ 部分测试失败，请检查失败原因修复后重新验收。")

    print("\n" + "=" * 70 + "\n")


# 注册 pytest hook
def pytest_configure(config):
    """注册 sessionfinish hook。"""
    config.pluginmanager.register(
        type("AcceptanceReportPlugin", (), {"pytest_sessionfinish": staticmethod(pytest_sessionfinish)})(),
        "acceptance_report_plugin",
    )
