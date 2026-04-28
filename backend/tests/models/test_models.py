"""
数据库模型测试。

使用 SQLite 内存数据库测试模型创建和关联。
"""

import uuid
import pytest
from datetime import date, datetime
from sqlalchemy import select

from models.user import User, UserRole
from models.pet import Pet, PetSpecies, PetGender, NeuteredStatus
from models.log import MealLog, ActivityLog, WeightLog


@pytest.mark.asyncio
async def test_user_model(test_db):
    """测试用户模型创建和查询。"""
    user = User(
        id=uuid.uuid4(),
        wechat_openid="test_model_openid",
        nickname="模型测试用户",
        role=UserRole.USER,
        is_active=True,
    )
    test_db.add(user)
    await test_db.flush()

    # 查询
    stmt = select(User).where(User.wechat_openid == "test_model_openid")
    result = await test_db.execute(stmt)
    found = result.scalar_one_or_none()

    assert found is not None
    assert found.nickname == "模型测试用户"
    assert found.role == UserRole.USER


@pytest.mark.asyncio
async def test_pet_model(test_db):
    """测试宠物模型创建和用户关联。"""
    user = User(
        id=uuid.uuid4(),
        wechat_openid="pet_test_openid",
        nickname="宠物主人",
        role=UserRole.USER,
    )
    test_db.add(user)
    await test_db.flush()

    pet = Pet(
        id=uuid.uuid4(),
        name="旺财",
        species=PetSpecies.DOG,
        breed="柴犬",
        gender=PetGender.MALE,
        neutered_status=NeuteredStatus.INTACT,
        owner_id=user.id,
    )
    test_db.add(pet)
    await test_db.flush()

    # 查询
    stmt = select(Pet).where(Pet.name == "旺财")
    result = await test_db.execute(stmt)
    found = result.scalar_one_or_none()

    assert found is not None
    assert found.species == PetSpecies.DOG
    assert found.owner_id == user.id


@pytest.mark.asyncio
async def test_meal_log_model(test_db):
    """测试饮食记录模型。"""
    user = User(
        id=uuid.uuid4(),
        wechat_openid="meal_test_openid",
        nickname="饮食测试用户",
    )
    test_db.add(user)
    await test_db.flush()

    pet = Pet(
        id=uuid.uuid4(),
        name="咪咪",
        species=PetSpecies.CAT,
        owner_id=user.id,
    )
    test_db.add(pet)
    await test_db.flush()

    meal = MealLog(
        id=uuid.uuid4(),
        pet_id=pet.id,
        user_id=user.id,
        food_name="猫粮",
        amount=50,
        unit="g",
        food_type=MealLog.FoodType.MAIN,
        meal_time=datetime.utcnow(),
    )
    test_db.add(meal)
    await test_db.flush()

    stmt = select(MealLog).where(MealLog.pet_id == pet.id)
    result = await test_db.execute(stmt)
    found = result.scalar_one_or_none()

    assert found is not None
    assert found.food_name == "猫粮"


@pytest.mark.asyncio
async def test_weight_log_model(test_db):
    """测试体重记录模型。"""
    user = User(
        id=uuid.uuid4(),
        wechat_openid="weight_test_openid",
    )
    test_db.add(user)
    await test_db.flush()

    pet = Pet(
        id=uuid.uuid4(),
        name="圆圆",
        species=PetSpecies.CAT,
        owner_id=user.id,
    )
    test_db.add(pet)
    await test_db.flush()

    weight_log = WeightLog(
        id=uuid.uuid4(),
        pet_id=pet.id,
        user_id=user.id,
        weight=4.5,
        measurement_time=datetime.utcnow(),
    )
    test_db.add(weight_log)
    await test_db.flush()

    stmt = select(WeightLog).where(WeightLog.pet_id == pet.id)
    result = await test_db.execute(stmt)
    found = result.scalar_one_or_none()

    assert found is not None
    assert float(found.weight) == 4.5
