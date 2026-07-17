"""
日志记录相关的 Pydantic 模型。
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from models.log import ActivityLog, MealLog


class MealLogCreate(BaseModel):
    """创建饮食记录请求模型。"""

    pet_id: UUID = Field(..., description="宠物ID")
    food_name: str = Field(..., max_length=100, description="食物名称")
    food_type: MealLog.FoodType = Field(default=MealLog.FoodType.MAIN, description="食物类型")
    amount: Decimal = Field(..., ge=0, le=99999.99, description="分量")
    unit: str = Field(default="g", max_length=20, description="单位")
    meal_time: datetime = Field(..., description="喂食时间")
    notes: Optional[str] = Field(None, description="备注")
    photo_url: Optional[str] = Field(None, description="照片URL")


class MealLogResponse(BaseModel):
    """饮食记录响应模型。"""

    id: UUID = Field(..., description="记录ID")
    pet_id: UUID = Field(..., description="宠物ID")
    user_id: UUID = Field(..., description="用户ID")
    food_name: str = Field(..., description="食物名称")
    food_type: MealLog.FoodType = Field(..., description="食物类型")
    amount: Decimal = Field(..., description="分量")
    unit: str = Field(..., description="单位")
    meal_time: datetime = Field(..., description="喂食时间")
    notes: Optional[str] = Field(None, description="备注")
    photo_url: Optional[str] = Field(None, description="照片URL")
    is_duplicate: bool = Field(..., description="是否重复喂食")
    duplicate_of: Optional[UUID] = Field(None, description="重复的记录ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        """Pydantic 配置。"""
        from_attributes = True


class ActivityLogCreate(BaseModel):
    """创建活动记录请求模型。"""

    pet_id: UUID = Field(..., description="宠物ID")
    activity_type: ActivityLog.ActivityType = Field(..., description="活动类型")
    duration_minutes: int = Field(..., ge=1, le=1440, description="持续时间 (分钟)")
    activity_time: datetime = Field(..., description="活动时间")
    intensity: Optional[str] = Field(None, max_length=20, description="强度")
    calories_estimated: Optional[Decimal] = Field(None, ge=0, description="预估消耗卡路里")
    notes: Optional[str] = Field(None, description="备注")


class ActivityLogResponse(BaseModel):
    """活动记录响应模型。"""

    id: UUID = Field(..., description="记录ID")
    pet_id: UUID = Field(..., description="宠物ID")
    user_id: UUID = Field(..., description="用户ID")
    activity_type: ActivityLog.ActivityType = Field(..., description="活动类型")
    duration_minutes: int = Field(..., description="持续时间 (分钟)")
    activity_time: datetime = Field(..., description="活动时间")
    intensity: Optional[str] = Field(None, description="强度")
    calories_estimated: Optional[Decimal] = Field(None, description="预估消耗卡路里")
    notes: Optional[str] = Field(None, description="备注")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        """Pydantic 配置。"""
        from_attributes = True


class WeightLogCreate(BaseModel):
    """创建体重记录请求模型。"""

    pet_id: UUID = Field(..., description="宠物ID")
    weight: Decimal = Field(..., ge=0, le=999.99, description="体重 (kg)")
    measurement_time: datetime = Field(..., description="测量时间")
    notes: Optional[str] = Field(None, description="备注")
    photo_url: Optional[str] = Field(None, description="照片URL")


class WeightLogResponse(BaseModel):
    """体重记录响应模型。"""

    id: UUID = Field(..., description="记录ID")
    pet_id: UUID = Field(..., description="宠物ID")
    user_id: UUID = Field(..., description="用户ID")
    weight: Decimal = Field(..., description="体重 (kg)")
    measurement_time: datetime = Field(..., description="测量时间")
    notes: Optional[str] = Field(None, description="备注")
    photo_url: Optional[str] = Field(None, description="照片URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        """Pydantic 配置。"""
        from_attributes = True


class LogListResponse(BaseModel):
    """通用日志列表响应模型。"""

    total: int = Field(..., description="总数量")
    items: List = Field(..., description="日志列表")
