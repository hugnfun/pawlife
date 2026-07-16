"""initial

Revision ID: 001
Revises:
Create Date: 2026-04-27 19:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 启用 pgvector 扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 用户表
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('wechat_openid', sa.String(255), unique=True, nullable=False, index=True, comment='微信 openid'),
        sa.Column('wechat_unionid', sa.String(255), unique=True, nullable=True, index=True, comment='微信 unionid'),
        sa.Column('nickname', sa.String(100), nullable=True, comment='用户昵称'),
        sa.Column('avatar_url', sa.Text, nullable=True, comment='头像 URL'),
        sa.Column('phone_number', sa.String(20), unique=True, nullable=True, comment='手机号'),
        sa.Column('role', postgresql.ENUM('admin', 'user', name='userrole'), nullable=False, server_default='user', comment='用户角色'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true'), comment='是否激活'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True, comment='最后登录时间'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 家庭组表
    op.create_table(
        'families',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, comment='家庭组名称'),
        sa.Column('invite_code', sa.String(6), unique=True, nullable=False, index=True, comment='邀请码'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 家庭成员关系表
    op.create_table(
        'family_members',
        sa.Column('family_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('families.id', ondelete='CASCADE'), primary_key=True, comment='家庭ID'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, comment='用户ID'),
        sa.Column('role', postgresql.ENUM('owner', 'member', 'guest', name='familyrole'), nullable=False, server_default='member', comment='在家庭中的角色'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False, comment='加入时间'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 宠物表
    op.create_table(
        'pets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, comment='宠物名字'),
        sa.Column('species', postgresql.ENUM('dog', 'cat', 'bird', 'rabbit', 'other', name='petspecies'), nullable=False, comment='物种'),
        sa.Column('breed', sa.String(100), nullable=True, comment='品种'),
        sa.Column('gender', postgresql.ENUM('male', 'female', 'unknown', name='petgender'), nullable=False, server_default='unknown', comment='性别'),
        sa.Column('birth_date', sa.Date, nullable=True, comment='出生日期'),
        sa.Column('neutered_status', postgresql.ENUM('neutered', 'intact', 'unknown', name='neuteredstatus'), nullable=False, server_default='unknown', comment='绝育状态'),
        sa.Column('current_weight', sa.Numeric(5, 2), nullable=True, comment='当前体重 (kg)'),
        sa.Column('ideal_weight', sa.Numeric(5, 2), nullable=True, comment='理想体重 (kg)'),
        sa.Column('body_condition_score', postgresql.ENUM('1', '2', '3', '4', '5', '6', '7', '8', '9', name='bodyconditionscore'), nullable=True, comment='体型评分'),
        sa.Column('known_diseases', sa.Text, nullable=True, comment='已知疾病/过敏史'),
        sa.Column('long_term_medication', sa.Text, nullable=True, comment='长期用药'),
        sa.Column('main_food_brand', sa.String(100), nullable=True, comment='主粮品牌'),
        sa.Column('allergy_blacklist', sa.Text, nullable=True, comment='过敏食材黑名单'),
        sa.Column('avatar_url', sa.Text, nullable=True, comment='宠物头像 URL'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true'), comment='是否活跃'),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='拥有者ID'),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('families.id', ondelete='SET NULL'), nullable=True, comment='家庭ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 饮食记录表
    op.create_table(
        'meal_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pets.id', ondelete='CASCADE'), nullable=False, comment='宠物ID'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='记录用户ID'),
        sa.Column('food_name', sa.String(100), nullable=False, comment='食物名称'),
        sa.Column('food_type', postgresql.ENUM('main', 'treat', 'supplement', 'other', name='foodtype'), nullable=False, server_default='main', comment='食物类型'),
        sa.Column('amount', sa.Numeric(7, 2), nullable=False, comment='分量'),
        sa.Column('unit', sa.String(20), nullable=False, server_default='g', comment='单位'),
        sa.Column('meal_time', sa.DateTime(timezone=True), nullable=False, comment='喂食时间'),
        sa.Column('notes', sa.Text, nullable=True, comment='备注'),
        sa.Column('photo_url', sa.Text, nullable=True, comment='照片URL'),
        sa.Column('is_duplicate', sa.Boolean, nullable=False, server_default=sa.text('false'), comment='是否重复喂食'),
        sa.Column('duplicate_of', postgresql.UUID(as_uuid=True), sa.ForeignKey('meal_logs.id', ondelete='SET NULL'), nullable=True, comment='重复的记录ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 活动记录表
    op.create_table(
        'activity_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pets.id', ondelete='CASCADE'), nullable=False, comment='宠物ID'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='记录用户ID'),
        sa.Column('activity_type', postgresql.ENUM('walk', 'run', 'play', 'swim', 'training', 'other', name='activitytype'), nullable=False, comment='活动类型'),
        sa.Column('duration_minutes', sa.Integer, nullable=False, comment='持续时间 (分钟)'),
        sa.Column('activity_time', sa.DateTime(timezone=True), nullable=False, comment='活动时间'),
        sa.Column('intensity', sa.String(20), nullable=True, comment='强度'),
        sa.Column('calories_estimated', sa.Numeric(7, 2), nullable=True, comment='预估消耗卡路里'),
        sa.Column('notes', sa.Text, nullable=True, comment='备注'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 体重记录表
    op.create_table(
        'weight_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pets.id', ondelete='CASCADE'), nullable=False, comment='宠物ID'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='记录用户ID'),
        sa.Column('weight', sa.Numeric(5, 2), nullable=False, comment='体重 (kg)'),
        sa.Column('measurement_time', sa.DateTime(timezone=True), nullable=False, comment='测量时间'),
        sa.Column('notes', sa.Text, nullable=True, comment='备注'),
        sa.Column('photo_url', sa.Text, nullable=True, comment='照片URL'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 疫苗记录表
    op.create_table(
        'vaccine_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pets.id', ondelete='CASCADE'), nullable=False, comment='宠物ID'),
        sa.Column('vaccine_name', sa.String(100), nullable=False, comment='疫苗名称'),
        sa.Column('administered_date', sa.Date, nullable=False, comment='接种日期'),
        sa.Column('next_due_date', sa.Date, nullable=True, comment='下次接种日期'),
        sa.Column('notes', sa.Text, nullable=True, comment='备注'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 驱虫记录表
    op.create_table(
        'deworming_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pets.id', ondelete='CASCADE'), nullable=False, comment='宠物ID'),
        sa.Column('deworming_type', postgresql.ENUM('internal', 'external', 'both', name='dewormingtype'), nullable=False, comment='驱虫类型'),
        sa.Column('product_name', sa.String(100), nullable=False, comment='产品名称'),
        sa.Column('administered_date', sa.Date, nullable=False, comment='驱虫日期'),
        sa.Column('next_due_date', sa.Date, nullable=True, comment='下次驱虫日期'),
        sa.Column('cycle_days', sa.Integer, nullable=True, comment='驱虫周期 (天)'),
        sa.Column('notes', sa.Text, nullable=True, comment='备注'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 提醒表
    op.create_table(
        'reminders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pets.id', ondelete='CASCADE'), nullable=False, comment='宠物ID'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='创建用户ID'),
        sa.Column('reminder_type', postgresql.ENUM('feeding', 'medication', 'deworming', 'vaccine', 'weighing', 'bath', 'nail_trim', 'other', name='remindertype'), nullable=False, comment='提醒类型'),
        sa.Column('title', sa.String(100), nullable=False, comment='提醒标题'),
        sa.Column('description', sa.Text, nullable=True, comment='提醒描述'),
        sa.Column('remind_at', sa.DateTime(timezone=True), nullable=False, comment='提醒时间'),
        sa.Column('repeat_type', postgresql.ENUM('none', 'daily', 'every_x_days', 'weekly', 'monthly', 'yearly', name='repeattype'), nullable=False, server_default='none', comment='重复类型'),
        sa.Column('repeat_interval', sa.Integer, nullable=True, comment='重复间隔天数'),
        sa.Column('status', postgresql.ENUM('pending', 'sent', 'completed', 'skipped', 'cancelled', name='reminderstatus'), nullable=False, server_default='pending', comment='提醒状态'),
        sa.Column('last_reminded_at', sa.DateTime(timezone=True), nullable=True, comment='上次提醒时间'),
        sa.Column('next_remind_at', sa.DateTime(timezone=True), nullable=True, comment='下次提醒时间'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true'), comment='是否激活'),
        sa.Column('notes', sa.Text, nullable=True, comment='备注'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 食谱表
    op.create_table(
        'recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pets.id', ondelete='CASCADE'), nullable=False, comment='宠物ID'),
        sa.Column('name', sa.String(100), nullable=False, comment='食谱名称'),
        sa.Column('description', sa.Text, nullable=True, comment='食谱描述'),
        sa.Column('recipe_type', postgresql.ENUM('daily', 'weight_loss', 'weight_gain', 'special', 'homemade', name='recipetype'), nullable=False, server_default='daily', comment='食谱类型'),
        sa.Column('source', postgresql.ENUM('ai_generated', 'user_custom', 'recommended', 'imported', name='recipesource'), nullable=False, server_default='ai_generated', comment='食谱来源'),
        sa.Column('daily_calories_target', sa.Numeric(8, 2), nullable=True, comment='目标每日热量 (kcal)'),
        sa.Column('protein_target_percent', sa.Numeric(5, 2), nullable=True, comment='蛋白质目标百分比'),
        sa.Column('fat_target_percent', sa.Numeric(5, 2), nullable=True, comment='脂肪目标百分比'),
        sa.Column('carb_target_percent', sa.Numeric(5, 2), nullable=True, comment='碳水目标百分比'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true'), comment='是否当前使用'),
        sa.Column('notes', sa.Text, nullable=True, comment='AI 生成备注/建议'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 食谱食材表
    op.create_table(
        'recipe_ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('recipe_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('recipes.id', ondelete='CASCADE'), nullable=False, comment='食谱ID'),
        sa.Column('food_name', sa.String(100), nullable=False, comment='食物名称'),
        sa.Column('brand', sa.String(100), nullable=True, comment='品牌'),
        sa.Column('amount', sa.Numeric(7, 2), nullable=False, comment='分量'),
        sa.Column('unit', sa.String(20), nullable=False, server_default='g', comment='单位'),
        sa.Column('calories_per_unit', sa.Numeric(8, 2), nullable=True, comment='每单位热量 (kcal)'),
        sa.Column('protein_per_unit', sa.Numeric(6, 2), nullable=True, comment='每单位蛋白质 (g)'),
        sa.Column('fat_per_unit', sa.Numeric(6, 2), nullable=True, comment='每单位脂肪 (g)'),
        sa.Column('carb_per_unit', sa.Numeric(6, 2), nullable=True, comment='每单位碳水 (g)'),
        sa.Column('is_allergy_risk', sa.Boolean, nullable=False, server_default=sa.text('false'), comment='是否为过敏风险食材'),
        sa.Column('notes', sa.Text, nullable=True, comment='备注'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 宠物长期记忆表 (pgvector)
    op.create_table(
        'pet_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pets.id', ondelete='CASCADE'), nullable=False, comment='宠物ID'),
        sa.Column('content', sa.Text, nullable=False, comment='记忆内容文本'),
        sa.Column('embedding', sa.Text, nullable=False, comment='向量化表示'),  # pgvector Vector(1536)
        sa.Column('source', sa.String(20), nullable=False, server_default='conversation', comment='记忆来源'),
        sa.Column('importance', sa.Integer, nullable=False, server_default='3', comment='重要性评分 1-5'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 将 embedding 列类型改为 vector（USING 显式转换空表以避免 DatatypeMismatch）
    op.execute('ALTER TABLE pet_memories ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)')

    # 营养数据库表
    op.create_table(
        'food_nutritions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('food_name', sa.String(100), nullable=False, index=True, comment='食材中文名称'),
        sa.Column('food_name_en', sa.String(100), nullable=True, comment='食材英文名称'),
        sa.Column('food_category', sa.String(50), nullable=False, index=True, comment='食材分类'),
        sa.Column('is_common', sa.Boolean, nullable=False, server_default=sa.text('true'), comment='是否为常见食材'),
        sa.Column('is_pet_safe', sa.Boolean, nullable=False, server_default=sa.text('true'), comment='是否对宠物安全'),
        sa.Column('calories', sa.Numeric(8, 2), nullable=True, comment='热量 (kcal / 100g)'),
        sa.Column('protein', sa.Numeric(6, 2), nullable=True, comment='蛋白质 (g / 100g)'),
        sa.Column('fat', sa.Numeric(6, 2), nullable=True, comment='脂肪 (g / 100g)'),
        sa.Column('carbs', sa.Numeric(6, 2), nullable=True, comment='碳水化合物 (g / 100g)'),
        sa.Column('fiber', sa.Numeric(6, 2), nullable=True, comment='膳食纤维 (g / 100g)'),
        sa.Column('ash', sa.Numeric(6, 2), nullable=True, comment='灰分 (g / 100g)'),
        sa.Column('calcium', sa.Numeric(8, 2), nullable=True, comment='钙 (mg / 100g)'),
        sa.Column('phosphorus', sa.Numeric(8, 2), nullable=True, comment='磷 (mg / 100g)'),
        sa.Column('omega3', sa.Numeric(6, 3), nullable=True, comment='ω-3 脂肪酸 (g / 100g)'),
        sa.Column('omega6', sa.Numeric(6, 3), nullable=True, comment='ω-6 脂肪酸 (g / 100g)'),
        sa.Column('water', sa.Numeric(6, 2), nullable=True, comment='水分 (g / 100g)'),
        sa.Column('usda_fdc_id', sa.Integer, nullable=True, comment='USDA FoodData Central 食品ID'),
        sa.Column('notes', sa.Text, nullable=True, comment='备注信息'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
    )

    # 审计日志表
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False, index=True, comment='用户ID'),
        sa.Column('action', sa.String(50), nullable=False, comment='操作类型'),
        sa.Column('resource_type', sa.String(50), nullable=False, comment='资源类型'),
        sa.Column('resource_id', sa.String(36), nullable=True, comment='资源 ID'),
        sa.Column('detail', postgresql.JSONB, nullable=True, comment='操作详情'),
        sa.Column('ip_address', sa.String(45), nullable=True, comment='客户端 IP'),
        sa.Column('user_agent', sa.String(500), nullable=True, comment='User-Agent'),
        sa.Column('status', sa.String(20), nullable=False, server_default='success', comment='操作结果'),
        sa.Column('error_message', sa.Text, nullable=True, comment='错误信息'),
        sa.Column('created_at', sa.DateTime, nullable=False, comment='创建时间'),
    )
    op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])

    # 额外索引
    op.create_index('ix_meal_logs_pet_id', 'meal_logs', ['pet_id'])
    op.create_index('ix_meal_logs_user_id', 'meal_logs', ['user_id'])
    op.create_index('ix_meal_logs_meal_time', 'meal_logs', ['meal_time'])
    op.create_index('ix_activity_logs_pet_id', 'activity_logs', ['pet_id'])
    op.create_index('ix_weight_logs_pet_id', 'weight_logs', ['pet_id'])
    op.create_index('ix_weight_logs_measurement_time', 'weight_logs', ['measurement_time'])
    op.create_index('ix_reminders_pet_id', 'reminders', ['pet_id'])
    op.create_index('ix_reminders_user_id', 'reminders', ['user_id'])
    op.create_index('ix_pet_memories_pet_id', 'pet_memories', ['pet_id'])
    op.create_index('ix_recipes_pet_id', 'recipes', ['pet_id'])


def downgrade() -> None:
    # 按依赖关系逆序删除
    op.drop_table('audit_logs')
    op.drop_table('food_nutritions')
    op.drop_table('pet_memories')
    op.drop_table('recipe_ingredients')
    op.drop_table('recipes')
    op.drop_table('reminders')
    op.drop_table('deworming_records')
    op.drop_table('vaccine_records')
    op.drop_table('weight_logs')
    op.drop_table('activity_logs')
    op.drop_table('meal_logs')
    op.drop_table('pets')
    op.drop_table('family_members')
    op.drop_table('families')
    op.drop_table('users')

    # 删除枚举类型
    op.execute('DROP TYPE IF EXISTS userrole')
    op.execute('DROP TYPE IF EXISTS familyrole')
    op.execute('DROP TYPE IF EXISTS petspecies')
    op.execute('DROP TYPE IF EXISTS petgender')
    op.execute('DROP TYPE IF EXISTS neuteredstatus')
    op.execute('DROP TYPE IF EXISTS bodyconditionscore')
    op.execute('DROP TYPE IF EXISTS foodtype')
    op.execute('DROP TYPE IF EXISTS activitytype')
    op.execute('DROP TYPE IF EXISTS dewormingtype')
    op.execute('DROP TYPE IF EXISTS remindertype')
    op.execute('DROP TYPE IF EXISTS repeattype')
    op.execute('DROP TYPE IF EXISTS reminderstatus')
    op.execute('DROP TYPE IF EXISTS recipetype')
    op.execute('DROP TYPE IF EXISTS recipesource')

    # 删除 pgvector 扩展（谨慎操作）
    # op.execute('DROP EXTENSION IF EXISTS vector')
