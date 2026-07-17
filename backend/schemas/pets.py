"""
宠物相关的 Pydantic 模型。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from models.pet import (
    BodyConditionScore,
    NeuteredStatus,
    PetGender,
    PetSpecies,
)


class PetCreate(BaseModel):
    """创建宠物请求模型。"""

    name: str = Field(..., min_length=1, max_length=50, description="宠物名字")
    species: PetSpecies = Field(..., description="物种")
    breed: Optional[str] = Field(None, max_length=100, description="品种")
    gender: PetGender = Field(default=PetGender.UNKNOWN, description="性别")
    birth_date: Optional[date] = Field(None, description="出生日期")
    neutered_status: NeuteredStatus = Field(
        default=NeuteredStatus.UNKNOWN, description="绝育状态"
    )
    current_weight: Optional[Decimal] = Field(
        None, ge=0, le=999.99, description="当前体重 (kg)"
    )
    ideal_weight: Optional[Decimal] = Field(
        None, ge=0, le=999.99, description="理想体重 (kg)"
    )
    body_condition_score: Optional[BodyConditionScore] = Field(
        None, description="体型评分"
    )
    known_diseases: Optional[str] = Field(None, description="已知疾病/过敏史")
    long_term_medication: Optional[str] = Field(None, description="长期用药")
    main_food_brand: Optional[str] = Field(None, max_length=100, description="主粮品牌")
    allergy_blacklist: Optional[str] = Field(None, description="过敏食材黑名单")
    avatar_url: Optional[str] = Field(None, description="宠物头像 URL")
    family_id: Optional[UUID] = Field(None, description="所属家庭ID")


class PetUpdate(BaseModel):
    """更新宠物请求模型。"""

    name: Optional[str] = Field(None, min_length=1, max_length=50, description="宠物名字")
    species: Optional[PetSpecies] = Field(None, description="物种")
    breed: Optional[str] = Field(None, max_length=100, description="品种")
    gender: Optional[PetGender] = Field(None, description="性别")
    birth_date: Optional[date] = Field(None, description="出生日期")
    neutered_status: Optional[NeuteredStatus] = Field(None, description="绝育状态")
    current_weight: Optional[Decimal] = Field(
        None, ge=0, le=999.99, description="当前体重 (kg)"
    )
    ideal_weight: Optional[Decimal] = Field(
        None, ge=0, le=999.99, description="理想体重 (kg)"
    )
    body_condition_score: Optional[BodyConditionScore] = Field(
        None, description="体型评分"
    )
    known_diseases: Optional[str] = Field(None, description="已知疾病/过敏史")
    long_term_medication: Optional[str] = Field(None, description="长期用药")
    main_food_brand: Optional[str] = Field(None, max_length=100, description="主粮品牌")
    allergy_blacklist: Optional[str] = Field(None, description="过敏食材黑名单")
    avatar_url: Optional[str] = Field(None, description="宠物头像 URL")
    family_id: Optional[UUID] = Field(None, description="所属家庭ID")
    is_active: Optional[bool] = Field(None, description="是否活跃")


class PetResponse(BaseModel):
    """宠物响应模型。"""

    id: UUID = Field(..., description="宠物ID")
    name: str = Field(..., description="宠物名字")
    species: PetSpecies = Field(..., description="物种")
    breed: Optional[str] = Field(None, description="品种")
    gender: PetGender = Field(..., description="性别")
    birth_date: Optional[date] = Field(None, description="出生日期")
    neutered_status: NeuteredStatus = Field(..., description="绝育状态")
    current_weight: Optional[Decimal] = Field(None, description="当前体重 (kg)")
    ideal_weight: Optional[Decimal] = Field(None, description="理想体重 (kg)")
    body_condition_score: Optional[BodyConditionScore] = Field(None, description="体型评分")
    known_diseases: Optional[str] = Field(None, description="已知疾病/过敏史")
    long_term_medication: Optional[str] = Field(None, description="长期用药")
    main_food_brand: Optional[str] = Field(None, description="主粮品牌")
    allergy_blacklist: Optional[str] = Field(None, description="过敏食材黑名单")
    avatar_url: Optional[str] = Field(None, description="宠物头像 URL")
    is_active: bool = Field(..., description="是否活跃")
    owner_id: UUID = Field(..., description="拥有者ID")
    family_id: Optional[UUID] = Field(None, description="所属家庭ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        """Pydantic 配置。"""
        from_attributes = True


class PetListResponse(BaseModel):
    """宠物列表响应模型。"""

    total: int = Field(..., description="总数量")
    items: List[PetResponse] = Field(..., description="宠物列表")
