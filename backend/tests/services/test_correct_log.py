"""数据纠错闭环测试（requirements-v1.1.md §3）。

覆盖：
1. 模型级纠正行为（is_corrected / corrected_from_id / correction_reason）
2. 列表查询过滤已纠正记录
3. 二次纠正场景
4. CorrectLastLogTool mock 测试
5. route_by_intent 路由 correct_log
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from models.log import ActivityLog, MealLog, WeightLog


@pytest.mark.asyncio
async def test_correct_last_meal_log(test_db, sample_pet, sample_user):
    """测试纠正最近一条饮食记录。"""
    original = MealLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        food_name="鸡胸肉",
        amount=50,
        unit="g",
        food_type=MealLog.FoodType.MAIN,
        meal_time=datetime.now(timezone.utc),
    )
    test_db.add(original)
    await test_db.commit()
    await test_db.refresh(original)

    original_id = original.id
    assert original.is_corrected is False

    # 模拟纠正：标记原记录 + 创建纠正版本
    original.is_corrected = True
    original.correction_reason = "用户说吃的是40g不是50g"

    corrected = MealLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        food_name="鸡胸肉",
        amount=40,
        unit="g",
        food_type=MealLog.FoodType.MAIN,
        meal_time=original.meal_time,
        corrected_from_id=original_id,
        correction_reason="用户说吃的是40g不是50g",
        is_corrected=False,
    )
    test_db.add(corrected)
    await test_db.commit()
    await test_db.refresh(corrected)

    # 验证原记录被标记
    assert original.is_corrected is True
    assert original.correction_reason == "用户说吃的是40g不是50g"

    # 验证纠正版本
    assert corrected.corrected_from_id == original_id
    assert corrected.is_corrected is False
    assert float(corrected.amount) == 40


@pytest.mark.asyncio
async def test_correct_weight_log(test_db, sample_pet, sample_user):
    """测试纠正体重记录。"""
    original = WeightLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        weight=5.0,
        measurement_time=datetime.now(timezone.utc),
    )
    test_db.add(original)
    await test_db.commit()
    await test_db.refresh(original)

    # 纠正
    original.is_corrected = True
    corrected = WeightLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        weight=5.2,
        measurement_time=original.measurement_time,
        corrected_from_id=original.id,
        correction_reason="体重记错了",
    )
    test_db.add(corrected)
    await test_db.commit()

    assert float(corrected.weight) == 5.2
    assert corrected.corrected_from_id == original.id


@pytest.mark.asyncio
async def test_double_correction(test_db, sample_pet, sample_user):
    """§3.3 验收标准：二次纠正场景。"""
    # 原始记录
    original = MealLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        food_name="狗粮",
        amount=100,
        unit="g",
        food_type=MealLog.FoodType.MAIN,
        meal_time=datetime.now(timezone.utc),
    )
    test_db.add(original)
    await test_db.commit()
    await test_db.refresh(original)

    # 第一次纠正：100g -> 80g
    original.is_corrected = True
    corrected1 = MealLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        food_name="狗粮",
        amount=80,
        unit="g",
        food_type=MealLog.FoodType.MAIN,
        meal_time=original.meal_time,
        corrected_from_id=original.id,
    )
    test_db.add(corrected1)
    await test_db.commit()
    await test_db.refresh(corrected1)

    # 第二次纠正：80g -> 60g
    corrected1.is_corrected = True
    corrected2 = MealLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        food_name="狗粮",
        amount=60,
        unit="g",
        food_type=MealLog.FoodType.MAIN,
        meal_time=original.meal_time,
        corrected_from_id=corrected1.id,
    )
    test_db.add(corrected2)
    await test_db.commit()
    await test_db.refresh(corrected2)

    # 验证链：original -> corrected1 -> corrected2
    assert original.is_corrected is True
    assert corrected1.is_corrected is True
    assert corrected2.is_corrected is False
    assert corrected2.corrected_from_id == corrected1.id
    assert corrected1.corrected_from_id == original.id
    assert float(corrected2.amount) == 60


@pytest.mark.asyncio
async def test_corrected_records_filtered_in_query(test_db, sample_pet, sample_user):
    """纠正后的记录在查询时被过滤。"""
    original = MealLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        food_name="猫粮",
        amount=50,
        unit="g",
        food_type=MealLog.FoodType.MAIN,
        meal_time=datetime.now(timezone.utc),
    )
    test_db.add(original)
    await test_db.commit()
    await test_db.refresh(original)

    # 纠正
    original.is_corrected = True
    corrected = MealLog(
        pet_id=sample_pet.id,
        user_id=sample_user.id,
        food_name="猫粮",
        amount=30,
        unit="g",
        food_type=MealLog.FoodType.MAIN,
        meal_time=original.meal_time,
        corrected_from_id=original.id,
    )
    test_db.add(corrected)
    await test_db.commit()

    # 查询未纠正的记录
    stmt = (
        select(MealLog)
        .where(MealLog.pet_id == sample_pet.id)
        .where(MealLog.is_corrected == False)  # noqa: E712
    )
    result = await test_db.execute(stmt)
    logs = result.scalars().all()

    # 应该只有一条（纠正版本），原记录被过滤
    assert len(logs) == 1
    assert float(logs[0].amount) == 30


@pytest.mark.asyncio
async def test_correct_last_log_tool_mock():
    """CorrectLastLogTool mock 测试。"""
    from services.agent.tools import CorrectLastLogTool

    tool = CorrectLastLogTool()

    with patch("services.database.db") as mock_db:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.get_session.return_value = mock_session

        # mock 查询返回一条记录
        mock_original = MagicMock()
        mock_original.id = uuid.uuid4()
        mock_original.pet_id = uuid.uuid4()
        mock_original.user_id = uuid.uuid4()
        mock_original.is_corrected = False
        mock_original.food_name = "狗粮"
        mock_original.amount = 100
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_original
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await tool._arun(
            pet_id=str(uuid.uuid4()),
            log_type="meal",
            corrections={"amount": 80},
            reason="纠正测试",
        )

        assert result["success"] is True
        assert result["data"]["changes"]["amount"] == 80
        assert result["data"]["reason"] == "纠正测试"


def test_route_by_intent_correct_log():
    """route_by_intent 正确路由 correct_log 意图。"""
    from services.agent.nodes import route_by_intent

    state = {"intent": "correct_log", "error": None}
    assert route_by_intent(state) == "handle_correct_log"


def test_route_by_intent_other():
    """其他意图不受影响。"""
    from services.agent.nodes import route_by_intent

    assert route_by_intent({"intent": "chit_chat", "error": None}) == "generate_response"
    assert route_by_intent({"intent": "log_meal", "error": None}) == "handle_log_meal"
